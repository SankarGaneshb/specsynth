import React, { useState, useEffect } from 'react';
import { Galaxy, FilterCurveData } from '../types/galaxy';
import { SedPlot } from './SedPlot';
import { ColorColorPlot } from './ColorColorPlot';
import { PhotometryBar } from './PhotometryBar';
import {
  X,
  Sliders,
  CheckCircle2,
  AlertTriangle,
  Code,
  BarChart2,
  Layers,
  Copy,
  Check,
  ScatterChart,
  Info,
} from 'lucide-react';

interface GalaxyInspectorProps {
  galaxy: Galaxy | null;
  allGalaxies: Galaxy[];
  filters: FilterCurveData[];
  onClose: () => void;
  onUpdateGalaxy?: (updated: Galaxy) => void;
}

export const GalaxyInspector: React.FC<GalaxyInspectorProps> = ({
  galaxy,
  allGalaxies,
  filters,
  onClose,
  onUpdateGalaxy,
}) => {
  const [activeTab, setActiveTab] = useState<'sed' | 'color-color' | 'phot' | 'code'>('sed');
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

  // Scientific Extrapolation check (outside standard simulation calibration bounds)
  const isExtrapolatedRegime = currentZ > 8.0 || currentAv > 2.5;

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

  const pythonSnippet = `# Reproduce ${galaxy.id} via SpecSynth & FSPS
from specsynth.adapters.toy import ToyAdapter
from specsynth.core import attenuation_curve, synth_block
from specsynth.cosmology import TNG_COSMOLOGY, project_per_galaxy_photometry_chunk
import numpy as np

# Physical Parameters (Forward Model)
log_mstar = ${galaxy.log_mstar}
redshift = ${currentZ.toFixed(2)}
av = ${currentAv.toFixed(2)}
sfr = ${galaxy.sfr.toFixed(2)}  # M☉/yr

print("Executing in-flight GEMM filter projection...")
`;

  const handleCopyCode = () => {
    navigator.clipboard.writeText(pythonSnippet);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <aside className="w-full sm:w-[500px] h-[calc(100vh-3.5rem)] bg-cosmos-900/95 border-l border-cosmos-700/80 backdrop-blur-xl flex flex-col z-20 shadow-2xl overflow-hidden transition-all duration-300">
      {/* Top Header: Scientific Metadata & QA Status */}
      <div className="p-3.5 border-b border-cosmos-800 flex items-center justify-between bg-cosmos-950/60">
        <div className="flex items-center space-x-2.5">
          <div className="w-2.5 h-2.5 rounded-full bg-indigo-500 animate-pulse" />
          <div>
            <div className="flex items-center space-x-2">
              <h2 className="text-base font-bold text-slate-100">{galaxy.id}</h2>
              {galaxy.sentry_status === 'PRISTINE' ? (
                <span className="flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-950/80 text-emerald-400 border border-emerald-700/60">
                  <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                  <span>QC Passed: Validated</span>
                </span>
              ) : (
                <span className="flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-rose-950/80 text-rose-400 border border-rose-700/60">
                  <AlertTriangle className="w-3 h-3 text-rose-400" />
                  <span>QC Flag: Anomaly</span>
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
          title="Close Scientific Workspace"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Scientific Tab Switcher: Science Plots First! */}
      <div className="flex border-b border-cosmos-800 bg-cosmos-950/80 px-4 pt-2">
        <button
          onClick={() => setActiveTab('sed')}
          className={`flex items-center space-x-1.5 px-3 py-1.5 text-xs font-semibold border-b-2 transition-colors ${
            activeTab === 'sed'
              ? 'border-indigo-400 text-indigo-300'
              : 'border-transparent text-slate-400 hover:text-slate-300'
          }`}
        >
          <Layers className="w-3.5 h-3.5" />
          <span>Rest-Frame SED</span>
        </button>

        <button
          onClick={() => setActiveTab('color-color')}
          className={`flex items-center space-x-1.5 px-3 py-1.5 text-xs font-semibold border-b-2 transition-colors ${
            activeTab === 'color-color'
              ? 'border-amber-400 text-amber-300'
              : 'border-transparent text-slate-400 hover:text-slate-300'
          }`}
        >
          <ScatterChart className="w-3.5 h-3.5" />
          <span>Color-Color (Fig. 3)</span>
        </button>

        <button
          onClick={() => setActiveTab('phot')}
          className={`flex items-center space-x-1.5 px-3 py-1.5 text-xs font-semibold border-b-2 transition-colors ${
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
          className={`flex items-center space-x-1.5 px-3 py-1.5 text-xs font-semibold border-b-2 transition-colors ${
            activeTab === 'code'
              ? 'border-indigo-400 text-indigo-300'
              : 'border-transparent text-slate-400 hover:text-slate-300'
          }`}
        >
          <Code className="w-3.5 h-3.5" />
          <span>Python</span>
        </button>
      </div>

      {/* Main Scientific Visualization Panel (Dominant View) */}
      <div className="p-3.5 flex-1 overflow-y-auto space-y-3.5">
        {/* QC Failure Diagnostic Card */}
        {galaxy.sentry_status === 'ANOMALY' && (
          <div className="bg-rose-950/60 border border-rose-800/80 rounded-xl p-3.5 space-y-2 text-xs shadow-lg">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-1.5 text-rose-300 font-bold">
                <AlertTriangle className="w-4 h-4 text-rose-400 flex-shrink-0" />
                <span>QC FAILED: Physical Invariant Violation</span>
              </div>
              {galaxy.qc_failure_code && (
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-rose-900/80 text-rose-200 border border-rose-700/60 font-semibold">
                  {galaxy.qc_failure_code}
                </span>
              )}
            </div>
            <div className="text-slate-100 font-semibold text-xs">
              {galaxy.qc_failure_title}
            </div>
            <p className="text-[11px] text-slate-300 leading-relaxed bg-cosmos-950/80 p-2.5 rounded-lg border border-rose-900/40">
              {galaxy.qc_failure_detail}
            </p>
            <div className="text-[10px] text-rose-300 flex items-center space-x-1 pt-0.5">
              <span className="font-semibold text-rose-400">Action:</span>
              <span>Quarantine object. Run <code className="bg-cosmos-900 px-1 py-0.5 rounded text-rose-200">specsynth sentry --clean</code> to purge.</span>
            </div>
          </div>
        )}

        {activeTab === 'sed' && (
          <SedPlot
            sed={galaxy.sed}
            filters={filters}
            redshift={currentZ}
            originalZ={galaxy.redshift}
            dustAv={currentAv}
            originalAv={galaxy.av}
          />
        )}

        {activeTab === 'color-color' && (
          <ColorColorPlot
            allGalaxies={allGalaxies}
            selectedGalaxy={galaxy}
            currentZ={currentZ}
            currentAv={currentAv}
          />
        )}

        {activeTab === 'phot' && <PhotometryBar mags={currentMags} />}

        {activeTab === 'code' && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-400 font-medium">Deterministic Python In-Flight Forward Model</span>
              <button
                onClick={handleCopyCode}
                className="flex items-center space-x-1 text-xs px-2.5 py-1 rounded bg-cosmos-800 hover:bg-cosmos-700 text-slate-200 border border-cosmos-700"
              >
                {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                <span>{copied ? 'Copied' : 'Copy'}</span>
              </button>
            </div>
            <pre className="p-3 bg-cosmos-950 rounded-lg border border-cosmos-800 text-[11px] font-mono text-indigo-200 overflow-x-auto leading-relaxed">
              {pythonSnippet}
            </pre>
          </div>
        )}

        {/* Physical Extrapolation Regime Warning */}
        {isExtrapolatedRegime && (
          <div className="bg-amber-950/40 border border-amber-800/60 rounded-lg p-2.5 flex items-start space-x-2 text-xs text-amber-200">
            <Info className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
            <div className="text-[11px] leading-relaxed">
              <span className="font-semibold text-amber-300">Extrapolated Physical Regime:</span> Parameter extends beyond standard IllustrisTNG snapshot range ($z \le 8.0, A_V \le 2.5$). Model forward-projects using continuous spectral extrapolation.
            </div>
          </div>
        )}

        {/* Supporting Physical Parameters Grid */}
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="bg-cosmos-950/80 border border-cosmos-800 rounded-lg p-2.5">
            <div className="text-slate-400 text-[10px] uppercase font-semibold">Stellar Mass</div>
            <div className="text-sm font-bold text-indigo-300 mt-0.5">
              10<sup>{galaxy.log_mstar.toFixed(2)}</sup> <span className="text-xs font-normal text-slate-400">M☉</span>
            </div>
          </div>

          <div className="bg-cosmos-950/80 border border-cosmos-800 rounded-lg p-2.5">
            <div className="text-slate-400 text-[10px] uppercase font-semibold">Redshift z</div>
            <div className="text-sm font-bold text-amber-300 mt-0.5">
              {currentZ.toFixed(2)}{' '}
              {isZEdited && <span className="text-[9px] text-amber-400 font-normal">(Forward Model)</span>}
            </div>
          </div>

          <div className="bg-cosmos-950/80 border border-cosmos-800 rounded-lg p-2.5">
            <div className="text-slate-400 text-[10px] uppercase font-semibold">SFR ψ(t)</div>
            <div className="text-sm font-bold text-cyan-300 mt-0.5">
              {galaxy.sfr.toFixed(2)} <span className="text-xs font-normal text-slate-400">M☉/yr</span>
            </div>
          </div>

          <div className="bg-cosmos-950/80 border border-cosmos-800 rounded-lg p-2.5">
            <div className="text-slate-400 text-[10px] uppercase font-semibold">Dust Attenuation Av</div>
            <div className="text-sm font-bold text-rose-300 mt-0.5">
              {currentAv.toFixed(2)} <span className="text-xs font-normal text-slate-400">mag</span>{' '}
              {isAvEdited && <span className="text-[9px] text-rose-400 font-normal">(Forward Model)</span>}
            </div>
          </div>
        </div>

        {/* Supporting Interactive Controls Deck (Underneath the Science) */}
        <div className="p-3 bg-cosmos-950/70 border border-cosmos-800 rounded-xl space-y-2.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-1.5 text-xs font-semibold text-slate-300">
              <Sliders className="w-3.5 h-3.5 text-amber-400" />
              <span>Forward-Modeling Controls</span>
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
          <div>
            <div className="flex justify-between text-[11px] text-slate-400 mb-1">
              <span>Redshift (z)</span>
              <span className="font-mono text-slate-200">z = {currentZ.toFixed(2)}</span>
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
      </div>
    </aside>
  );
};
