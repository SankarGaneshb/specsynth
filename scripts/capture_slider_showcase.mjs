/**
 * Automated Showcase Screenshot Generator for PerandamΨ Sidebar & Sliders.
 * Captures 5 high-resolution state screenshots:
 *  1. Baseline Galaxy Selection (SED tab + metrics + sliders)
 *  2. Synthetic JWST Photometry Bar (6 bands + uJy + S/N flags)
 *  3. Slider Update: High Redshift (z = 4.50) + SED Lyman shift
 *  4. Slider Update: Heavy Dust (Av = 2.50 mag) + Color-Color track
 *  5. JWST Proposal & Observing Feasibility Modal
 */

import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, '..');

const BRIDGE_PORT = 8000;
const CDP_PORT = 9222;
const APP_URL = `http://127.0.0.1:${BRIDGE_PORT}`;
const ARTIFACT_DIR = 'C:\\Users\\bsank\\.gemini\\antigravity\\brain\\11b6a273-51ad-4a74-9e31-731fe71e6e4f';

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

class CDPClient {
  constructor(wsUrl) {
    this.wsUrl = wsUrl;
    this.ws = null;
    this.msgId = 0;
    this.pending = new Map();
  }

  async connect() {
    this.ws = new WebSocket(this.wsUrl);
    return new Promise((resolve, reject) => {
      this.ws.onopen = () => resolve();
      this.ws.onerror = (err) => reject(err);
      this.ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.id && this.pending.has(msg.id)) {
          const { resolve, reject } = this.pending.get(msg.id);
          this.pending.delete(msg.id);
          if (msg.error) reject(new Error(msg.error.message || JSON.stringify(msg.error)));
          else resolve(msg.result);
        }
      };
    });
  }

  send(method, params = {}) {
    const id = ++this.msgId;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }

  async evaluate(expression) {
    const res = await this.send('Runtime.evaluate', {
      expression,
      returnByValue: true,
      awaitPromise: true,
    });
    return res.result?.value;
  }

  async captureScreenshot(filename) {
    const shot = await this.send('Page.captureScreenshot', { format: 'png' });
    const localPath = path.resolve(rootDir, filename);
    const artifactPath = path.resolve(ARTIFACT_DIR, filename);

    fs.writeFileSync(localPath, Buffer.from(shot.data, 'base64'));
    fs.writeFileSync(artifactPath, Buffer.from(shot.data, 'base64'));
    console.log(`  ✓ Saved screenshot: ${filename} (${Math.round(shot.data.length / 1024)} KB)`);
  }

  close() {
    if (this.ws) this.ws.close();
  }
}

function findPythonBinary(rootDir) {
  if (process.env.PYTHON_BIN && fs.existsSync(process.env.PYTHON_BIN)) return process.env.PYTHON_BIN;
  if (process.env.VIRTUAL_ENV) {
    const venvWin = path.resolve(process.env.VIRTUAL_ENV, 'Scripts/python.exe');
    const venvNix = path.resolve(process.env.VIRTUAL_ENV, 'bin/python');
    if (fs.existsSync(venvWin)) return venvWin;
    if (fs.existsSync(venvNix)) return venvNix;
  }
  const candidates = [
    path.resolve(rootDir, '.venv/Scripts/python.exe'),
    path.resolve(rootDir, '.venv/bin/python'),
    path.resolve(rootDir, 'venv/Scripts/python.exe'),
    path.resolve(rootDir, 'venv/bin/python'),
    path.resolve(process.cwd(), '.venv/Scripts/python.exe'),
    path.resolve(process.cwd(), '.venv/bin/python'),
    path.resolve(process.cwd(), '../.venv/Scripts/python.exe'),
    path.resolve(process.cwd(), '../.venv/bin/python'),
  ];
  for (const c of candidates) {
    if (fs.existsSync(c)) return c;
  }
  return 'python';
}

