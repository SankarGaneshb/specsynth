import React, { useState } from 'react';
import { SedPoint, FilterCurveData } from '../types/galaxy';

interface SedPlotProps {
  sed: SedPoint[];
  filters: FilterCurveData[];
  redshift: number;
  dustAv: number;
  originalAv: number;
}

export const SedPlot: React.FC<SedPlotProps> = ({ sed, filters, redshift, dustAv, originalAv }) => {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  if (!sed || sed.length === 0) {
    return (
      <div className="h-48 flex items-center justify-center text-slate-500 text-xs">
        No SED spectral data available
      </div>
    );
  }

  // Calculate wavelength range from original data
  const minWave = Math.min(...sed.map((p) => p.wave));
  const maxWave = Math.max(...sed.map((p) => p.wave));

  // Compute attenuation relative to the galaxy's intrinsic dust
  // Charlot & Fall (2000): delta_tau = (dustAv - originalAv) / 1.086 * (wave / 5500)^(-0.7)
  const deltaAv = dustAv - originalAv;
  const isModified = Math.abs(deltaAv) > 0.01;

  const modifiedSed = sed.map((p) => {
    const wave = p.wave;
    const deltaTau = (deltaAv / 1.086) * Math.pow(wave / 5500.0, -0.7);
    const atten = Math.exp(-deltaTau);
    return { wave, flux: Math.max(1e-12, p.flux * atten) };
  });

  // CRITICAL FIX: Anchor the Y-axis range to the ORIGINAL baseline SED!
  // This prevents the SVG from auto-scaling away the visual drop in flux.
  const origFluxes = sed.map((p) => p.flux).filter((f) => f > 0);
  const baselineMaxFlux = Math.max(...origFluxes, 1.0);
  const logMaxFlux = Math.log10(baselineMaxFlux * 1.5);
  // Fixed 4.5 decades of dynamic range
  const logMinFlux = logMaxFlux - 4.5;

  // SVG coordinate dimensions
  const svgWidth = 440;
  const svgHeight = 220;
  const padding = { top: 25, right: 20, bottom: 35, left: 52 };

  const plotWidth = svgWidth - padding.left - padding.right;
  const plotHeight = svgHeight - padding.top - padding.bottom;

  // Logarithmic coordinate mapping
  const logMinWave = Math.log10(minWave);
  const logMaxWave = Math.log10(maxWave);

  const getX = (w: number) => {
    const logW = Math.log10(Math.max(w, minWave));
    return padding.left + ((logW - logMinWave) / (logMaxWave - logMinWave)) * plotWidth;
  };

  const getY = (f: number) => {
    const logF = Math.log10(Math.max(f, 10 ** logMinFlux));
    const clampedLogF = Math.max(logMinFlux, Math.min(logMaxFlux, logF));
    return padding.top + plotHeight - ((clampedLogF - logMinFlux) / (logMaxFlux - logMinFlux)) * plotHeight;
  };

  // Path for original baseline SED (dashed reference)
  const origPathD = sed.reduce((acc, p, idx) => {
    const x = getX(p.wave);
    const y = getY(p.flux);
    return idx === 0 ? `M ${x} ${y}` : `${acc} L ${x} ${y}`;
  }, '');

  // Path for modified/attenuated SED curve
  const pathD = modifiedSed.reduce((acc, p, idx) => {
    const x = getX(p.wave);
    const y = getY(p.flux);
    return idx === 0 ? `M ${x} ${y}` : `${acc} L ${x} ${y}`;
  }, '');

  // Calculate UV attenuation percentage for live status badge
  const uvSampleIdx = Math.floor(sed.length * 0.1);
  const origUv = sed[uvSampleIdx]?.flux || 1;
  const modUv = modifiedSed[uvSampleIdx]?.flux || 1;
  const uvDropPct = Math.round((1 - modUv / origUv) * 100);

  // Filter band colors
  const filterColors: Record<string, string> = {
    jwst_f090w: '#38bdf8', // Light Blue
    jwst_f150w: '#34d399', // Emerald
    jwst_f200w: '#facc15', // Gold
    jwst_f277w: '#fb923c', // Orange
    jwst_f356w: '#f87171', // Red
    jwst_f444w: '#e879f9', // Pink
  };

  // Y-axis tick values
  const yTicks = [];
  const topExp = Math.floor(logMaxFlux);
  for (let exp = topExp; exp >= topExp - 4; exp--) {
    yTicks.push({ val: 10 ** exp, label: `10^${exp}`, y: getY(10 ** exp) });
  }

  return (
    <div className="relative w-full bg-cosmos-950/80 rounded-xl border border-cosmos-800 p-3 select-none">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center space-x-2">
          <span className="text-xs font-semibold text-slate-200">Rest-Frame SED & Filter Bandpasses</span>
          {isModified && (
            <span
              className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${
                deltaAv > 0
                  ? 'bg-rose-950/80 text-rose-300 border border-rose-800/60'
                  : 'bg-cyan-950/80 text-cyan-300 border border-cyan-800/60'
              }`}
            >
              {deltaAv > 0 ? `ΔAv = +${deltaAv.toFixed(2)} (${uvDropPct}% UV absorbed)` : `ΔAv = ${deltaAv.toFixed(2)}`}
            </span>
          )}
        </div>
        <span className="text-[10px] text-slate-400 font-mono">λ_rest ∈ [10³ - 5×10⁴ Å]</span>
      </div>

      <svg viewBox={`0 0 ${svgWidth} ${svgHeight}`} className="w-full h-auto overflow-visible">
        {/* Y-axis Grid Lines and Labels */}
        {yTicks.map((t, idx) => (
          <g key={idx}>
            <line
              x1={padding.left}
              y1={t.y}
              x2={padding.left + plotWidth}
              y2={t.y}
              stroke="#1e293b"
              strokeDasharray="2,2"
            />
            <text
              x={padding.left - 6}
              y={t.y + 3}
              fill="#64748b"
              fontSize="8"
              textAnchor="end"
              fontFamily="monospace"
            >
              {t.label}
            </text>
          </g>
        ))}

        {/* X-axis Grid lines */}
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

        {/* Original Baseline Curve (if modified, show as gray dashed reference) */}
        {isModified && (
          <path
            d={origPathD}
            fill="none"
            stroke="#94a3b8"
            strokeWidth={1.5}
            strokeDasharray="3,3"
            strokeOpacity={0.6}
          />
        )}

        {/* Glowing Active SED Curve */}
        <path d={pathD} fill="none" stroke="#6366f1" strokeWidth={3} strokeOpacity={0.25} />
        <path
          d={pathD}
          fill="none"
          stroke={isModified ? (deltaAv > 0 ? '#fb7185' : '#38bdf8') : '#818cf8'}
          strokeWidth={2}
        />

        {/* Hover Crosshair Dot */}
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
          L_λ (L☉/Å)
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

      {/* Legend & Hover Status Readout */}
      <div className="mt-1 flex items-center justify-between text-[11px] text-slate-300 font-mono bg-cosmos-900/90 rounded px-2.5 py-1 border border-cosmos-800">
        <div className="flex items-center space-x-3 text-[10px]">
          {isModified && (
            <div className="flex items-center space-x-1 text-slate-400">
              <span className="inline-block w-3 h-0.5 border-t border-dashed border-slate-400" />
              <span>Original (Av={originalAv.toFixed(2)})</span>
            </div>
          )}
          <div className="flex items-center space-x-1">
            <span
              className={`inline-block w-3 h-0.5 ${
                isModified ? (deltaAv > 0 ? 'bg-rose-400' : 'bg-sky-400') : 'bg-indigo-400'
              }`}
            />
            <span className={isModified ? (deltaAv > 0 ? 'text-rose-300' : 'text-sky-300') : 'text-indigo-300'}>
              {isModified ? `Attenuated (Av=${dustAv.toFixed(2)})` : `Intrinsic (Av=${dustAv.toFixed(2)})`}
            </span>
          </div>
        </div>

        {hoverIndex !== null && modifiedSed[hoverIndex] && (
          <div className="text-[10px] text-amber-300">
            λ = {modifiedSed[hoverIndex].wave.toFixed(0)}Å • L_λ = {modifiedSed[hoverIndex].flux.toExponential(2)}
          </div>
        )}
      </div>
    </div>
  );
};
