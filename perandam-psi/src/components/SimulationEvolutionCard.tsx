import React, { useState, useMemo } from 'react';
import evolutionTracksData from '../data/evolution_tracks.json';
import {
  Activity,
  GitBranch,
  Layers,
  Sparkles,
  ChevronDown,
  ChevronUp,
  Clock,
  Flame,
  Calendar,
  Maximize2,
  Minimize2,
} from 'lucide-react';

interface SimulationEvolutionCardProps {
  currentRedshift: number;
  onSelectRedshift?: (z: number) => void;
  activeTrackId?: string;
  onChangeTrackId?: (id: string) => void;
}

export const SimulationEvolutionCard: React.FC<SimulationEvolutionCardProps> = ({
  currentRedshift,
  onSelectRedshift,
  activeTrackId: controlledTrackId,
  onChangeTrackId,
}) => {
  const [internalTrackId, setInternalTrackId] = useState<string>('TNG-DISC-01');
  const [isCollapsed, setIsCollapsed] = useState<boolean>(false);

  const activeTrackId = controlledTrackId || internalTrackId;
  const setTrackId = onChangeTrackId || setInternalTrackId;

  const tracks = (evolutionTracksData as any)?.tracks || {};
  const currentTrack = tracks[activeTrackId] || tracks['TNG-DISC-01'];
  const mainBranch: any[] = currentTrack?.main_branch || [];
  const mergers: any[] = currentTrack?.mergers || [];

  // Find the closest snapshot to currentRedshift
  const activeSnapshot = useMemo(() => {
    if (!mainBranch.length) return null;
    let closest = mainBranch[0];
    let minDiff = Math.abs((closest.redshift ?? 0) - currentRedshift);
    for (let i = 1; i < mainBranch.length; i++) {
      const diff = Math.abs((mainBranch[i].redshift ?? 0) - currentRedshift);
      if (diff < minDiff) {
        minDiff = diff;
        closest = mainBranch[i];
      }
    }
    return closest;
  }, [mainBranch, currentRedshift]);

  if (!currentTrack || !activeSnapshot) return null;

  return (
    <div className="bg-slate-900/90 backdrop-blur-md border border-slate-700/70 rounded-2xl p-3.5 shadow-2xl pointer-events-auto w-full select-none text-slate-200 transition-all duration-200">
      {/* Header: Title, Track Selector & Collapse button */}
      <div className="flex items-center justify-between pb-2 mb-2 border-b border-slate-700/60">
        <div className="flex items-center space-x-1.5 min-w-0">
          <Activity className="w-3.5 h-3.5 text-cyan-400 flex-shrink-0 animate-pulse" />
          <span className="text-[11px] font-bold uppercase tracking-wider text-cyan-300 truncate">
            Simulation Track & SED
          </span>
        </div>
        <div className="flex items-center space-x-1 flex-shrink-0">
          <select
            value={activeTrackId}
            onChange={(e) => setTrackId(e.target.value)}
            className="bg-slate-950 border border-slate-700 text-[10px] text-slate-300 rounded px-1.5 py-0.5 focus:outline-none focus:border-cyan-400 cursor-pointer"
          >
            <option value="TNG-DISC-01">TNG Disk Track</option>
            <option value="TNG-ANOM-01">TNG Monster Track</option>
          </select>
          <button
            onClick={() => setIsCollapsed((prev) => !prev)}
            className="p-1 text-slate-400 hover:text-slate-100 rounded hover:bg-slate-800 transition cursor-pointer"
            title={isCollapsed ? 'Expand Simulation Card' : 'Collapse Simulation Card'}
          >
            {isCollapsed ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronUp className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>

      {isCollapsed ? (
        /* Collapsed Summary Pill */
        <div className="flex items-center justify-between text-xs py-0.5">
          <span className="font-mono text-amber-300 font-semibold">
            z = {currentRedshift.toFixed(2)}
          </span>
          <span className="text-slate-400 text-[11px]">
            M* = {activeSnapshot.stellar_mass_msun.toExponential(1)} M☉
          </span>
          <span className="text-cyan-400 text-[10px] font-mono">
            {activeSnapshot.snapshot_id}
          </span>
        </div>
      ) : (
        /* Expanded Full Simulation & Forward-Modeling View */
        <div className="space-y-2.5 text-xs">
          {/* Active Snapshot Redshift & Time */}
          <div className="flex items-center justify-between bg-slate-950/80 p-2 rounded-xl border border-slate-800">
            <div>
              <div className="text-[10px] uppercase font-semibold text-slate-400">Current Epoch</div>
              <div className="text-base font-bold font-mono text-amber-300">
                z = {activeSnapshot.redshift.toFixed(2)}
              </div>
            </div>
            <div className="text-right">
              <div className="text-[10px] text-slate-400">Cosmic Age</div>
              <div className="text-xs font-mono text-cyan-300 font-semibold">
                t ≈ {activeSnapshot.cosmic_time_gyr.toFixed(2)} Gyr
              </div>
              <div className="text-[10px] text-slate-500 font-mono">
                ~{activeSnapshot.lookback_time_gyr.toFixed(1)} Gyr ago
              </div>
            </div>
          </div>

          {/* Key Simulation Physics Metrics */}
          <div className="grid grid-cols-2 gap-1.5 font-mono text-[11px]">
            <div className="bg-slate-950/60 p-2 rounded-lg border border-slate-800/80">
              <div className="text-[10px] font-sans text-slate-400 font-medium">Stellar Mass (M*)</div>
              <div className="text-emerald-400 font-bold mt-0.5">
                {activeSnapshot.stellar_mass_msun.toExponential(2)} M☉
              </div>
            </div>
            <div className="bg-slate-950/60 p-2 rounded-lg border border-slate-800/80">
              <div className="text-[10px] font-sans text-slate-400 font-medium">Star Formation (SFR)</div>
              <div className="text-cyan-300 font-bold mt-0.5">
                {activeSnapshot.sfr_msun_per_yr.toFixed(2)} M☉/yr
              </div>
            </div>
            <div className="bg-slate-950/60 p-2 rounded-lg border border-slate-800/80">
              <div className="text-[10px] font-sans text-slate-400 font-medium">Half-Mass Radius</div>
              <div className="text-slate-200 mt-0.5">
                r_1/2 ≈ {activeSnapshot.half_mass_radius_kpc.toFixed(2)} kpc
              </div>
            </div>
            <div className="bg-slate-950/60 p-2 rounded-lg border border-slate-800/80">
              <div className="text-[10px] font-sans text-slate-400 font-medium">Metallicity (Z)</div>
              <div className="text-amber-300 mt-0.5">
                Z ≈ {activeSnapshot.metallicity_z.toFixed(3)}
              </div>
            </div>
          </div>

          {/* Synthetic JWST NIRCam Multi-Band Photometry */}
          {activeSnapshot.photometry && (
            <div className="bg-slate-950/70 p-2 rounded-xl border border-slate-800/80">
              <div className="text-[10px] font-sans font-semibold text-slate-400 uppercase tracking-wider mb-1 flex items-center justify-between">
                <span>JWST NIRCam Photometry</span>
                <span className="text-slate-500 font-mono text-[9px]">AB mag</span>
              </div>
              <div className="grid grid-cols-3 gap-1 font-mono text-[10px]">
                <div className="bg-slate-900 px-1.5 py-0.5 rounded border border-cyan-900/60 flex justify-between items-center">
                  <span className="text-cyan-400 font-sans text-[9px]">F090W:</span>
                  <span className="text-slate-200">{activeSnapshot.photometry.jwst_f090w_mag?.toFixed(1) ?? '—'}</span>
                </div>
                <div className="bg-slate-900 px-1.5 py-0.5 rounded border border-sky-900/60 flex justify-between items-center">
                  <span className="text-sky-300 font-sans text-[9px]">F150W:</span>
                  <span className="text-slate-200">{activeSnapshot.photometry.jwst_f150w_mag?.toFixed(1) ?? '—'}</span>
                </div>
                <div className="bg-slate-900 px-1.5 py-0.5 rounded border border-amber-900/60 flex justify-between items-center">
                  <span className="text-amber-300 font-sans text-[9px]">F200W:</span>
                  <span className="text-slate-200">{activeSnapshot.photometry.jwst_f200w_mag?.toFixed(1) ?? '—'}</span>
                </div>
                <div className="bg-slate-900 px-1.5 py-0.5 rounded border border-orange-900/60 flex justify-between items-center">
                  <span className="text-orange-300 font-sans text-[9px]">F277W:</span>
                  <span className="text-slate-200">{activeSnapshot.photometry.jwst_f277w_mag?.toFixed(1) ?? '—'}</span>
                </div>
                <div className="bg-slate-900 px-1.5 py-0.5 rounded border border-rose-900/60 flex justify-between items-center">
                  <span className="text-rose-300 font-sans text-[9px]">F356W:</span>
                  <span className="text-slate-200">{activeSnapshot.photometry.jwst_f356w_mag?.toFixed(1) ?? '—'}</span>
                </div>
                <div className="bg-slate-900 px-1.5 py-0.5 rounded border border-purple-900/60 flex justify-between items-center">
                  <span className="text-purple-300 font-sans text-[9px]">F444W:</span>
                  <span className="text-slate-200">{activeSnapshot.photometry.jwst_f444w_mag?.toFixed(1) ?? '—'}</span>
                </div>
              </div>
            </div>
          )}

          {/* Merger History Timeline */}
          {mergers.length > 0 && (
            <div className="pt-1.5 border-t border-slate-800">
              <div className="text-[10px] font-sans font-semibold text-slate-400 uppercase tracking-wider mb-1 flex items-center space-x-1">
                <GitBranch className="w-3 h-3 text-amber-400" />
                <span>Simulation Merger Milestones</span>
              </div>
              <div className="space-y-1">
                {mergers.map((m: any, idx: number) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => onSelectRedshift?.(m.redshift)}
                    className="w-full flex items-center justify-between px-2 py-1 bg-slate-950/70 hover:bg-slate-800/80 border border-slate-800 rounded-lg text-[10px] font-mono transition text-left cursor-pointer"
                    title={`Jump to merger epoch at z=${m.redshift}`}
                  >
                    <div className="flex items-center space-x-1.5 text-slate-300">
                      <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                      <span>z = {m.redshift.toFixed(1)}</span>
                      <span className="text-slate-500 font-sans">({m.merger_type})</span>
                    </div>
                    <span className="text-cyan-400 font-semibold">
                      Ratio 1:{(1 / (m.mass_ratio || 0.1)).toFixed(1)}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
