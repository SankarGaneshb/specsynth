import React, { useRef, useEffect, useState, useCallback } from 'react';
import { Galaxy, SkyColorMode } from '../types/galaxy';

interface SkyCanvasProps {
  galaxies: Galaxy[];
  selectedGalaxy: Galaxy | null;
  onSelectGalaxy: (galaxy: Galaxy) => void;
  centerRa: number;
  centerDec: number;
  fieldRadius: number;
  resetTrigger: number;
  colorMode?: SkyColorMode;
  discoveryMode?: boolean;
  rarityThreshold?: number;
}

export const SkyCanvas: React.FC<SkyCanvasProps> = ({
  galaxies,
  selectedGalaxy,
  onSelectGalaxy,
  centerRa,
  centerDec,
  fieldRadius,
  resetTrigger,
  colorMode = 'rgb',
  discoveryMode = false,
  rarityThreshold = 3.5,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  // Viewport transform state
  const [zoom, setZoom] = useState<number>(1.0);
  const [offset, setOffset] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [dragStart, setDragStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [hoveredGalaxy, setHoveredGalaxy] = useState<Galaxy | null>(null);
  const [mousePos, setMousePos] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [canvasSize, setCanvasSize] = useState<{ width: number; height: number }>({ width: 0, height: 0 });

  // Reset view to center on trigger
  useEffect(() => {
    setZoom(1.0);
    setOffset({ x: 0, y: 0 });
  }, [resetTrigger]);

  // Coordinate projection helper: RA/Dec -> Screen Pixels
  const projectCoordinates = useCallback(
    (ra: number, dec: number, width: number, height: number, zFactor: number, off: { x: number; y: number }) => {
      const baseScale = Math.min(width, height) / (2.2 * fieldRadius);
      const totalScale = baseScale * zFactor;

      // In astronomy: RA increases to the left (East), Dec increases upwards (North)
      const cosDecCenter = Math.cos((centerDec * Math.PI) / 180);
      const dx = (centerRa - ra) * cosDecCenter * totalScale;
      const dy = (centerDec - dec) * totalScale;

      const screenX = width / 2 + dx + off.x;
      const screenY = height / 2 + dy + off.y;

      return { x: screenX, y: screenY };
    },
    [centerRa, centerDec, fieldRadius]
  );

  // Helper to ensure valid color byte in [0, 255]
  const clampByte = (val: number, fallback = 128): number => {
    if (isNaN(val) || !isFinite(val)) return fallback;
    return Math.max(0, Math.min(255, Math.round(val)));
  };

  // Compute color based on scientific mode, returning clean numeric RGB components
  const getGalaxyRgb = useCallback(
    (g: Galaxy): { r: number; g: number; b: number } => {
      if (colorMode === 'redshift') {
        // Cosmological Redshift Colormap: z in [0.2, 8.5]
        const zVal = typeof g.redshift === 'number' && !isNaN(g.redshift) ? g.redshift : 1.0;
        const t = Math.max(0, Math.min(1, (zVal - 0.2) / 8.0));
        if (t < 0.3) {
          const f = t / 0.3;
          return {
            r: clampByte(56 + f * (52 - 56)),
            g: clampByte(189 + f * (211 - 189)),
            b: clampByte(248 + f * (153 - 248)),
          };
        } else if (t < 0.65) {
          const f = (t - 0.3) / 0.35;
          return {
            r: clampByte(52 + f * (251 - 52)),
            g: clampByte(211 + f * (191 - 211)),
            b: clampByte(153 + f * (36 - 153)),
          };
        } else {
          const f = (t - 0.65) / 0.35;
          return {
            r: clampByte(251 + f * (244 - 251)),
            g: clampByte(191 + f * (63 - 191)),
            b: clampByte(36 + f * (94 - 36)),
          };
        }
      } else if (colorMode === 'ssfr') {
        // Specific Star Formation Rate (Bimodality)
        const ssfrVal = (g.sfr && g.stellar_mass && g.stellar_mass > 0) ? (g.sfr / g.stellar_mass) : 1e-12;
        const logSSFR = Math.log10(Math.max(1e-13, ssfrVal));
        if (logSSFR > -10.0) {
          return { r: 96, g: 165, b: 250 }; // Star-forming blue cloud
        } else if (logSSFR > -10.8) {
          return { r: 52, g: 211, b: 153 }; // Green Valley
        } else {
          return { r: 244, g: 63, b: 94 }; // Quiescent red sequence
        }
      } else if (colorMode === 'mass') {
        // Stellar Mass log M* in [7.5, 11.5]
        const mVal = typeof g.log_mstar === 'number' && !isNaN(g.log_mstar) ? g.log_mstar : 9.5;
        const t = Math.max(0, Math.min(1, (mVal - 7.5) / 4.0));
        return {
          r: clampByte(129 + t * (254 - 129)),
          g: clampByte(140 + t * (240 - 140)),
          b: clampByte(248 - t * 110),
        };
      } else {
        // True Astronomical RGB Composite from NIRCam F444W, F200W, F090W
        // Guard against negative fluxes (e.g. TNG-ANOM-01) by clamping to 0!
        const rFlux = Math.max(0, g.fluxes?.['jwst_f444w'] ?? 1e-32);
        const gFlux = Math.max(0, g.fluxes?.['jwst_f200w'] ?? 1e-32);
        const bFlux = Math.max(0, g.fluxes?.['jwst_f090w'] ?? 1e-32);

        const maxFlux = Math.max(rFlux, gFlux, bFlux);
        if (maxFlux <= 0) return { r: 200, g: 220, b: 255 };

        const rRaw = 255 * Math.pow(rFlux / maxFlux, 0.4);
        const gRaw = 255 * Math.pow(gFlux / maxFlux, 0.4);
        const bRaw = 255 * Math.pow(bFlux / maxFlux, 0.4);

        const boost = Math.max(rRaw, gRaw, bRaw);
        const minLum = 180;
        const factor = boost > 0 && boost < minLum ? minLum / boost : 1;

        return {
          r: clampByte(rRaw * factor),
          g: clampByte(gRaw * factor),
          b: clampByte(bRaw * factor),
        };
      }
    },
    [colorMode]
  );

  // Main Render Loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animId: number;

    const render = () => {
      const width = canvas.width || canvas.parentElement?.clientWidth || window.innerWidth;
      const height = canvas.height || canvas.parentElement?.clientHeight || window.innerHeight;

      // 1. Deep Space Background
      ctx.fillStyle = '#03050c';
      ctx.fillRect(0, 0, width, height);

      // Subtle background nebula/cosmic gradient
      const bgGrad = ctx.createRadialGradient(
        width / 2 + offset.x,
        height / 2 + offset.y,
        10,
        width / 2 + offset.x,
        height / 2 + offset.y,
        Math.max(width, height) * 0.8
      );
      bgGrad.addColorStop(0, 'rgba(13, 19, 43, 0.35)');
      bgGrad.addColorStop(0.5, 'rgba(7, 10, 24, 0.8)');
      bgGrad.addColorStop(1, '#03050c');
      ctx.fillStyle = bgGrad;
      ctx.fillRect(0, 0, width, height);

      // 2. Draw Astrometric Grid & Axes
      ctx.strokeStyle = 'rgba(99, 102, 241, 0.12)';
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 4]);

      const nGrid = 6;
      for (let i = -nGrid; i <= nGrid; i++) {
        const gridDec = centerDec + (i * fieldRadius) / 2;
        const p1 = projectCoordinates(centerRa - fieldRadius, gridDec, width, height, zoom, offset);
        const p2 = projectCoordinates(centerRa + fieldRadius, gridDec, width, height, zoom, offset);
        ctx.beginPath();
        ctx.moveTo(p1.x, p1.y);
        ctx.lineTo(p2.x, p2.y);
        ctx.stroke();

        const gridRa = centerRa + (i * fieldRadius) / 2;
        const p3 = projectCoordinates(gridRa, centerDec - fieldRadius, width, height, zoom, offset);
        const p4 = projectCoordinates(gridRa, centerDec + fieldRadius, width, height, zoom, offset);
        ctx.beginPath();
        ctx.moveTo(p3.x, p3.y);
        ctx.lineTo(p4.x, p4.y);
        ctx.stroke();
      }
      ctx.setLineDash([]);

      // 3. Render Galaxies
      for (const g of galaxies) {
        const { x, y } = projectCoordinates(g.ra, g.dec, width, height, zoom, offset);

        // Sanity & Viewport culling
        if (isNaN(x) || isNaN(y) || x < -20 || x > width + 20 || y < -20 || y > height + 20) continue;

        // Radius based on stellar mass and zoom
        const isSelected = selectedGalaxy?.id === g.id;
        const isHovered = hoveredGalaxy?.id === g.id;
        const isDiscovery = Boolean(g.discovery_profile || (g.rarity_score && g.rarity_score >= rarityThreshold));
        const alphaFactor = discoveryMode ? (isDiscovery ? 1.0 : 0.15) : 1.0;

        const mstar = typeof g.log_mstar === 'number' && !isNaN(g.log_mstar) ? g.log_mstar : 9.5;
        const baseRadius = Math.max(1.8, Math.min(8.5, (mstar - 6.5) * 1.6));
        const currentRadius = Math.max(1.5, baseRadius * Math.pow(Math.max(0.1, zoom), 0.35));
        const rgb = getGalaxyRgb(g);

        // Discovery Auroral Beacon Halo
        if (discoveryMode && isDiscovery) {
          ctx.save();
          const auroralRadius = Math.max(3.0, currentRadius * 4.5);
          const aura = ctx.createRadialGradient(x, y, 0, x, y, auroralRadius);
          aura.addColorStop(0, 'rgba(192, 132, 252, 0.85)'); // purple-400
          aura.addColorStop(0.5, 'rgba(6, 182, 212, 0.4)'); // cyan-500
          aura.addColorStop(1, 'rgba(0, 0, 0, 0)');
          ctx.fillStyle = aura;
          ctx.beginPath();
          ctx.arc(x, y, auroralRadius, 0, Math.PI * 2);
          ctx.fill();

          // Pulsing Beacon Ring
          ctx.strokeStyle = '#c084fc';
          ctx.lineWidth = 1.6;
          ctx.beginPath();
          ctx.arc(x, y, currentRadius * 3.5 + 3, 0, Math.PI * 2);
          ctx.stroke();

          // Discovery Tag
          if (zoom >= 0.8) {
            ctx.fillStyle = '#e9d5ff';
            ctx.font = 'bold 9px monospace';
            const tag = g.discovery_profile?.class_title.split('(')[0].trim() || `${g.rarity_score?.toFixed(1)}σ Outlier`;
            ctx.fillText(tag, x + currentRadius * 3.5 + 6, y + 3);
          }
          ctx.restore();
        }

        // Glow halo
        const haloRadius = Math.max(2.0, currentRadius * 3.5);
        const haloGrad = ctx.createRadialGradient(x, y, 0, x, y, haloRadius);
        haloGrad.addColorStop(0, `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, ${0.9 * alphaFactor})`);
        haloGrad.addColorStop(0.4, `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, ${0.35 * alphaFactor})`);
        haloGrad.addColorStop(1, 'rgba(0, 0, 0, 0)');

        ctx.fillStyle = haloGrad;
        ctx.beginPath();
        ctx.arc(x, y, haloRadius, 0, Math.PI * 2);
        ctx.fill();

        // Core dot
        ctx.fillStyle = discoveryMode && !isDiscovery ? `rgba(255, 255, 255, 0.3)` : '#ffffff';
        ctx.beginPath();
        ctx.arc(x, y, currentRadius * 0.75, 0, Math.PI * 2);
        ctx.fill();

        // QC Anomaly Warning Ring
        if (g.sentry_status === 'ANOMALY') {
          ctx.save();
          ctx.strokeStyle = '#f43f5e';
          ctx.lineWidth = 1.8;
          ctx.setLineDash([4, 3]);
          ctx.beginPath();
          ctx.arc(x, y, currentRadius * 3.5 + 4, 0, Math.PI * 2);
          ctx.stroke();
          ctx.restore();
        }

        // Selected Galaxy Reticle
        if (isSelected) {
          let reticleColor = '#f59e0b';
          if (g.sentry_status === 'ANOMALY') reticleColor = '#f43f5e';
          else if (g.discovery_profile) reticleColor = '#c084fc'; // purple for discovery
          ctx.strokeStyle = reticleColor;
          ctx.lineWidth = 2;
          ctx.beginPath();
          ctx.arc(x, y, currentRadius * 4 + 4, 0, Math.PI * 2);
          ctx.stroke();

          // Crosshairs
          const rSize = currentRadius * 4 + 10;
          ctx.beginPath();
          ctx.moveTo(x - rSize, y);
          ctx.lineTo(x - currentRadius * 4 - 4, y);
          ctx.moveTo(x + currentRadius * 4 + 4, y);
          ctx.lineTo(x + rSize, y);
          ctx.moveTo(x, y - rSize);
          ctx.lineTo(x, y - currentRadius * 4 - 4);
          ctx.moveTo(x, y + currentRadius * 4 + 4);
          ctx.lineTo(x, y + rSize);
          ctx.stroke();
        }

        // Hover Reticle
        if (isHovered && !isSelected) {
          ctx.strokeStyle = '#06b6d4';
          ctx.lineWidth = 1.5;
          ctx.setLineDash([3, 3]);
          ctx.beginPath();
          ctx.arc(x, y, currentRadius * 3 + 4, 0, Math.PI * 2);
          ctx.stroke();
          ctx.setLineDash([]);
        }
      }

      // 4. Astrometric Scale Bar (bottom left)
      const scaleBarArcmin = 1.0;
      const scaleBarDeg = scaleBarArcmin / 60.0;
      const baseScale = Math.min(width, height) / (2.2 * fieldRadius);
      const scaleBarPx = scaleBarDeg * baseScale * zoom;

      if (scaleBarPx > 25 && scaleBarPx < width / 3) {
        const barX = 24;
        const barY = height - 24;
        ctx.strokeStyle = '#94a3b8';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(barX, barY);
        ctx.lineTo(barX + scaleBarPx, barY);
        ctx.stroke();

        ctx.fillStyle = '#cbd5e1';
        ctx.font = '11px monospace';
        ctx.fillText(`1.0' (${scaleBarArcmin * 60}")`, barX, barY - 6);
      }
    };

    render();
  }, [
    galaxies,
    selectedGalaxy,
    hoveredGalaxy,
    zoom,
    offset,
    centerRa,
    centerDec,
    fieldRadius,
    projectCoordinates,
    getGalaxyRgb,
    canvasSize,
    discoveryMode,
    rarityThreshold,
  ]);

  // Window Resize Listener & Dimensions Sync
  useEffect(() => {
    const handleResize = () => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const w = canvas.parentElement?.clientWidth || window.innerWidth;
      const h = canvas.parentElement?.clientHeight || window.innerHeight;
      if (w > 0 && h > 0 && (canvas.width !== w || canvas.height !== h)) {
        canvas.width = w;
        canvas.height = h;
        setCanvasSize({ width: w, height: h });
      }
    };
    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Mouse Handlers
  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    setIsDragging(true);
    setDragStart({ x: e.clientX - offset.x, y: e.clientY - offset.y });
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;
    setMousePos({ x: mouseX, y: mouseY });

    if (isDragging) {
      setOffset({
        x: e.clientX - dragStart.x,
        y: e.clientY - dragStart.y,
      });
      return;
    }

    // Hover hit test
    const width = canvas.width;
    const height = canvas.height;
    let found: Galaxy | null = null;
    let closestDist = 20;

    for (const g of galaxies) {
      const { x, y } = projectCoordinates(g.ra, g.dec, width, height, zoom, offset);
      const dist = Math.hypot(mouseX - x, mouseY - y);
      if (dist < closestDist) {
        closestDist = dist;
        found = g;
      }
    }
    setHoveredGalaxy(found);
  };

  const handleMouseUp = () => setIsDragging(false);

  // Wheel Zoom
  const handleWheel = (e: React.WheelEvent<HTMLCanvasElement>) => {
    e.preventDefault();
    const zoomFactor = e.deltaY < 0 ? 1.15 : 0.87;
    const newZoom = Math.max(0.5, Math.min(25.0, zoom * zoomFactor));

    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left - canvas.width / 2;
    const mouseY = e.clientY - rect.top - canvas.height / 2;

    const dx = mouseX - offset.x;
    const dy = mouseY - offset.y;

    const scaleChange = newZoom / zoom;
    setOffset({
      x: mouseX - dx * scaleChange,
      y: mouseY - dy * scaleChange,
    });
    setZoom(newZoom);
  };

  const handleClick = () => {
    if (hoveredGalaxy) {
      onSelectGalaxy(hoveredGalaxy);
    }
  };

  return (
    <div className="relative w-full h-full cursor-crosshair">
      <canvas
        ref={canvasRef}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onWheel={handleWheel}
        onClick={handleClick}
        className="w-full h-full block"
      />

      {/* Hover Galaxy Tooltip */}
      {hoveredGalaxy && (
        <div
          style={{
            left: `${mousePos.x + 16}px`,
            top: `${mousePos.y - 40}px`,
          }}
          className="absolute pointer-events-none z-20 bg-cosmos-900/95 border border-cyan-500/60 rounded-lg px-3 py-2 text-xs shadow-xl backdrop-blur"
        >
          <div className="font-bold text-cyan-300 flex items-center space-x-1.5">
            <span>{hoveredGalaxy.id}</span>
            <span className="text-[10px] text-slate-400 font-normal">
              (z = {hoveredGalaxy.redshift.toFixed(2)})
            </span>
          </div>
          <div className="text-slate-300 text-[11px] mt-0.5 space-x-2">
            <span>log M* = {hoveredGalaxy.log_mstar.toFixed(2)}</span>
            <span>•</span>
            <span>SFR = {hoveredGalaxy.sfr.toFixed(2)} M☉/yr</span>
          </div>
          <div className="text-slate-400 text-[10px] mt-0.5">Click to inspect in Scientific Workspace</div>
        </div>
      )}

      {/* Scientific Colorbar Overlay */}
      <div className="absolute bottom-4 right-4 z-10 flex flex-col items-end space-y-1.5 pointer-events-none">
        {colorMode === 'redshift' && (
          <div className="bg-cosmos-950/90 border border-cosmos-800 rounded-lg p-2 text-[10px] text-slate-300 backdrop-blur shadow-lg">
            <div className="font-semibold text-slate-200 mb-1">Color: Cosmological Redshift (z)</div>
            <div className="w-48 h-2 rounded-full bg-gradient-to-r from-sky-400 via-emerald-400 via-amber-400 to-rose-500" />
            <div className="flex justify-between font-mono text-[9px] text-slate-400 mt-1">
              <span>z = 0.2</span>
              <span>z = 2.0</span>
              <span>z = 5.0</span>
              <span>z = 8.5</span>
            </div>
          </div>
        )}

        {colorMode === 'ssfr' && (
          <div className="bg-cosmos-950/90 border border-cosmos-800 rounded-lg p-2 text-[10px] text-slate-300 backdrop-blur shadow-lg">
            <div className="font-semibold text-slate-200 mb-1">Color: Specific SFR (Bimodality)</div>
            <div className="flex items-center space-x-2 text-[9px] font-mono">
              <span className="flex items-center space-x-1">
                <span className="w-2 h-2 rounded-full bg-blue-400" />
                <span>Star-Forming</span>
              </span>
              <span className="flex items-center space-x-1">
                <span className="w-2 h-2 rounded-full bg-emerald-400" />
                <span>Green Valley</span>
              </span>
              <span className="flex items-center space-x-1">
                <span className="w-2 h-2 rounded-full bg-rose-500" />
                <span>Quiescent</span>
              </span>
            </div>
          </div>
        )}

        {colorMode === 'mass' && (
          <div className="bg-cosmos-950/90 border border-cosmos-800 rounded-lg p-2 text-[10px] text-slate-300 backdrop-blur shadow-lg">
            <div className="font-semibold text-slate-200 mb-1">Color: Stellar Mass (log M*)</div>
            <div className="w-44 h-2 rounded-full bg-gradient-to-r from-indigo-400 via-amber-400 to-yellow-200" />
            <div className="flex justify-between font-mono text-[9px] text-slate-400 mt-1">
              <span>10⁷·⁵ M☉</span>
              <span>10⁹·⁵</span>
              <span>10¹¹·⁵ M☉</span>
            </div>
          </div>
        )}

        {colorMode === 'rgb' && (
          <div className="bg-cosmos-950/80 border border-cosmos-800 rounded-lg px-2.5 py-1 text-[10px] text-slate-400 backdrop-blur">
            <span className="text-rose-400">R: F444W</span> • <span className="text-emerald-400">G: F200W</span> • <span className="text-sky-400">B: F090W</span>
          </div>
        )}

        {/* Navigation Hints */}
        <div className="bg-cosmos-950/80 border border-cosmos-800 rounded-lg px-2.5 py-1 text-[10px] text-slate-400 backdrop-blur">
          <span>Drag to pan • Scroll to zoom ({(zoom).toFixed(1)}×)</span>
        </div>
      </div>
    </div>
  );
};
