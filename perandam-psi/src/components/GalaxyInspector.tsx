import React, { useState, useEffect } from 'react';
import { Galaxy, FilterCurveData } from '../types/galaxy';
import { SedPlot } from './SedPlot';
import { PhotometryBar } from './PhotometryBar';
import { X, Sliders, ShieldCheck, AlertTriangle, Code, BarChart2, Layers, Copy, Check } from 'lucide-react';

interface GalaxyInspectorProps {
  galaxy: Galaxy | null;
  filters: FilterCurveData[];
  onClose: () => void;
  onUpdateGalaxy?: (updated: Galaxy) => void;
}

export const GalaxyInspector: React.FC<GalaxyInspectorProps> = ({
  galaxy,
  filters,
  onClose,
  onUpdateGalaxy,
}) => {
  const [activeTab, setActiveTab] = useState<'sed' | 'phot' | 'code'>('sed');
  const [sliderZ, setSliderZ] = useState<number | null>(null);
  const [sliderAv, setSliderAv] = useState<number | null>(null);
  const [copied, setCopied] = useState<boolean>(false);

  // Reset slider state when a new galaxy is selected
  useEffect(() => {
    setSliderZ(null);
    setSliderAv(null);
  }, [galaxy?.id]);

  if (!galaxy) return null;

  const currentZ = sliderZ !== null ? sliderZ : galaxy.redshift;
  const currentAv = sliderAv !== null ? sliderAv : galaxy.av;

  const isZEdited = sliderZ !== null && Math.abs(sliderZ - galaxy.redshift) > 0.01;
  const isAvEdited = sliderAv !== null && Math.abs(sliderAv - galaxy.av) > 0.01;

  // Recompute fluxes & magnitudes for JWST bands when Av or z is changed
  const deltaAv = currentAv - galaxy.av;
  const currentFluxes: Record<string, number> = {};
  const currentMags: Record<string, number> = {};

  filters.forEach((flt) => {
    const origFlux = galaxy.fluxes[flt.name] || 1e-32;
    const restCenter = flt.pivot_wavelength / (1.0 + currentZ);
    const deltaTau = (deltaAv / 1.086) * Math.pow(restCenter / 5500.0, -0.7);
    const newFlux = Math.max(1e-35, origFlux * Math.exp(-deltaTau));
    currentFluxes[flt.name] = newFlux;
    currentMags[flt.name] = newFlux > 0 ? parseFloat((-2.5 * Math.log10(newFlux) - 48.60).toFixed(2)) : 99.0;
  });

  const handleResetSliders = () => {
    setSliderZ(null);
    setSliderAv(null);
    if (onUpdateGalaxy) {
      onUpdateGalaxy(galaxy);
    }
  };

  const handleSliderChange = (newZ: number | null, newAv: number | null) => {
    const zVal = newZ !== null ? newZ : currentZ;
    const avVal = newAv !== null ? newAv : currentAv;
    if (newZ !== null) setSliderZ(newZ);
    if (newAv !== null) setSliderAv(newAv);

    if (onUpdateGalaxy) {
      onUpdateGalaxy({
        ...galaxy,
        redshift: zVal,
        av: avVal,
        fluxes: currentFluxes,
        mags: currentMags,
      });
    }
  };

  const pythonSnippet = `# Reproduce ${galaxy.id} via SpecSynth
from specsynth.adapters.toy import ToyAdapter
from specsynth.core import attenuation_curve, synth_block
from specsynth.cosmology import TNG_COSMOLOGY, project_per_galaxy_photometry_chunk
import numpy as np

# 1. Physical Parameters
log_mstar = ${galaxy.log_mstar}
redshift = ${currentZ.toFixed(2)}
av = ${currentAv.toFixed(2)}
sfr = ${galaxy.sfr.toFixed(2)} # M☉/yr

# 2. Forward-Model Photometry in-flight
print(f"Synthesizing {galaxy.id} at z={redshift}...")
`;

  const handleCopyCode = () => {
    navigator.clipboard.writeText(pythonSnippet);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <aside className="w-full sm:w-[480px] h-[calc(100vh-3.5rem)] bg-cosmos-900/95 border-l border-cosmos-700/80 backdrop-blur-xl flex flex-col z-20 shadow-2xl overflow-hidden transition-all duration-300">
      {/* Top Header */}
      <div className="p-4 border-b border-cosmos-800 flex items-center justify-between">
        <div className="flex items-center space-x-2.5">
          <div className="w-2.5 h-2.5 rounded-full bg-indigo-500 animate-pulse" />
          <div>
            <div className="flex items-center space-x-2">
              <h2 className="text-base font-bold text-slate-100">{galaxy.id}</h2>
              {galaxy.sentry_status === 'PRISTINE' ? (
                <span className="flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-950/80 text-emerald-400 border border-emerald-700/60">
                  <ShieldCheck className="w-3 h-3" />
                  <span>SENTRY PRISTINE</span>
                </span>
              ) : (
                <span className="flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-rose-950/80 text-rose-400 border border-rose-700/60">
                  <AlertTriangle className="w-3 h-3" />
                  <span>ANOMALY FLAGGED</span>
                </span>
              )}
            </div>
            <div className="text-[11px] text-slate-400 font-mono">
              RA: {galaxy.ra.toFixed(5)}° • Dec: {galaxy.dec.toFixed(5)}°
            </div>
          </div>
        </div>

        <button
          onClick={onClose}
          className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-cosmos-800 transition-colors"
          title="Close Inspector"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Physical Parameter Badges */}
      <div className="p-4 border-b border-cosmos-800/80 grid grid-cols-2 gap-2 text-xs">
        <div className="bg-cosmos-950/80 border border-cosmos-800 rounded-lg p-2.5">
          <div className="text-slate-400 text-[10px] uppercase font-semibold">Stellar Mass</div>
          <div className="text-base font-bold text-indigo-300 mt-0.5">
            10<sup>{galaxy.log_mstar.toFixed(2)}</sup> <span className="text-xs font-normal text-slate-400">M☉</span>
          </div>
        </div>

        <div className="bg-cosmos-950/80 border border-cosmos-800 rounded-lg p-2.5">
          <div className="text-slate-400 text-[10px] uppercase font-semibold">Redshift z</div>
          <div className="text-base font-bold text-amber-300 mt-0.5">
            {currentZ.toFixed(2)}{' '}
            {isZEdited && <span className="text-[10px] text-amber-400 font-normal">(edited)</span>}
          </div>
        </div>

        <div className="bg-cosmos-950/80 border border-cosmos-800 rounded-lg p-2.5">
          <div className="text-slate-400 text-[10px] uppercase font-semibold">SFR ψ(t)</div>
          <div className="text-base font-bold text-cyan-300 mt-0.5">
            {galaxy.sfr.toFixed(2)} <span className="text-xs font-normal text-slate-400">M☉/yr</span>
          </div>
        </div>

        <div className="bg-cosmos-950/80 border border-cosmos-800 rounded-lg p-2.5">
          <div className="text-slate-400 text-[10px] uppercase font-semibold">Dust Attenuation Av</div>
          <div className="text-base font-bold text-rose-300 mt-0.5">
            {currentAv.toFixed(2)} <span className="text-xs font-normal text-slate-400">mag</span>{' '}
            {isAvEdited && <span className="text-[10px] text-rose-400 font-normal">(edited)</span>}
          </div>
        </div>
      </div>

      {/* Real-Time Sliders Section */}
      <div className="px-4 py-3 bg-cosmos-950/40 border-b border-cosmos-800/80">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center space-x-1.5 text-xs font-semibold text-slate-300">
            <Sliders className="w-3.5 h-3.5 text-amber-400" />
            <span>Interactive Forward-Modeling Controls</span>
          </div>
          {(isZEdited || isAvEdited) && (
            <button
              onClick={handleResetSliders}
              className="text-[10px] text-amber-400 hover:text-amber-300 underline cursor-pointer"
            >
              Reset to TNG Origin
            </button>
          )}
        </div>

        {/* Redshift Slider */}
        <div className="mb-2">
          <div className="flex justify-between text-[11px] text-slate-400 mb-1">
            <span>Redshift (z)</span>
            <span className="font-mono text-slate-200">{currentZ.toFixed(2)}</span>
          </div>
          <input
            type="range"
            min="0.1"
            max="10.0"
            step="0.05"
            value={currentZ}
            onChange={(e) => handleSliderChange(parseFloat(e.target.value), null)}
            className="w-full h-1.5 bg-cosmos-800 rounded-lg appearance-none cursor-pointer accent-amber-400"
          />
        </div>

        {/* Dust Av Slider */}
        <div>
          <div className="flex justify-between text-[11px] text-slate-400 mb-1">
            <span>Dust Attenuation (Av)</span>
            <span className="font-mono text-slate-200">{currentAv.toFixed(2)} mag</span>
          </div>
          <input
            type="range"
            min="0.0"
            max="3.0"
            step="0.05"
            value={currentAv}
            onChange={(e) => handleSliderChange(null, parseFloat(e.target.value))}
            className="w-full h-1.5 bg-cosmos-800 rounded-lg appearance-none cursor-pointer accent-rose-400"
          />
        </div>
      </div>

      {/* Tab Switcher */}
      <div className="flex border-b border-cosmos-800 bg-cosmos-950/60 px-4 pt-2">
        <button
          onClick={() => setActiveTab('sed')}
          className={`flex items-center space-x-1.5 px-3 py-1.5 text-xs font-medium border-b-2 transition-colors ${
            activeTab === 'sed'
              ? 'border-indigo-400 text-indigo-300'
              : 'border-transparent text-slate-400 hover:text-slate-300'
          }`}
        >
          <Layers className="w-3.5 h-3.5" />
          <span>Rest-Frame SED</span>
        </button>

        <button
          onClick={() => setActiveTab('phot')}
          className={`flex items-center space-x-1.5 px-3 py-1.5 text-xs font-medium border-b-2 transition-colors ${
            activeTab === 'phot'
              ? 'border-indigo-400 text-indigo-300'
              : 'border-transparent text-slate-400 hover:text-slate-300'
          }`}
        >
          <BarChart2 className="w-3.5 h-3.5" />
          <span>Photometry</span>
        </button>

        <button
          onClick={() => setActiveTab('code')}
          className={`flex items-center space-x-1.5 px-3 py-1.5 text-xs font-medium border-b-2 transition-colors ${
            activeTab === 'code'
              ? 'border-indigo-400 text-indigo-300'
              : 'border-transparent text-slate-400 hover:text-slate-300'
          }`}
        >
          <Code className="w-3.5 h-3.5" />
          <span>Export Python</span>
        </button>
      </div>

      {/* Main Tab Content */}
      <div className="p-4 flex-1 overflow-y-auto space-y-4">
        {activeTab === 'sed' && (
          <SedPlot
            sed={galaxy.sed}
            filters={filters}
            redshift={currentZ}
            dustAv={currentAv}
            originalAv={galaxy.av}
          />
        )}

        {activeTab === 'phot' && <PhotometryBar mags={currentMags} />}

        {activeTab === 'code' && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-400">SpecSynth Python Reproduction Snippet</span>
              <button
                onClick={handleCopyCode}
                className="flex items-center space-x-1 text-xs px-2 py-1 rounded bg-cosmos-800 hover:bg-cosmos-700 text-slate-200 border border-cosmos-700"
              >
                {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                <span>{copied ? 'Copied!' : 'Copy'}</span>
              </button>
            </div>
            <pre className="p-3 bg-cosmos-950 rounded-lg border border-cosmos-800 text-[11px] font-mono text-indigo-200 overflow-x-auto leading-relaxed">
              {pythonSnippet}
            </pre>
          </div>
        )}
      </div>
    </aside>
  );
};
