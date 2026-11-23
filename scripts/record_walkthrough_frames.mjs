/**
 * Frame-by-frame Walkthrough Capture for PerandamΨ GitHub Demo.
 * Captures 14 sequential high-resolution frames of live UI interactions:
 *  - Sky view -> Galaxy Selection -> Sidebar open
 *  - Photometry bar inspection
 *  - Smooth Redshift slider sweep (z = 1.0 -> 4.5)
 *  - Dynamic Photometry update
 *  - Color-Color plot & Dust slider sweep (Av = 0.5 -> 2.5)
 *  - JWST Proposal & Observing Feasibility Modal
 *  - Dual Dataset Switcher (508 -> 100)
 */

import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, '..');
const framesDir = path.resolve(rootDir, '.tmp_frames');

const BRIDGE_PORT = 8000;
const CDP_PORT = 9222;
const APP_URL = `http://127.0.0.1:${BRIDGE_PORT}`;

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

  async captureFrame(frameNum, label) {
    const shot = await this.send('Page.captureScreenshot', { format: 'png' });
    const filename = `frame_${String(frameNum).padStart(2, '0')}.png`;
    const filePath = path.resolve(framesDir, filename);
    fs.writeFileSync(filePath, Buffer.from(shot.data, 'base64'));
    console.log(`  [Frame ${frameNum}/14] ${label} (${Math.round(shot.data.length / 1024)} KB)`);
  }

  close() {
    if (this.ws) this.ws.close();
  }
}

async function isPortOpen(url) {
  try {
    const res = await fetch(url);
    return res.ok;
  } catch {
    return false;
  }
}

