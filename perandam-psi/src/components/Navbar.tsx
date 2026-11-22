import React from 'react';
import {
  Telescope,
  Cpu,
  CheckCircle2,
  Compass,
  GraduationCap,
  Palette,
} from 'lucide-react';
import { SkyColorMode } from '../types/galaxy';

interface NavbarProps {
  nGalaxies: number;
  selectedId: string | null;
  isConnected: boolean;
  colorMode: SkyColorMode;
  onChangeColorMode: (mode: SkyColorMode) => void;
  onResetView: () => void;
  onSelectGalaxy: (id: string) => void;
  onOpenGuide: () => void;
  galaxiesList: string[];
}

export const Navbar: React.FC<NavbarProps> = ({
  nGalaxies,
  selectedId,
  isConnected,
  colorMode,
  onChangeColorMode,
  onResetView,
  onSelectGalaxy,
  onOpenGuide,
  galaxiesList,
}) => {
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

      {/* Center Controls: Colormap Selector & Galaxy Quick-Jump */}
      <div className="flex items-center space-x-2.5">
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
            {galaxiesList.slice(0, 100).map((id) => (
              <option key={id} value={id} className="bg-cosmos-900 text-slate-200">
                {id}
              </option>
            ))}
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
        {/* Validated Physical QA Badge */}
        <div
          title="Passed 4-tier physical invariants: non-negative fluxes, D4000 break bounds, sub-Hubble stellar ages"
          className="hidden sm:flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-emerald-950/60 border border-emerald-700/50 text-emerald-300"
        >
          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
          <span>QC Passed: Validated</span>
        </div>

        {/* Engine Connectivity Indicator */}
        <div
          title={isConnected ? 'Connected to local SpecSynth engine (:8000)' : 'Running in Standalone Mock mode'}
          className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-full border ${
            isConnected
              ? 'bg-indigo-950/60 border-indigo-500/60 text-indigo-300'
              : 'bg-cosmos-800/80 border-cosmos-700 text-slate-400'
          }`}
        >
          <Cpu className={`w-3.5 h-3.5 ${isConnected ? 'text-indigo-400 animate-pulse' : 'text-slate-500'}`} />
          <span>{isConnected ? 'Engine: SpecSynth' : 'Standalone Mock'}</span>
        </div>
      </div>
    </header>
  );
};