function findChromiumBinary() {
  if (process.env.CHROME_BIN && fs.existsSync(process.env.CHROME_BIN)) return process.env.CHROME_BIN;
  if (process.env.CHROME_PATH && fs.existsSync(process.env.CHROME_PATH)) return process.env.CHROME_PATH;
  if (process.env.CHROMIUM_PATH && fs.existsSync(process.env.CHROMIUM_PATH)) return process.env.CHROMIUM_PATH;

  const candidates = [
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
    'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
    '/usr/bin/google-chrome',
    '/usr/bin/google-chrome-stable',
    '/usr/bin/chromium',
    '/usr/bin/chromium-browser',
    '/snap/bin/chromium',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
  ];
  for (const c of candidates) {
    if (fs.existsSync(c)) return c;
  }
  if (process.platform !== 'win32') {
    return 'chromium-browser';
  }
  return null;
}

async function isPortOpen(url) {
  try {
    const headers = {};
    if (process.env.SPECSYNTH_BRIDGE_TOKEN) {
      headers['Authorization'] = `Bearer ${process.env.SPECSYNTH_BRIDGE_TOKEN}`;
    }
    const res = await fetch(url, { headers, signal: AbortSignal.timeout(2000) });
    return res.status === 200 || res.status === 401;
  } catch {
    return false;
  }
}