async function main() {
  console.log('=== PerandamΨ Walkthrough Frame Capture ===\n');

  if (fs.existsSync(framesDir)) {
    fs.rmSync(framesDir, { recursive: true, force: true });
  }
  fs.mkdirSync(framesDir, { recursive: true });

  let bridgeProc = null;
  let chromeProc = null;
  let cdp = null;

  try {
    // 1. Check or start bridge server
    if (!(await isPortOpen(`${APP_URL}/api/health`))) {
      console.log('Starting local bridge server...');
      const venvPy = path.resolve(rootDir, '.venv/Scripts/python.exe');
      const pyBin = fs.existsSync(venvPy) ? venvPy : 'python';
      bridgeProc = spawn(pyBin, ['-m', 'specsynth.mcp.bridge', '--port', String(BRIDGE_PORT)], {
        cwd: rootDir,
        stdio: 'ignore',
      });
      for (let i = 0; i < 25; i++) {
        await sleep(300);
        if (await isPortOpen(`${APP_URL}/api/health`)) break;
      }
    }

    // 2. Launch Chrome
    const chromePaths = [
      'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
      'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
    ];
    const chromeBin = chromePaths.find((p) => fs.existsSync(p));
    const profileDir = path.resolve(process.env.TEMP || '.', `chrome_walk_${Date.now()}`);
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

    // 3. Navigate
    console.log('Navigating to PerandamΨ...');
    await cdp.send('Page.navigate', { url: APP_URL });
    for (let i = 0; i < 30; i++) {
      await sleep(300);
      const readyState = await cdp.evaluate('document.readyState');
      const hasBrand = await cdp.evaluate('document.body.innerText.includes("PerandamΨ")');
      if (readyState === 'complete' && hasBrand) break;
    }
    await sleep(800);

    // Frame 01: Initial Landing View (Sky Canvas with all galaxies)
    await cdp.captureFrame(1, 'Initial Landing View (Sky Canvas with 508 galaxies)');

    // Frame 02: Selecting Galaxy via Jump Selector
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
    await sleep(600);
    // Frame 03: Galaxy Inspector Open with Baseline SED & Metrics
    await cdp.captureFrame(2, 'Galaxy Inspector Open (TNG-DISC-01 baseline SED & metrics)');

    // Frame 04: Switch to Photometry Tab
    await cdp.evaluate(`
      (() => {
        const buttons = Array.from(document.querySelectorAll('aside button, .galaxy-inspector button'));
        const photBtn = buttons.find(b => b.innerText.includes('Photometry'));
        if (photBtn) photBtn.click();
      })()
    `);
    await sleep(500);
    await cdp.captureFrame(3, 'Photometry Bar (All 6 NIRCam bands with uJy fluxes & S/N flags)');

    // Switch back to SED tab
    await cdp.evaluate(`
      (() => {
        const buttons = Array.from(document.querySelectorAll('aside button, .galaxy-inspector button'));
        const sedBtn = buttons.find(b => b.innerText.includes('SED'));
        if (sedBtn) sedBtn.click();
      })()
    `);
    await sleep(400);

    // Sweep Redshift Slider: z = 1.80, 2.80, 3.80, 4.50
    const zSteps = ['1.80', '2.80', '3.80', '4.50'];
    let frameIdx = 4;
    for (const zVal of zSteps) {
      await cdp.evaluate(`
        (() => {
          const sliders = Array.from(document.querySelectorAll('input[type="range"]'));
          if (sliders.length > 0) {
            const zSlider = sliders[0];
            zSlider.value = "${zVal}";
            zSlider.dispatchEvent(new Event('input', { bubbles: true }));
            zSlider.dispatchEvent(new Event('change', { bubbles: true }));
          }
        })()
      `);
      await sleep(400);
      await cdp.captureFrame(frameIdx++, `Redshift Slider swept to z = ${zVal} (in-flight forward model)`);
    }

    // Frame 08: Switch to Photometry tab to show updated photometry at z = 4.50
    await cdp.evaluate(`
      (() => {
        const buttons = Array.from(document.querySelectorAll('aside button, .galaxy-inspector button'));
        const photBtn = buttons.find(b => b.innerText.includes('Photometry'));
        if (photBtn) photBtn.click();
      })()
    `);
    await sleep(500);
    await cdp.captureFrame(frameIdx++, 'Photometry Bar at z = 4.50 (recalculated fluxes & Lyman dropout)');

    // Frame 09: Switch to Color-Color Tab
    await cdp.evaluate(`
      (() => {
        const buttons = Array.from(document.querySelectorAll('aside button, .galaxy-inspector button'));
        const ccBtn = buttons.find(b => b.innerText.includes('Color-Color'));
        if (ccBtn) ccBtn.click();
      })()
    `);
    await sleep(500);
    await cdp.captureFrame(frameIdx++, 'Color-Color Diagnostic Plot with evolutionary track & target reticle');

    // Sweep Dust Slider: Av = 1.50, 2.50
    const avSteps = ['1.50', '2.50'];
    for (const avVal of avSteps) {
      await cdp.evaluate(`
        (() => {
          const sliders = Array.from(document.querySelectorAll('input[type="range"]'));
          if (sliders.length > 1) {
            const avSlider = sliders[1];
            avSlider.value = "${avVal}";
            avSlider.dispatchEvent(new Event('input', { bubbles: true }));
            avSlider.dispatchEvent(new Event('change', { bubbles: true }));
          }
        })()
      `);
      await sleep(400);
      await cdp.captureFrame(frameIdx++, `Dust Slider swept to Av = ${avVal} mag (Charlot & Fall extinction)`);
    }

    // Frame 12: Open JWST Observing Feasibility Modal
    await cdp.evaluate(`
      (() => {
        const buttons = Array.from(document.querySelectorAll('button'));
        const propBtn = buttons.find(b => b.innerText.includes('JWST Proposal') || b.innerText.includes('Feasibility'));
        if (propBtn) propBtn.click();
      })()
    `);
    await sleep(600);
    await cdp.captureFrame(frameIdx++, 'JWST Observing Feasibility Modal (Celestial/Ecliptic & NIRSpec WATA)');

    // Close modal
    await cdp.evaluate(`
      (() => {
        const closeBtn = document.querySelector('.fixed button') || Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Close'));
        if (closeBtn) closeBtn.click();
      })()
    `);
    await sleep(400);

    // Frame 13: Switch to TNG-100 Calibration Dataset
    await cdp.evaluate(`
      (() => {
        const select = document.querySelector('header select');
        if (select) {
          select.value = 'tng_100';
          select.dispatchEvent(new Event('change', { bubbles: true }));
        }
      })()
    `);
    await sleep(700);
    await cdp.captureFrame(frameIdx++, 'Dual Dataset Switcher (TNG-100 Calibration sample loaded)');

    console.log(`\n✓ All ${frameIdx - 1} frames captured into .tmp_frames/ successfully!`);
  } catch (err) {
    console.error('Error during frame capture:', err);
    process.exit(1);
  } finally {
    if (cdp) cdp.close();
    if (chromeProc) chromeProc.kill();
    if (bridgeProc) bridgeProc.kill();
  }
}

main();
