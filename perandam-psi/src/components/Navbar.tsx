import React from 'react';
import {
  Telescope,
  Cpu,
  CheckCircle2,
  Compass,
  GraduationCap,
  Palette,
  Sparkles,
  AlertTriangle,
  ShieldCheck,
  Layers,
  Box,
} from 'lucide-react';
import { Galaxy, SkyColorMode, ViewportMode } from '../types/galaxy';

interface NavbarProps {
  nGalaxies: number;
  selectedId: string | null;
  isConnected: boolean;
  colorMode: SkyColorMode;
  onChangeColorMode: (mode: SkyColorMode) => void;
  viewportMode: ViewportMode;
  onToggleViewportMode: () => void;
  onChangeViewportMode?: (mode: ViewportMode) => void;
  onResetView: () => void;
  onSelectGalaxy: (id: string) => void;
  onOpenGuide: () => void;
  galaxies: Galaxy[];
  discoveryMode: boolean;
  onToggleDiscoveryMode: () => void;
  datasetId: 'goods_s_mock' | 'tng_100';
  onSwitchDataset: (id: 'goods_s_mock' | 'tng_100') => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  nGalaxies,
  selectedId,
  isConnected,
  colorMode,
  onChangeColorMode,
  viewportMode,
  onToggleViewportMode,
  onChangeViewportMode,
  onResetView,
  onSelectGalaxy,
  onOpenGuide,
  galaxies,
  discoveryMode,
  onToggleDiscoveryMode,
  datasetId,
  onSwitchDataset,
}) => {
  const selectedGalaxy = galaxies.find((g) => g.id === selectedId);
  const discoveries = galaxies.filter((g) => Boolean(g.discovery_profile));
  const anomalies = galaxies.filter((g) => g.sentry_status === 'ANOMALY');
  const standardGalaxies = galaxies.filter((g) => !g.discovery_profile && g.sentry_status !== 'ANOMALY');
  return (
    <header className="h-14 bg-cosmos-900/90 backdrop-blur border-b border-cosmos-700/80 px-4 flex items-center justify-between z-30 select-none">
      {/* Brand & Signature Mark */}
      <div className="flex items-center space-x-3">
        <div className="flex items-center space-x-2">
          <span className="text-2xl font-black bg-gradient-to-r from-indigo-400 via-cyan-400 to-amber-300 bg-clip-text text-transparent tracking-wider">
            PerandamΨ
          </span>
          <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-950/80 border border-indigo-700/60 text-indigo-300 font-medium">
            PSI Space
          </span>
        </div>
        <div className="hidden lg:flex items-center text-xs text-slate-400 pl-3 border-l border-cosmos-700">
          <span>IllustrisTNG → JWST NIRCam Scientific Demo</span>
        </div>
      </div>

      {/* Center Controls: Dataset Switcher, Colormap Selector & Galaxy Quick-Jump */}
      <div className="flex items-center space-x-2.5">
        {/* Dual Dataset Switcher (Issue #6 Provisioning) */}
        <div className="flex items-center space-x-1.5 bg-cosmos-950/80 border border-indigo-700/60 rounded-lg px-2.5 py-1 text-xs shadow-sm">
          <Layers className="w-3.5 h-3.5 text-indigo-400" />
          <span className="hidden xl:inline text-slate-400 font-medium">Dataset:</span>
          <select
            value={datasetId}
            onChange={(e) => onSwitchDataset(e.target.value as 'goods_s_mock' | 'tng_100')}
            className="bg-transparent text-indigo-200 focus:outline-none cursor-pointer pr-1 font-medium font-mono"
            title="Switch between Synthetic GOODS-S Mock and IllustrisTNG-100 Calibration Sample"
          >
            <option value="goods_s_mock" className="bg-cosmos-900 text-slate-200 font-sans">
              GOODS-S Deep Mock (508)
            </option>
            <option value="tng_100" className="bg-cosmos-900 text-slate-200 font-sans">
              TNG-100 Calibration (100)
            </option>
          </select>
        </div>

        {/* Scientific Colormap Selector */}
        <div className="flex items-center space-x-1.5 bg-cosmos-950/80 border border-cosmos-700 rounded-lg px-2.5 py-1 text-xs">
          <Palette className="w-3.5 h-3.5 text-indigo-400" />
          <span className="hidden sm:inline text-slate-400 font-medium">Color Field:</span>
          <select
            value={colorMode}
            onChange={(e) => onChangeColorMode(e.target.value as SkyColorMode)}
            className="bg-transparent text-slate-200 focus:outline-none cursor-pointer pr-1 font-medium"
          >
            <option value="rgb" className="bg-cosmos-900 text-slate-200">
              JWST RGB Composite
            </option>
            <option value="redshift" className="bg-cosmos-900 text-slate-200">
              Redshift (z)
            </option>
            <option value="ssfr" className="bg-cosmos-900 text-slate-200">
              Specific SFR (Bimodality)
            </option>
            <option value="mass" className="bg-cosmos-900 text-slate-200">
              Stellar Mass (log M*)
            </option>
          </select>
        </div>

        {/* Viewport Mode Segmented Selector (2D Sky / 3D Lightcone / 3D Stage) */}
        <div className="flex items-center bg-cosmos-950/80 border border-cosmos-700 rounded-lg p-0.5 text-xs">
          <button
            onClick={() => onChangeViewportMode ? onChangeViewportMode('2d') : onToggleViewportMode()}
            className={`px-2 py-1 rounded-md font-semibold transition-all cursor-pointer ${
              viewportMode === '2d'
                ? 'bg-cosmos-800 text-cyan-300 shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
            title="2D Projected Sky Canvas"
          >
            2D Sky
          </button>
          <button
            onClick={() => onChangeViewportMode ? onChangeViewportMode('3d') : onToggleViewportMode()}
            className={`flex items-center space-x-1 px-2 py-1 rounded-md font-semibold transition-all cursor-pointer ${
              viewportMode === '3d'
                ? 'bg-indigo-950 border border-indigo-500/60 text-indigo-200 shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
            title="3D Cosmological Lightcone & Progenitor Trajectories"
          >
            <Compass className="w-3.5 h-3.5 text-indigo-400" />
            <span>3D Lightcone</span>
          </button>
          <button
            onClick={() => onChangeViewportMode ? onChangeViewportMode('twin') : onToggleViewportMode()}
            className={`flex items-center space-x-1 px-2 py-1 rounded-md font-semibold transition-all cursor-pointer ${
              viewportMode === 'twin'
                ? 'bg-gradient-to-r from-indigo-950 to-cyan-950 border border-cyan-400 text-cyan-200 shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
            title="3D Multi-Galaxy Stage & Milky Way Benchmark"
          >
            <Sparkles className="w-3.5 h-3.5 text-amber-300" />
            <span>3D Stage</span>
          </button>
        </div>

        {/* 🔭 Discovery Mode Toggle */}
        <button
          onClick={onToggleDiscoveryMode}
          title="Toggle Frontier Discovery Mining Mode"
          className={`flex items-center space-x-1.5 px-2.5 py-1 text-xs border rounded-lg font-semibold transition-all cursor-pointer ${
            discoveryMode
              ? 'bg-purple-900/80 border-purple-500 text-purple-200 shadow-lg shadow-purple-900/40 ring-1 ring-purple-400/50'
              : 'bg-cosmos-950/80 hover:bg-cosmos-800 border-cosmos-700 text-slate-300'
          }`}
        >
          <Sparkles className={`w-3.5 h-3.5 ${discoveryMode ? 'text-purple-300 animate-pulse' : 'text-purple-400'}`} />
          <span className="hidden sm:inline">Discovery</span>
          {discoveryMode && (
            <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-ping" />
          )}
        </button>

        {/* Galaxy Jump Selector */}
        <div className="flex items-center space-x-2 bg-cosmos-950/80 border border-cosmos-700 rounded-lg px-2.5 py-1 text-xs">
          <Telescope className="w-3.5 h-3.5 text-cyan-400" />
          <select
            value={selectedId || ''}
            onChange={(e) => e.target.value && onSelectGalaxy(e.target.value)}
            className="bg-transparent text-slate-200 focus:outline-none cursor-pointer pr-1"
          >
            <option value="" disabled className="bg-cosmos-900">
              Jump to Galaxy ({nGalaxies})...
            </option>
            {discoveries.length > 0 && (
              <optgroup label={`✨ Frontier Discoveries & Extrema (${discoveries.length})`}>
                {discoveries.map((g) => (
                  <option key={g.id} value={g.id} className="bg-cosmos-900 text-purple-300 font-mono">
                    ✨ {g.id} — {g.discovery_profile?.class_title.split('(')[0].trim()} ({g.rarity_score?.toFixed(1)}σ)
                  </option>
                ))}
              </optgroup>
            )}
            {anomalies.length > 0 && (
              <optgroup label={`⚠️ QC Failed Anomalies (${anomalies.length})`}>
                {anomalies.map((g) => (
                  <option key={g.id} value={g.id} className="bg-cosmos-900 text-rose-300 font-mono">
                    ⚠️ {g.id} ({g.qc_failure_code || 'Anomaly'})
                  </option>
                ))}
              </optgroup>
            )}
            <optgroup label={`Standard Galaxies (${standardGalaxies.length})`}>
              {standardGalaxies.slice(0, 100).map((g) => (
                <option key={g.id} value={g.id} className="bg-cosmos-900 text-slate-200">
                  {g.id} (z={g.redshift.toFixed(2)}, logM={g.log_mstar.toFixed(1)})
                </option>
              ))}
            </optgroup>
          </select>
        </div>

        <button
          onClick={onResetView}
          title="Reset Viewport & Center Field"
          className="flex items-center space-x-1.5 px-2.5 py-1 text-xs bg-cosmos-800 hover:bg-cosmos-700 border border-cosmos-700 rounded-lg text-slate-300 transition-colors"
        >
          <Compass className="w-3.5 h-3.5 text-amber-400" />
          <span className="hidden md:inline">Center</span>
        </button>

        <button
          onClick={onOpenGuide}
          title="Student & Scientific Walkthrough Guide"
          className="flex items-center space-x-1.5 px-2.5 py-1 text-xs bg-indigo-900/60 hover:bg-indigo-800/80 border border-indigo-700/70 rounded-lg text-indigo-200 transition-colors"
        >
          <GraduationCap className="w-3.5 h-3.5 text-indigo-300" />
          <span>Guide</span>
        </button>
      </div>

      {/* Right Stats & Scientific QA / Engine Status */}
      <div className="flex items-center space-x-2.5 text-xs">
        {/* Global Catalog Sentry QA Status (Non-redundant with Inspector) */}
        <div
          title={`Catalog Sentry: ${galaxies.length - anomalies.length} pristine objects, ${anomalies.length} quarantined anomalies (${((1 - anomalies.length / galaxies.length) * 100).toFixed(1)}% invariant compliance)`}
          className="hidden sm:flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-cosmos-950/90 border border-cosmos-700 text-slate-300 shadow-sm"
        >
          <ShieldCheck className="w-3.5 h-3.5 text-cyan-400" />
          <span>Catalog Sentry: <strong className="text-emerald-400 font-mono">{galaxies.length - anomalies.length}</strong>/{galaxies.length}</span>
        </div>

        {/* Engine Connectivity Indicator */}
        <div
          title={isConnected ? 'Connected to local SpecSynth HTTP Bridge (:8000)' : 'Running in Standalone In-Browser Mode'}
          className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-full border ${
            isConnected
              ? 'bg-indigo-950/60 border-indigo-500/60 text-indigo-300'
              : 'bg-cosmos-800/80 border-cosmos-700 text-slate-400'
          }`}
        >
          <Cpu className={`w-3.5 h-3.5 ${isConnected ? 'text-indigo-400 animate-pulse' : 'text-slate-500'}`} />
          <span>{isConnected ? 'Local Bridge Available' : 'Standalone Mode'}</span>
        </div>
      </div>
    </header>
  );
};
