import React, { useRef, useEffect, useState, useCallback } from 'react';
import { Galaxy } from '../types/galaxy';

interface SkyCanvasProps {
  galaxies: Galaxy[];
  selectedGalaxy: Galaxy | null;
  onSelectGalaxy: (galaxy: Galaxy) => void;
  centerRa: number;
  centerDec: number;
  fieldRadius: number;
  resetTrigger: number;
}

export const SkyCanvas: React.FC<SkyCanvasProps> = ({
  galaxies,
  selectedGalaxy,
  onSelectGalaxy,
  centerRa,
  centerDec,
  fieldRadius,
  resetTrigger,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  // Viewport transform state
  const [zoom, setZoom] = useState<number>(1.0);
  const [offset, setOffset] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [dragStart, setDragStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [hoveredGalaxy, setHoveredGalaxy] = useState<Galaxy | null>(null);
  const [mousePos, setMousePos] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

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

  // Compute color from fluxes (RGB composite from NIRCam F444W, F200W, F090W)
  const getGalaxyColor = useCallback((g: Galaxy) => {
    const rFlux = g.fluxes['jwst_f444w'] || 1e-32;
    const gFlux = g.fluxes['jwst_f200w'] || 1e-32;
    const bFlux = g.fluxes['jwst_f090w'] || 1e-32;

    const maxFlux = Math.max(rFlux, gFlux, bFlux);
    if (maxFlux <= 0) return 'rgba(200, 220, 255, 0.8)';

    // Normalizing with gentle power-law curve to emphasize color differences
    const r = Math.min(255, Math.floor(255 * Math.pow(rFlux / maxFlux, 0.4)));
    const gCol = Math.min(255, Math.floor(255 * Math.pow(gFlux / maxFlux, 0.4)));
    const b = Math.min(255, Math.floor(255 * Math.pow(bFlux / maxFlux, 0.4)));

    // Ensure galaxies don't look completely dim
    const boost = Math.max(r, gCol, b);
    const minLum = 180;
    const factor = boost > 0 && boost < minLum ? minLum / boost : 1;

    return `rgb(${Math.min(255, Math.floor(r * factor))}, ${Math.min(255, Math.floor(gCol * factor))}, ${Math.min(255, Math.floor(b * factor))})`;
  }, []);

  // Main Render Loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animId: number;

    const render = () => {
      const width = canvas.width;
      const height = canvas.height;

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

        // Viewport culling
        if (x < -20 || x > width + 20 || y < -20 || y > height + 20) continue;

        // Radius based on stellar mass and zoom
        const isSelected = selectedGalaxy?.id === g.id;
        const isHovered = hoveredGalaxy?.id === g.id;

        const baseRadius = Math.max(1.8, Math.min(8.5, (g.log_mstar - 6.5) * 1.6));
        const currentRadius = baseRadius * Math.pow(zoom, 0.35);
        const color = getGalaxyColor(g);

        // Glow halo
        const haloGrad = ctx.createRadialGradient(x, y, 0, x, y, currentRadius * 3.5);
        haloGrad.addColorStop(0, color.replace('rgb', 'rgba').replace(')', ', 0.9)'));
        haloGrad.addColorStop(0.4, color.replace('rgb', 'rgba').replace(')', ', 0.35)'));
        haloGrad.addColorStop(1, 'rgba(0, 0, 0, 0)');

        ctx.fillStyle = haloGrad;
        ctx.beginPath();
        ctx.arc(x, y, currentRadius * 3.5, 0, Math.PI * 2);
        ctx.fill();

        // Core dot
        ctx.fillStyle = '#ffffff';
        ctx.beginPath();
        ctx.arc(x, y, currentRadius * 0.75, 0, Math.PI * 2);
        ctx.fill();

        // Selected Galaxy Reticle
        if (isSelected) {
          ctx.strokeStyle = '#f59e0b';
          ctx.lineWidth = 2;
          ctx.beginPath();
          ctx.arc(x, y, currentRadius * 4 + 4, 0, Math.PI * 2);
          ctx.stroke();

          // Reticle tick crosshairs
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
      const scaleBarArcmin = 1.0; // 1 arcminute
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
    getGalaxyColor,
  ]);

  // Window Resize Listener
  useEffect(() => {
    const handleResize = () => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      canvas.width = canvas.parentElement?.clientWidth || window.innerWidth;
      canvas.height = canvas.parentElement?.clientHeight || window.innerHeight;
    };
    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Mouse Drag / Pan Handlers
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
    let closestDist = 20; // 20px hit tolerance

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

  // Wheel Zoom Handler
  const handleWheel = (e: React.WheelEvent<HTMLCanvasElement>) => {
    e.preventDefault();
    const zoomFactor = e.deltaY < 0 ? 1.15 : 0.87;
    const newZoom = Math.max(0.5, Math.min(25.0, zoom * zoomFactor));

    // Zoom centered on cursor position
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

  // Click Selection Handler
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
          <div className="text-slate-400 text-[10px] mt-0.5">Click to inspect in PSI Explorer</div>
        </div>
      )}

      {/* On-screen Navigation Hints */}
      <div className="absolute bottom-4 right-4 bg-cosmos-950/80 border border-cosmos-800 rounded-lg px-3 py-1.5 text-[11px] text-slate-400 pointer-events-none backdrop-blur">
        <span>Drag to pan • Scroll to zoom ({(zoom).toFixed(1)}×)</span>
      </div>
    </div>
  );
};
