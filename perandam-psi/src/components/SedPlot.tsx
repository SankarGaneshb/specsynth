import React, { useState } from 'react';
import { SedPoint, FilterCurveData } from '../types/galaxy';

interface SedPlotProps {
  sed: SedPoint[];
  filters: FilterCurveData[];
  redshift: number;
  dustAv: number;
}

export const SedPlot: React.FC<SedPlotProps> = ({ sed, filters, redshift, dustAv }) => {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  if (!sed || sed.length === 0) {
    return (
      <div className="h-48 flex items-center justify-center text-slate-500 text-xs">
        No SED spectral data available
      </div>
    );
  }

  // Calculate wavelength and flux ranges
  const minWave = Math.min(...sed.map((p) => p.wave));
  const maxWave = Math.max(...sed.map((p) => p.wave));

  // Attenuate the SED dynamically if user moved dust slider Av
  // Charlot & Fall (2000): tau_diffuse = Av / 1.086 * (wave / 5500)^(-0.7)
  const modifiedSed = sed.map((p) => {
    const wave = p.wave;
    const tau = (dustAv / 1.086) * Math.pow(wave / 5500.0, -0.7);
    const atten = Math.exp(-Math.max(0, tau));
    return { wave, flux: p.flux * atten };
  });

  const fluxes = modifiedSed.map((p) => p.flux).filter((f) => f > 0);
  const minFlux = Math.min(...fluxes, 1e-6);
  const maxFlux = Math.max(...fluxes, 1.0);

  // SVG coordinate dimensions
  const svgWidth = 440;
  const svgHeight = 220;
  const padding = { top: 20, right: 20, bottom: 35, left: 45 };

  const plotWidth = svgWidth - padding.left - padding.right;
  const plotHeight = svgHeight - padding.top - padding.bottom;

  // Logarithmic coordinate mapping
  const logMinWave = Math.log10(minWave);
  const logMaxWave = Math.log10(maxWave);
  const logMinFlux = Math.log10(Math.max(minFlux, maxFlux * 1e-4));
  const logMaxFlux = Math.log10(maxFlux * 1.3);

  const getX = (w: number) => {
    const logW = Math.log10(Math.max(w, minWave));
    return padding.left + ((logW - logMinWave) / (logMaxWave - logMinWave)) * plotWidth;
  };

  const getY = (f: number) => {
    const logF = Math.log10(Math.max(f, 10 ** logMinFlux));
    return padding.top + plotHeight - ((logF - logMinFlux) / (logMaxFlux - logMinFlux)) * plotHeight;
  };

  // Build path string for SED curve
  const pathD = modifiedSed.reduce((acc, p, idx) => {
    const x = getX(p.wave);
    const y = getY(p.flux);
    return idx === 0 ? `M ${x} ${y}` : `${acc} L ${x} ${y}`;
  }, '');

  // Filter band colors
  const filterColors: Record<string, string> = {
    jwst_f090w: '#38bdf8', // Light Blue
    jwst_f150w: '#34d399', // Emerald
    jwst_f200w: '#facc15', // Gold
    jwst_f277w: '#fb923c', // Orange
    jwst_f356w: '#f87171', // Red
    jwst_f444w: '#e879f9', // Pink
  };

  // Rest-frame markers
  const markers = [
    { name: 'Ly-α', wave: 1216, color: '#06b6d4' },
    { name: 'Balmer', wave: 3646, color: '#f59e0b' },
    { name: '4000Å', wave: 4000, color: '#a855f7' },
    { name: 'H-α', wave: 6563, color: '#ef4444' },
  ];

  return (
    <div className="relative w-full bg-cosmos-950/80 rounded-xl border border-cosmos-800 p-3 select-none">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-semibold text-slate-300">Rest-Frame SED & Filter Bandpasses</span>
        <span className="text-[10px] text-slate-400 font-mono">λ_rest ∈ [10³ - 5×10⁴ Å]</span>
      </div>

      <svg viewBox={`0 0 ${svgWidth} ${svgHeight}`} className="w-full h-auto overflow-visible">
        {/* Plot Grid lines */}
        {[1500, 4000, 10000, 25000].map((w) => {
          const x = getX(w);
          return (
            <g key={w}>
              <line
                x1={x}
                y1={padding.top}
                x2={x}
                y2={padding.top + plotHeight}
                stroke="#1e293b"
                strokeDasharray="2,2"
              />
              <text x={x} y={svgHeight - 12} fill="#64748b" fontSize="9" textAnchor="middle" fontFamily="monospace">
                {w < 10000 ? `${w}Å` : `${w / 10000}µm`}
              </text>
            </g>
          );
        })}

        {/* Filter Bandpass Overlays (Shifted to Rest-Frame: λ_obs / (1 + z)) */}
        {filters.map((flt) => {
          const restCenter = flt.pivot_wavelength / (1.0 + redshift);
          if (restCenter < minWave || restCenter > maxWave) return null;

          const fColor = filterColors[flt.name] || '#6366f1';
          const restX = getX(restCenter);

          return (
            <g key={flt.name}>
              {/* Filter pivot center line */}
              <line
                x1={restX}
                y1={padding.top}
                x2={restX}
                y2={padding.top + plotHeight}
                stroke={fColor}
                strokeWidth={1}
                strokeOpacity={0.4}
                strokeDasharray="3,3"
              />
              <text
                x={restX}
                y={padding.top - 6}
                fill={fColor}
                fontSize="8"
                textAnchor="middle"
                fontWeight="bold"
              >
                {flt.name.replace('jwst_', '').toUpperCase()}
              </text>
            </g>
          );
        })}

        {/* Physical Spectral Markers */}
        {markers.map((m) => {
          if (m.wave < minWave || m.wave > maxWave) return null;
          const x = getX(m.wave);
          return (
            <line
              key={m.name}
              x1={x}
              y1={padding.top + plotHeight - 15}
              x2={x}
              y2={padding.top + plotHeight}
              stroke={m.color}
              strokeWidth={1.5}
            />
          );
        })}

        {/* Glowing SED Curve */}
        <path d={pathD} fill="none" stroke="#6366f1" strokeWidth={3} strokeOpacity={0.25} />
        <path d={pathD} fill="none" stroke="#818cf8" strokeWidth={1.8} />

        {/* Hover Crosshair */}
        {hoverIndex !== null && modifiedSed[hoverIndex] && (
          <g>
            <circle
              cx={getX(modifiedSed[hoverIndex].wave)}
              cy={getY(modifiedSed[hoverIndex].flux)}
              r={4}
              fill="#f59e0b"
              stroke="#ffffff"
              strokeWidth={1.5}
            />
          </g>
        )}

        {/* Transparent mouse hit-test rect */}
        <rect
          x={padding.left}
          y={padding.top}
          width={plotWidth}
          height={plotHeight}
          fill="transparent"
          onMouseMove={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            const relX = ((e.clientX - rect.left) / rect.width) * plotWidth + padding.left;
            // Find closest SED sample
            let closest = 0;
            let minDist = Infinity;
            modifiedSed.forEach((p, idx) => {
              const dist = Math.abs(getX(p.wave) - relX);
              if (dist < minDist) {
                minDist = dist;
                closest = idx;
              }
            });
            setHoverIndex(closest);
          }}
          onMouseLeave={() => setHoverIndex(null)}
          className="cursor-crosshair"
        />

        {/* Y-axis label */}
        <text
          x={14}
          y={padding.top + plotHeight / 2}
          fill="#64748b"
          fontSize="9"
          textAnchor="middle"
          transform={`rotate(-90, 14, ${padding.top + plotHeight / 2})`}
        >
          log L_λ (L☉/Å)
        </text>

        {/* X-axis label */}
        <text
          x={padding.left + plotWidth / 2}
          y={svgHeight - 2}
          fill="#64748b"
          fontSize="9"
          textAnchor="middle"
        >
          Rest Wavelength λ_rest (Å)
        </text>
      </svg>

      {/* Hover Status Readout */}
      {hoverIndex !== null && modifiedSed[hoverIndex] && (
        <div className="mt-1 flex items-center justify-between text-[11px] text-slate-300 font-mono bg-cosmos-900/90 rounded px-2 py-0.5 border border-cosmos-800">
          <span>λ = {modifiedSed[hoverIndex].wave.toFixed(1)} Å</span>
          <span>L_λ = {modifiedSed[hoverIndex].flux.toExponential(3)}</span>
        </div>
      )}
    </div>
  );
};
