import React, { useState, useMemo } from 'react';
import { SedPoint, FilterCurveData } from '../types/galaxy';
import {
  forwardModelGalaxy,
  luminosityDistanceCm,
  madauIgmTransmission,
  charlotFallAttenuation,
} from '../utils/physics';

interface SedPlotProps {
  sed: SedPoint[];
  filters: FilterCurveData[];
  redshift: number;
  originalZ: number;
  dustAv: number;
  originalAv: number;
}

export type SedViewMode = 'rest' | 'observed';

export const SedPlot: React.FC<SedPlotProps> = ({
  sed,
  filters,
  redshift,
  originalZ,
  dustAv,
  originalAv,
}) => {
  const [viewMode, setViewMode] = useState<SedViewMode>('rest');
  const [showBreakMarkers, setShowBreakMarkers] = useState<boolean>(true);
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  if (!sed || sed.length === 0) {
    return (
      <div className="h-48 flex items-center justify-center text-slate-500 text-xs">
        No SED spectral data available
      </div>
    );
  }

  // Parameter modification diffs
  const deltaAv = dustAv - originalAv;
  const isDustModified = Math.abs(deltaAv) > 0.01;
  const deltaZ = redshift - originalZ;
  const isZModified = Math.abs(deltaZ) > 0.01;

  // Compute forward-modeled active and baseline spectra using physical engine
  const activeModel = useMemo(() => {
    return forwardModelGalaxy(sed, originalZ, redshift, originalAv, dustAv, filters);
  }, [sed, originalZ, redshift, originalAv, dustAv, filters]);

  const baselineModel = useMemo(() => {
    return forwardModelGalaxy(sed, originalZ, originalZ, originalAv, originalAv, filters);
  }, [sed, originalZ, originalAv, filters]);

  // Active curves depending on viewMode
  const activeCurve = viewMode === 'rest' ? activeModel.sedRestModified : activeModel.sedObs;
  const baselineCurve = viewMode === 'rest' ? sed : baselineModel.sedObs;

  // Wavelength ranges
  const minWave = Math.min(...activeCurve.map((p) => p.wave));
  const maxWave = Math.max(...activeCurve.map((p) => p.wave));

  // Adaptive Y-axis bounds based on actual continuum range (covering ~2.5 decades)
  const positiveFluxes = activeCurve.map((p) => p.flux).filter((f) => f > 0 && isFinite(f));
  const maxFlux = Math.max(...positiveFluxes, 1e-35);
  // Continuum 90th percentile to anchor the top of the axis
  const sortedFluxes = [...positiveFluxes].sort((a, b) => a - b);
  const p95Flux = sortedFluxes[Math.floor(sortedFluxes.length * 0.95)] || maxFlux;
  const logMaxFlux = Math.log10(p95Flux * 2.0);
  const logMinFlux = logMaxFlux - 2.8; // 2.8 decades window provides ideal visibility of breaks

  // SVG dimensions
  const svgWidth = 440;
  const svgHeight = 240;
  const padding = { top: 26, right: 18, bottom: 40, left: 60 };

  const plotWidth = svgWidth - padding.left - padding.right;
  const plotHeight = svgHeight - padding.top - padding.bottom;

  // Logarithmic coordinate mapping
  const logMinWave = Math.log10(Math.max(10, minWave));
  const logMaxWave = Math.log10(Math.max(100, maxWave));

  const getX = (w: number) => {
    const logW = Math.log10(Math.max(w, minWave));
    return padding.left + ((logW - logMinWave) / (logMaxWave - logMinWave)) * plotWidth;
  };

  const getY = (f: number) => {
    const logF = Math.log10(Math.max(f, 10 ** (logMinFlux - 2)));
    const clampedLogF = Math.max(logMinFlux, Math.min(logMaxFlux, logF));
    return padding.top + plotHeight - ((clampedLogF - logMinFlux) / (logMaxFlux - logMinFlux)) * plotHeight;
  };

  // Paths
  const activePathD = activeCurve.reduce((acc, p, idx) => {
    const x = getX(p.wave);
    const y = getY(p.flux);
    return idx === 0 ? `M ${x} ${y}` : `${acc} L ${x} ${y}`;
  }, '');

  const baselinePathD = baselineCurve.reduce((acc, p, idx) => {
    const x = getX(p.wave);
    const y = getY(p.flux);
    return idx === 0 ? `M ${x} ${y}` : `${acc} L ${x} ${y}`;
  }, '');

  // Filter band colors
  const filterColors: Record<string, string> = {
    jwst_f090w: '#38bdf8',
    jwst_f150w: '#34d399',
    jwst_f200w: '#facc15',
    jwst_f277w: '#fb923c',
    jwst_f356w: '#f87171',
    jwst_f444w: '#e879f9',
  };

  // Y-axis tick values (3-4 nice decades)
  const yTicks = [];
  const topExp = Math.floor(logMaxFlux);
  for (let exp = topExp; exp >= topExp - 3; exp--) {
    yTicks.push({
      val: 10 ** exp,
      label: `10^${exp}`,
      y: getY(10 ** exp),
    });
  }

  // Astrophysical Spectral Break Markers
  // (Lyman limit 912 Å, Ly-alpha 1216 Å, Balmer 3646 Å, Dn4000 4000 Å, H-alpha 6563 Å)
  const restBreaks = [
    { name: 'Ly-limit', wave: 911.75, color: '#ec4899', desc: 'Lyman Limit (912 Å)' },
    { name: 'Lyα', wave: 1215.67, color: '#f43f5e', desc: 'Lyman-alpha (1216 Å)' },
    { name: 'Balmer', wave: 3646.0, color: '#06b6d4', desc: 'Balmer Break (3646 Å)' },
    { name: 'Dn4000', wave: 4000.0, color: '#10b981', desc: 'Dn4000 Break (4000 Å)' },
    { name: 'Hα', wave: 6562.8, color: '#eab308', desc: 'H-alpha (6563 Å)' },
  ];

  const zFactor = viewMode === 'observed' ? 1.0 + redshift : 1.0;
  const activeBreaks = restBreaks
    .map((b) => ({
      ...b,
      evalWave: b.wave * zFactor,
    }))
    .filter((b) => b.evalWave >= minWave && b.evalWave <= maxWave);

  // Wavelength ticks
  const waveTicks = viewMode === 'rest'
    ? [1000, 2000, 4000, 10000, 25000, 60000]
    : [3000, 7000, 15000, 30000, 60000, 150000];

  return (
    <div className="relative w-full bg-cosmos-950/80 rounded-xl border border-cosmos-800 p-3 select-none shadow-md">
      {/* Header with Title and 1-Click Frame & Unit Toggle */}
      <div className="mb-2.5">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <span className="text-sm font-bold text-slate-100">
              {viewMode === 'rest' ? 'Rest-Frame Luminosity SED' : 'Observed-Frame Flux Density'}
            </span>
            <span className="text-xs text-indigo-300 font-mono bg-indigo-950/60 px-2 py-0.5 rounded border border-indigo-800/60">
              FSPS MIST
            </span>
          </div>

          {/* Unit / Frame Switcher Toggle */}
          <div className="flex items-center space-x-1.5 bg-cosmos-900 p-0.5 rounded-lg border border-cosmos-700/80">
            <button
              onClick={() => setViewMode('rest')}
              className={`px-2 py-0.5 text-xs font-mono font-bold rounded transition-all ${
                viewMode === 'rest'
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Rest (L_λ)
            </button>
            <button
              onClick={() => setViewMode('observed')}
              className={`px-2 py-0.5 text-xs font-mono font-bold rounded transition-all ${
                viewMode === 'observed'
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Obs (F_λ)
            </button>
          </div>
        </div>

        {/* Subheader Badges & Break Toggle */}
        <div className="flex flex-wrap items-center justify-between mt-1 text-xs text-slate-400">
          <div className="flex items-center space-x-2">
            <span className="font-mono text-slate-300">
              {viewMode === 'rest'
                ? 'Units: L_λ [L☉ / Å] at source'
                : 'Units: F_λ [erg s⁻¹ cm⁻² Å⁻¹] at Earth (D_L + IGM)'}
            </span>
          </div>

          <label className="flex items-center space-x-1.5 cursor-pointer text-xs hover:text-slate-200">
            <input
              type="checkbox"
              checked={showBreakMarkers}
              onChange={(e) => setShowBreakMarkers(e.target.checked)}
              className="rounded bg-cosmos-900 border-cosmos-700 text-indigo-500 focus:ring-0 w-3 h-3 cursor-pointer"
            />
            <span className="font-mono">Break Markers</span>
          </label>
        </div>

        {/* Dedicated Diff Badges Bar */}
        {(isZModified || isDustModified) && (
          <div className="flex flex-wrap items-center gap-2 mt-2 pt-2 border-t border-cosmos-800/60">
            {isZModified && (
              <span className="text-xs font-mono px-2 py-0.5 rounded bg-amber-950/80 text-amber-300 border border-amber-800/60 flex items-center space-x-1">
                <span className="font-bold">Δz = {deltaZ > 0 ? `+${deltaZ.toFixed(2)}` : deltaZ.toFixed(2)}</span>
                <span className="text-amber-400/80">({originalZ.toFixed(2)} → {redshift.toFixed(2)})</span>
              </span>
            )}
            {isDustModified && (
              <span
                className={`text-xs font-mono px-2 py-0.5 rounded flex items-center space-x-1 ${
                  deltaAv > 0
                    ? 'bg-rose-950/80 text-rose-300 border border-rose-800/60'
                    : 'bg-cyan-950/80 text-cyan-300 border border-cyan-800/60'
                }`}
              >
                <span className="font-bold">ΔAv = {deltaAv > 0 ? `+${deltaAv.toFixed(2)}` : deltaAv.toFixed(2)} mag</span>
                <span>(Charlot & Fall)</span>
              </span>
            )}
          </div>
        )}
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
              y={t.y + 3.5}
              fill="#94a3b8"
              fontSize="9.5"
              textAnchor="end"
              fontFamily="monospace"
              fontWeight="500"
            >
              {t.label}
            </text>
          </g>
        ))}

        {/* X-axis Grid lines */}
        {waveTicks.map((w) => {
          if (w < minWave || w > maxWave) return null;
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
              <text
                x={x}
                y={svgHeight - 16}
                fill="#94a3b8"
                fontSize="9.5"
                textAnchor="middle"
                fontFamily="monospace"
                fontWeight="500"
              >
                {w < 10000 ? `${w}Å` : `${(w / 10000).toFixed(1)}µm`}
              </text>
            </g>
          );
        })}

        {/* Astrophysical Spectral Break Markers */}
        {showBreakMarkers &&
          activeBreaks.map((b) => {
            const bx = getX(b.evalWave);
            return (
              <g key={`break-${b.name}`}>
                <line
                  x1={bx}
                  y1={padding.top}
                  x2={bx}
                  y2={padding.top + plotHeight}
                  stroke={b.color}
                  strokeWidth={1}
                  strokeOpacity={0.7}
                  strokeDasharray="2,3"
                />
                <text
                  x={bx}
                  y={padding.top - 5}
                  fill={b.color}
                  fontSize="7.5"
                  fontFamily="monospace"
                  fontWeight="bold"
                  textAnchor="middle"
                >
                  {b.name}
                </text>
              </g>
            );
          })}

        {/* Filter Bandpass Overlays */}
        {filters.map((flt) => {
          const evalWave = viewMode === 'rest'
            ? flt.pivot_wavelength / (1.0 + redshift)
            : flt.pivot_wavelength;

          if (evalWave < minWave || evalWave > maxWave) return null;
          const fColor = filterColors[flt.name] || '#6366f1';
          const restX = getX(evalWave);

          return (
            <g key={flt.name}>
              <line
                x1={restX}
                y1={padding.top + 10}
                x2={restX}
                y2={padding.top + plotHeight}
                stroke={fColor}
                strokeWidth={1.2}
                strokeOpacity={0.5}
                strokeDasharray="3,3"
              />
              <text
                x={restX}
                y={padding.top + 7}
                fill={fColor}
                fontSize="7.5"
                fontFamily="monospace"
                textAnchor="middle"
                fontWeight="bold"
              >
                {flt.name.replace('jwst_', '').toUpperCase()}
              </text>
            </g>
          );
        })}

        {/* Baseline Reference Curve (when dust or z modified) */}
        {(isDustModified || isZModified) && (
          <path
            d={baselinePathD}
            fill="none"
            stroke="#64748b"
            strokeWidth={1.5}
            strokeDasharray="3,3"
            strokeOpacity={0.6}
          />
        )}

        {/* Glowing Active SED Curve */}
        <path d={activePathD} fill="none" stroke="#6366f1" strokeWidth={3} strokeOpacity={0.25} />
        <path
          d={activePathD}
          fill="none"
          stroke={isDustModified ? (deltaAv > 0 ? '#fb7185' : '#38bdf8') : '#818cf8'}
          strokeWidth={2}
        />

        {/* Hover Crosshair Dot */}
        {hoverIndex !== null && activeCurve[hoverIndex] && (
          <g>
            <circle
              cx={getX(activeCurve[hoverIndex].wave)}
              cy={getY(activeCurve[hoverIndex].flux)}
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
            activeCurve.forEach((p, idx) => {
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
          fill="#94a3b8"
          fontSize="10"
          fontWeight="bold"
          textAnchor="middle"
          transform={`rotate(-90, 14, ${padding.top + plotHeight / 2})`}
        >
          {viewMode === 'rest' ? 'L_λ (L☉ / Å)' : 'F_λ (erg s⁻¹ cm⁻² Å⁻¹)'}
        </text>

        {/* X-axis label */}
        <text
          x={padding.left + plotWidth / 2}
          y={svgHeight - 2}
          fill="#94a3b8"
          fontSize="10"
          fontWeight="bold"
          textAnchor="middle"
        >
          {viewMode === 'rest' ? 'Rest Wavelength λ_rest (Å)' : 'Observed Wavelength λ_obs (Å)'}
        </text>
      </svg>

      {/* Legend & Hover Status Readout */}
      <div className="mt-1 flex items-center justify-between text-xs text-slate-200 font-mono bg-cosmos-900/90 rounded px-3 py-1.5 border border-cosmos-800 shadow-sm">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
          {(isDustModified || isZModified) && (
            <div className="flex items-center space-x-1 text-slate-400">
              <span className="inline-block w-3 h-0.5 border-t border-dashed border-slate-400" />
              <span>Baseline (z={originalZ.toFixed(2)}, Av={originalAv.toFixed(2)})</span>
            </div>
          )}
          <div className="flex items-center space-x-1.5 font-semibold">
            <span
              className={`inline-block w-3 h-1 rounded ${
                isDustModified ? (deltaAv > 0 ? 'bg-rose-400' : 'bg-sky-400') : 'bg-indigo-400'
              }`}
            />
            <span className={isDustModified ? (deltaAv > 0 ? 'text-rose-300' : 'text-sky-300') : 'text-indigo-300'}>
              Active Model (z={redshift.toFixed(2)}, Av={dustAv.toFixed(2)})
            </span>
          </div>
        </div>

        {hoverIndex !== null && activeCurve[hoverIndex] && (
          <div className="text-xs font-bold text-amber-300 flex-shrink-0 ml-2">
            λ = {activeCurve[hoverIndex].wave.toFixed(0)}Å •{' '}
            {viewMode === 'rest' ? 'L_λ = ' : 'F_λ = '}
            {activeCurve[hoverIndex].flux.toExponential(2)}
          </div>
        )}
      </div>
    </div>
  );
};
