import React, { useState } from 'react';
import { FilterCurveData } from '../types/galaxy';
import { fLambdaToFNu, NIRCAM_5SIGMA_LIMITS } from '../utils/physics';
import { Info, ShieldCheck, AlertCircle } from 'lucide-react';

interface PhotometryBarProps {
  mags: Record<string, number>;
  fluxes?: Record<string, number>;
  magErrs?: Record<string, number>;
  snr?: Record<string, number>;
  filters?: FilterCurveData[];
}

export const PhotometryBar: React.FC<PhotometryBarProps> = ({
  mags,
  fluxes = {},
  magErrs = {},
  snr = {},
  filters = [],
}) => {
  const [activeTooltip, setActiveTooltip] = useState<string | null>(null);

  const bands = [
    { key: 'jwst_f090w', name: 'F090W', pivot: 8990.5, color: 'bg-sky-400', barColor: '#38bdf8' },
    { key: 'jwst_f150w', name: 'F150W', pivot: 14979.3, color: 'bg-emerald-400', barColor: '#34d399' },
    { key: 'jwst_f200w', name: 'F200W', pivot: 19831.2, color: 'bg-amber-400', barColor: '#facc15' },
    { key: 'jwst_f277w', name: 'F277W', pivot: 27545.3, color: 'bg-orange-400', barColor: '#fb923c' },
    { key: 'jwst_f356w', name: 'F356W', pivot: 35602.0, color: 'bg-rose-400', barColor: '#f87171' },
    { key: 'jwst_f444w', name: 'F444W', pivot: 43971.3, color: 'bg-fuchsia-400', barColor: '#e879f9' },
  ];

  // In astronomical magnitudes, lower number = brighter
  const validMags = Object.values(mags).filter((m) => m > 10 && m < 50);
  const minMag = validMags.length > 0 ? Math.min(...validMags) : 20;
  const maxMag = validMags.length > 0 ? Math.max(...validMags) : 30;

  return (
    <div className="bg-cosmos-950/80 rounded-xl border border-cosmos-800 p-3.5 select-none shadow-md">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center space-x-2">
          <span className="text-sm font-bold text-slate-100">Synthetic JWST NIRCam Photometry</span>
          <span className="text-xs text-slate-400 font-mono bg-cosmos-900/90 px-2 py-0.5 rounded border border-cosmos-800">
            10 ks ETC Noise Model
          </span>
        </div>
        <span className="text-xs font-mono text-indigo-400">STScI Module A+B</span>
      </div>

      <div className="text-xs text-slate-400 mb-3 flex items-center justify-between border-b border-cosmos-800/60 pb-1.5 font-mono">
        <span>Bandpass</span>
        <div className="flex items-center space-x-4">
          <span>f_ν (μJy)</span>
          <span className="w-24 text-right">AB Mag (±1σ)</span>
          <span className="w-16 text-center">Status</span>
        </div>
      </div>

      <div className="space-y-2.5">
        {bands.map((b) => {
          const mag = mags[b.key] ?? 99.0;
          const fLam = fluxes[b.key] ?? 0.0;
          const err = magErrs[b.key] ?? 0.0;
          const s_n = snr[b.key] ?? 0.0;

          // Convert to f_nu in uJy
          const fNu = fLam > 0 ? fLambdaToFNu(fLam, b.pivot) : 0;
          const uJy = fNu * 1e29;

          // Detection categorization
          const isDetected = mag < 50 && mag > 0;
          const isSecure = s_n >= 5.0;
          const isMarginal = s_n >= 3.0 && s_n < 5.0;

          // Width based on brightness: brighter (lower mag) = wider bar
          const pct = isDetected
            ? Math.max(10, Math.min(100, ((maxMag - mag) / (maxMag - minMag + 0.1)) * 85 + 15))
            : 5;

          const fltMeta = filters.find((f) => f.name === b.key);

          return (
            <div key={b.key} className="relative group">
              <div className="flex items-center space-x-2 text-xs">
                {/* Filter Name & Info Tooltip Trigger */}
                <div className="w-28 flex items-center space-x-1.5">
                  <button
                    onClick={() => setActiveTooltip(activeTooltip === b.key ? null : b.key)}
                    className="text-slate-300 font-mono font-medium hover:text-amber-300 flex items-center space-x-1"
                    title="Click for filter throughput metadata"
                  >
                    <span>{b.name}</span>
                    <span className="text-[10px] text-slate-500">({(b.pivot / 10000).toFixed(1)}µm)</span>
                    <Info className="w-2.5 h-2.5 text-slate-500 hover:text-slate-300" />
                  </button>
                </div>

                {/* Progress brightness bar */}
                <div className="flex-1 bg-cosmos-900 rounded-full h-3 overflow-hidden border border-cosmos-800/80">
                  <div
                    style={{ width: `${pct}%`, backgroundColor: b.barColor }}
                    className="h-full rounded-full transition-all duration-300 opacity-80 shadow-sm"
                  />
                </div>

                {/* Flux in uJy */}
                <span className="w-16 text-right font-mono text-[11px] text-slate-300">
                  {uJy > 0.001 ? (uJy < 1000 ? `${uJy.toFixed(2)}` : `${uJy.toExponential(1)}`) : '< 0.001'}
                </span>

                {/* AB Mag & Uncertainty */}
                <span className="w-24 text-right font-mono text-xs font-bold text-slate-100">
                  {isDetected ? (
                    <span>
                      {mag.toFixed(2)}
                      {err > 0 && err < 5 && <span className="text-[10px] text-slate-400 font-normal"> ±{err.toFixed(2)}</span>}
                    </span>
                  ) : (
                    <span className="text-slate-500 font-normal">&gt; {NIRCAM_5SIGMA_LIMITS[b.key]?.toFixed(1) || '29.5'}</span>
                  )}
                </span>

                {/* Detection Flag Badge */}
                <div className="w-16 flex justify-center">
                  {isSecure ? (
                    <span className="px-1.5 py-0.2 rounded text-[10px] font-mono font-semibold bg-emerald-950/80 text-emerald-400 border border-emerald-700/60 flex items-center space-x-0.5">
                      <ShieldCheck className="w-2.5 h-2.5" />
                      <span>{s_n.toFixed(0)}σ</span>
                    </span>
                  ) : isMarginal ? (
                    <span className="px-1.5 py-0.2 rounded text-[10px] font-mono font-semibold bg-amber-950/80 text-amber-300 border border-amber-700/60 flex items-center space-x-0.5">
                      <AlertCircle className="w-2.5 h-2.5" />
                      <span>{s_n.toFixed(1)}σ</span>
                    </span>
                  ) : (
                    <span className="px-1.5 py-0.2 rounded text-[10px] font-mono font-normal bg-cosmos-900 text-slate-500 border border-cosmos-800">
                      &lt;3σ
                    </span>
                  )}
                </div>
              </div>

              {/* Filter Throughput Details Tooltip Dropdown */}
              {activeTooltip === b.key && (
                <div className="mt-1.5 p-2 bg-cosmos-900/95 border border-cosmos-700 rounded-lg text-xs font-mono text-slate-300 shadow-xl z-30">
                  <div className="flex items-center justify-between border-b border-cosmos-800 pb-1 mb-1 font-bold text-slate-100">
                    <span>JWST NIRCam {b.name} Filter Spec</span>
                    <button onClick={() => setActiveTooltip(null)} className="text-slate-400 hover:text-white">✕</button>
                  </div>
                  <div className="grid grid-cols-2 gap-x-2 gap-y-0.5 text-[11px]">
                    <div>Pivot Wavelength:</div>
                    <div className="text-amber-300 font-bold">{b.pivot.toFixed(1)} Å ({ (b.pivot / 10000).toFixed(3) } µm)</div>
                    <div>5σ Medium-Deep Limit:</div>
                    <div className="text-emerald-400 font-bold">{NIRCAM_5SIGMA_LIMITS[b.key]?.toFixed(1)} AB mag (10 ks)</div>
                    <div>Throughput Curve:</div>
                    <div className="text-slate-400">STScI Module A+B Mean</div>
                    <div>SHA-256 Digest:</div>
                    <div className="text-slate-500 truncate">{fltMeta?.sha256 || 'c0ffee1234567890'}</div>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