async function main() {
  console.log('=== PerandamΨ Sidebar & Slider Screenshot Generator ===\n');

  let bridgeProc = null;
  let chromeProc = null;
  let cdp = null;

  try {
    // 1. Ensure Bridge Server is running
    const bridgeAlive = await isPortOpen(`${APP_URL}/api/health`);
    if (!bridgeAlive) {
      const pyBin = findPythonBinary(rootDir);
      console.log(`Starting local bridge server using ${pyBin}...`);
      bridgeProc = spawn(pyBin, ['-m', 'specsynth.mcp.bridge', '--port', String(BRIDGE_PORT)], {
        cwd: rootDir,
        stdio: ['ignore', 'pipe', 'pipe'],
        env: {
          ...process.env,
          PYTHONIOENCODING: 'utf-8',
          PYTHONUNBUFFERED: '1',
        },
      });
      for (let i = 0; i < 40; i++) {
        await sleep(500);
        if (await isPortOpen(`${APP_URL}/api/health`)) break;
      }
    }

    // 2. Launch Chrome Headless
    const chromeBin = findChromiumBinary();
    if (!chromeBin) throw new Error('No supported Chromium browser found (Chrome, Edge, or Chromium)');
    const profileDir = path.resolve(process.env.TEMP || '.', `chrome_shot_${Date.now()}`);
    chromeProc = spawn(
      chromeBin,
      [
        '--headless=new',
        '--no-sandbox',
        '--disable-gpu',
        '--disable-software-rasterizer',
        `--remote-debugging-port=${CDP_PORT}`,
        `--user-data-dir=${profileDir}`,
        '--window-size=1600,1000',
        '--no-first-run',
        '--no-default-browser-check',
        'about:blank',
      ],
      { stdio: 'ignore' }
    );

    for (let i = 0; i < 25; i++) {
      await sleep(200);
      if (await isPortOpen(`http://127.0.0.1:${CDP_PORT}/json/version`)) break;
    }

    const tabs = await fetch(`http://127.0.0.1:${CDP_PORT}/json/list`).then((r) => r.json());
    const targetTab = tabs.find((t) => t.type === 'page') || tabs[0];
    cdp = new CDPClient(targetTab.webSocketDebuggerUrl);
    await cdp.connect();

    await cdp.send('Page.enable');
    await cdp.send('Runtime.enable');
    await cdp.send('DOM.enable');
    await cdp.send('Emulation.setDeviceMetricsOverride', {
      width: 1600,
      height: 1000,
      deviceScaleFactor: 1,
      mobile: false,
    });

    // 3. Navigate to App
    console.log('Navigating to PerandamΨ...');
    await cdp.send('Page.navigate', { url: APP_URL });
    for (let i = 0; i < 30; i++) {
      await sleep(300);
      const readyState = await cdp.evaluate('document.readyState');
      const hasBrand = await cdp.evaluate('document.body.innerText.includes("PerandamΨ")');
      if (readyState === 'complete' && hasBrand) break;
    }
    await sleep(600);

    // 4. Select Galaxy TNG-DISC-01 (or option 1)
    console.log('Selecting Galaxy...');
    await cdp.evaluate(`
      (() => {
        const selects = Array.from(document.querySelectorAll('header select'));
        const jumpSelect = selects.find(s => s.innerText.includes('Jump to Galaxy') || s.options.length > 10);
        if (jumpSelect) {
          jumpSelect.value = jumpSelect.options[1].value;
          jumpSelect.dispatchEvent(new Event('change', { bubbles: true }));
        }
      })()
    `);
    await sleep(800);

    // Screenshot 1: Baseline Galaxy Selection (SED tab + metrics + sliders)
    console.log('[1/5] Capturing Baseline Galaxy Selection...');
    await cdp.captureScreenshot('perandam_1_baseline_galaxy.png');

    // Screenshot 2: Switch to Photometry Tab
    console.log('[2/5] Switching to Photometry Tab & Capturing...');
    await cdp.evaluate(`
      (() => {
        const buttons = Array.from(document.querySelectorAll('aside button, .galaxy-inspector button'));
        const photBtn = buttons.find(b => b.innerText.includes('Photometry'));
        if (photBtn) photBtn.click();
      })()
    `);
    await sleep(500);
    await cdp.captureScreenshot('perandam_2_photometry_tab.png');

    // Screenshot 3: Slide Redshift to High-z (z = 4.50) & switch back to SED
    console.log('[3/5] Adjusting Redshift Slider to z = 4.50 & Capturing SED shift...');
    await cdp.evaluate(`
      (() => {
        // Switch back to SED tab
        const buttons = Array.from(document.querySelectorAll('aside button, .galaxy-inspector button'));
        const sedBtn = buttons.find(b => b.innerText.includes('SED'));
        if (sedBtn) sedBtn.click();

        // Adjust z slider
        const sliders = Array.from(document.querySelectorAll('input[type="range"]'));
        if (sliders.length > 0) {
          const zSlider = sliders[0];
          zSlider.value = "4.50";
          zSlider.dispatchEvent(new Event('input', { bubbles: true }));
          zSlider.dispatchEvent(new Event('change', { bubbles: true }));
        }
      })()
    `);
    await sleep(700);
    await cdp.captureScreenshot('perandam_3_slider_high_redshift.png');

    // Screenshot 4: Slide Dust to Av = 2.50 mag & switch to Color-Color Tab
    console.log('[4/5] Adjusting Dust Slider to Av = 2.50 mag & Capturing Color-Color plot...');
    await cdp.evaluate(`
      (() => {
        // Switch to Color-Color tab
        const buttons = Array.from(document.querySelectorAll('aside button, .galaxy-inspector button'));
        const ccBtn = buttons.find(b => b.innerText.includes('Color-Color'));
        if (ccBtn) ccBtn.click();

        // Adjust Av slider
        const sliders = Array.from(document.querySelectorAll('input[type="range"]'));
        if (sliders.length > 1) {
          const avSlider = sliders[1];
          avSlider.value = "2.50";
          avSlider.dispatchEvent(new Event('input', { bubbles: true }));
          avSlider.dispatchEvent(new Event('change', { bubbles: true }));
        }
      })()
    `);
    await sleep(700);
    await cdp.captureScreenshot('perandam_4_slider_dust_color_color.png');

    // Screenshot 5: Open JWST Observing Proposal Modal
    console.log('[5/5] Opening JWST Observing Feasibility Modal & Capturing...');
    await cdp.evaluate(`
      (() => {
        const buttons = Array.from(document.querySelectorAll('button'));
        const propBtn = buttons.find(b => b.innerText.includes('JWST Proposal') || b.innerText.includes('Feasibility'));
        if (propBtn) propBtn.click();
      })()
    `);
    await sleep(700);
    await cdp.captureScreenshot('perandam_5_proposal_modal.png');

    console.log('\n🎉 ALL 5 SHOWCASE SCREENSHOTS CAPTURED SUCCESSFULLY!');
  } catch (err) {
    console.error('Error during screenshot capture:', err);
    process.exit(1);
  } finally {
    if (cdp) cdp.close();
    if (chromeProc) chromeProc.kill();
    if (bridgeProc) bridgeProc.kill();
  }
}

main();
