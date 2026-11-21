import React from 'react';

interface PhotometryBarProps {
  mags: Record<string, number>;
}

export const PhotometryBar: React.FC<PhotometryBarProps> = ({ mags }) => {
  const bands = [
    { key: 'jwst_f090w', label: 'F090W (0.9µm)', color: 'bg-sky-400' },
    { key: 'jwst_f150w', label: 'F150W (1.5µm)', color: 'bg-emerald-400' },
    { key: 'jwst_f200w', label: 'F200W (2.0µm)', color: 'bg-amber-400' },
    { key: 'jwst_f277w', label: 'F277W (2.8µm)', color: 'bg-orange-400' },
    { key: 'jwst_f356w', label: 'F356W (3.6µm)', color: 'bg-rose-400' },
    { key: 'jwst_f444w', label: 'F444W (4.4µm)', color: 'bg-fuchsia-400' },
  ];

  // In astronomical magnitudes, lower number = brighter
  const validMags = Object.values(mags).filter((m) => m > 10 && m < 50);
  const minMag = Math.min(...validMags, 20);
  const maxMag = Math.max(...validMags, 30);

  return (
    <div className="bg-cosmos-950/80 rounded-xl border border-cosmos-800 p-3 select-none">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-semibold text-slate-300">Synthetic JWST NIRCam Photometry</span>
        <span className="text-[10px] text-slate-400 font-mono">AB Magnitudes</span>
      </div>

      <div className="space-y-2">
        {bands.map((b) => {
          const mag = mags[b.key] || 99.0;
          // Width based on brightness: brighter (lower mag) = wider bar
          const pct = Math.max(10, Math.min(100, ((maxMag - mag) / (maxMag - minMag + 0.1)) * 90 + 10));

          return (
            <div key={b.key} className="flex items-center space-x-2 text-xs">
              <span className="w-24 text-[11px] text-slate-400 font-mono">{b.label}</span>
              <div className="flex-1 bg-cosmos-900 rounded-full h-3 overflow-hidden border border-cosmos-800">
                <div
                  style={{ width: `${pct}%` }}
                  className={`h-full rounded-full ${b.color} transition-all duration-300 opacity-80`}
                />
              </div>
              <span className="w-14 text-right font-mono text-[11px] text-slate-200">
                {mag < 50 ? `${mag.toFixed(2)}` : 'undetected'}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
};
