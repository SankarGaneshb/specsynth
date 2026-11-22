import React, { useState, useEffect } from 'react';
import { Galaxy, FilterCurveData } from '../types/galaxy';
import { SedPlot } from './SedPlot';
import { ColorColorPlot } from './ColorColorPlot';
import { PhotometryBar } from './PhotometryBar';
import { DiscoveryHypothesisCard } from './DiscoveryHypothesisCard';
import { ProposalGeneratorModal } from './ProposalGeneratorModal';
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
  Sparkles,
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
  const [activeTab, setActiveTab] = useState<'sed' | 'color-color' | 'discovery' | 'phot' | 'code'>('sed');
  const [sliderZ, setSliderZ] = useState<number | null>(null);
  const [sliderAv, setSliderAv] = useState<number | null>(null);
  const [copied, setCopied] = useState<boolean>(false);
  const [isProposalOpen, setIsProposalOpen] = useState<boolean>(false);

  // Reset slider state when a new galaxy is selected
  useEffect(() => {
    setSliderZ(null);
    setSliderAv(null);
    if (activeTab === 'discovery' && !galaxy?.discovery_profile && galaxy?.sentry_status !== 'ANOMALY') {
      setActiveTab('sed');
    }
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
      {/* Top Header: Scientific Metadata & QA Status (Compact single-line) */}
      <div className="py-2 px-3 border-b border-cosmos-800 flex items-center justify-between bg-cosmos-950/70">
        <div className="flex items-center space-x-2 min-w-0">
          <div className="w-2 h-2 rounded-full bg-indigo-500 animate-pulse flex-shrink-0" />
          <h2 className="text-sm font-bold text-slate-100 font-mono">{galaxy.id}</h2>
          {galaxy.discovery_profile ? (
            <span className="flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-purple-950/80 text-purple-300 border border-purple-600/70 shadow-sm">
              <Sparkles className="w-2.5 h-2.5 text-purple-400 animate-pulse" />
              <span>{galaxy.discovery_profile.rarity_sigma.toFixed(1)}σ Outlier</span>
            </span>
          ) : galaxy.sentry_status === 'PRISTINE' ? (
            <span className="flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-950/80 text-emerald-400 border border-emerald-700/60">
              <CheckCircle2 className="w-2.5 h-2.5 text-emerald-400" />
              <span>QC Validated</span>
            </span>
          ) : (
            <span className="flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-rose-950/80 text-rose-400 border border-rose-700/60">
              <AlertTriangle className="w-2.5 h-2.5 text-rose-400" />
              <span>{galaxy.qc_failure_code || 'QC Anomaly'}</span>
            </span>
          )}
          <span className="text-[10px] text-slate-400 font-mono truncate hidden sm:inline">
            ({galaxy.ra.toFixed(4)}°, {galaxy.dec.toFixed(4)}°)
          </span>
        </div>

        <button
          onClick={onClose}
          className="p-1 rounded text-slate-400 hover:text-slate-200 hover:bg-cosmos-800 transition-colors"
          title="Close Scientific Workspace"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Scientific Tab Switcher: Science Plots First! */}
      <div className="flex border-b border-cosmos-800 bg-cosmos-950/80 px-2.5 pt-1.5 overflow-x-auto scrollbar-none">
        <button
          onClick={() => setActiveTab('sed')}
          className={`flex items-center space-x-1 px-2.5 py-1 text-xs font-semibold border-b-2 transition-colors whitespace-nowrap ${
            activeTab === 'sed'
              ? 'border-indigo-400 text-indigo-300'
              : 'border-transparent text-slate-400 hover:text-slate-300'
          }`}
        >
          <Layers className="w-3 h-3" />
          <span>Rest-Frame SED</span>
        </button>

        <button
          onClick={() => setActiveTab('color-color')}
          className={`flex items-center space-x-1 px-2.5 py-1 text-xs font-semibold border-b-2 transition-colors whitespace-nowrap ${
            activeTab === 'color-color'
              ? 'border-amber-400 text-amber-300'
              : 'border-transparent text-slate-400 hover:text-slate-300'
          }`}
        >
          <ScatterChart className="w-3 h-3" />
          <span>Color-Color (Fig. 3)</span>
        </button>

        {galaxy.discovery_profile && (
          <button
            onClick={() => setActiveTab('discovery')}
            className={`flex items-center space-x-1 px-2.5 py-1 text-xs font-semibold border-b-2 transition-colors whitespace-nowrap ${
              activeTab === 'discovery'
                ? 'border-purple-400 text-purple-300'
                : 'border-transparent text-purple-400/80 hover:text-purple-300'
            }`}
          >
            <Sparkles className="w-3 h-3 text-purple-400 animate-pulse" />
            <span>Hypotheses & Proposal</span>
          </button>
        )}

        {galaxy.sentry_status === 'ANOMALY' && (
          <button
            onClick={() => setActiveTab('discovery')}
            className={`flex items-center space-x-1 px-2.5 py-1 text-xs font-semibold border-b-2 transition-colors whitespace-nowrap ${
              activeTab === 'discovery'
                ? 'border-rose-400 text-rose-300'
                : 'border-transparent text-rose-400/80 hover:text-rose-300'
            }`}
          >
            <AlertTriangle className="w-3 h-3 text-rose-400" />
            <span>QC Diagnosis</span>
          </button>
        )}

        <button
          onClick={() => setActiveTab('phot')}
          className={`flex items-center space-x-1 px-2.5 py-1 text-xs font-semibold border-b-2 transition-colors whitespace-nowrap ${
            activeTab === 'phot'
              ? 'border-indigo-400 text-indigo-300'
              : 'border-transparent text-slate-400 hover:text-slate-300'
          }`}
        >
          <BarChart2 className="w-3 h-3" />
          <span>Photometry</span>
        </button>

        <button
          onClick={() => setActiveTab('code')}
          className={`flex items-center space-x-1 px-2.5 py-1 text-xs font-semibold border-b-2 transition-colors whitespace-nowrap ${
            activeTab === 'code'
              ? 'border-indigo-400 text-indigo-300'
              : 'border-transparent text-slate-400 hover:text-slate-300'
          }`}
        >
          <Code className="w-3 h-3" />
          <span>Python</span>
        </button>
      </div>

      {/* Main Scientific Visualization Panel (Dominant View) */}
      <div className="p-2.5 flex-1 overflow-y-auto space-y-2 scrollbar-thin scrollbar-thumb-cosmos-800">
        {/* On Plot Tabs: Slim 26px Alert Strip (Preserves Plot & Slider Visibility Without Scrollbar) */}
        {activeTab !== 'discovery' && galaxy.discovery_profile && (
          <div className="flex items-center justify-between px-2.5 py-1 bg-purple-950/40 border border-purple-800/50 rounded-lg text-xs shadow-sm">
            <div className="flex items-center space-x-1.5 truncate min-w-0">
              <Sparkles className="w-3 h-3 text-purple-400 flex-shrink-0" />
              <span className="text-[11px] font-semibold text-purple-200 truncate">{galaxy.discovery_profile.class_title}</span>
            </div>
            <div className="flex items-center space-x-2 flex-shrink-0">
              <button
                onClick={() => setIsProposalOpen(true)}
                className="px-2 py-0.5 rounded bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white text-[9.5px] font-semibold shadow transition-all cursor-pointer"
                title="Open STScI APT Observing Proposal Generator"
              >
                JWST Proposal
              </button>
              <button
                onClick={() => setActiveTab('discovery')}
                className="text-[10px] text-purple-300 hover:text-purple-100 underline font-medium cursor-pointer"
              >
                Hypotheses →
              </button>
            </div>
          </div>
        )}

        {activeTab !== 'discovery' && galaxy.sentry_status === 'ANOMALY' && (
          <div className="flex items-center justify-between px-2.5 py-1 bg-rose-950/40 border border-rose-800/50 rounded-lg text-xs shadow-sm">
            <div className="flex items-center space-x-1.5 truncate min-w-0">
              <AlertTriangle className="w-3 h-3 text-rose-400 flex-shrink-0" />
              <span className="text-[11px] font-semibold text-rose-200 truncate">{galaxy.qc_failure_title || galaxy.qc_failure_code}</span>
            </div>
            <button
              onClick={() => setActiveTab('discovery')}
              className="text-[10px] text-rose-300 hover:text-rose-100 underline font-medium cursor-pointer flex-shrink-0"
            >
              Diagnosis →
            </button>
          </div>
        )}

        {/* Dedicated Hypotheses & Proposal Tab View */}
        {activeTab === 'discovery' && galaxy.discovery_profile && (
          <DiscoveryHypothesisCard
            galaxyId={galaxy.id}
            profile={galaxy.discovery_profile}
            onOpenProposal={() => setIsProposalOpen(true)}
          />
        )}

        {/* Dedicated QC Diagnosis Tab View */}
        {activeTab === 'discovery' && galaxy.sentry_status === 'ANOMALY' && (
          <div className="bg-rose-950/60 border border-rose-800/80 rounded-xl p-3 space-y-2 text-xs shadow-lg">
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

        {/* Supporting Physical Parameters: Single Compact Row */}
        <div className="grid grid-cols-4 gap-1.5 text-xs">
          <div className="bg-cosmos-950/80 border border-cosmos-800 rounded-lg p-1.5">
            <div className="text-slate-400 text-[9px] uppercase font-semibold">Mass</div>
            <div className="text-xs font-bold text-indigo-300">
              10<sup>{galaxy.log_mstar.toFixed(2)}</sup> <span className="text-[9px] font-normal text-slate-400">M☉</span>
            </div>
          </div>

          <div className="bg-cosmos-950/80 border border-cosmos-800 rounded-lg p-1.5">
            <div className="text-slate-400 text-[9px] uppercase font-semibold">Redshift</div>
            <div className="text-xs font-bold text-amber-300">
              z={currentZ.toFixed(2)}
            </div>
          </div>

          <div className="bg-cosmos-950/80 border border-cosmos-800 rounded-lg p-1.5">
            <div className="text-slate-400 text-[9px] uppercase font-semibold">SFR</div>
            <div className="text-xs font-bold text-cyan-300 truncate">
              {galaxy.sfr.toFixed(1)} <span className="text-[9px] font-normal text-slate-400">M☉/yr</span>
            </div>
          </div>

          <div className="bg-cosmos-950/80 border border-cosmos-800 rounded-lg p-1.5">
            <div className="text-slate-400 text-[9px] uppercase font-semibold">Dust Av</div>
            <div className="text-xs font-bold text-rose-300">
              {currentAv.toFixed(2)} <span className="text-[9px] font-normal text-slate-400">mag</span>
            </div>
          </div>
        </div>

        {/* Supporting Interactive Controls Deck: 2-Column Compact Grid */}
        <div className="p-2.5 bg-cosmos-950/70 border border-cosmos-800 rounded-xl space-y-1.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-1.5 text-xs font-semibold text-slate-300">
              <Sliders className="w-3.5 h-3.5 text-amber-400" />
              <span className="text-[11px]">Forward-Modeling Parameters</span>
            </div>
            {(isZEdited || isAvEdited) && (
              <button
                onClick={handleResetSliders}
                className="text-[10px] text-amber-400 hover:text-amber-300 underline cursor-pointer"
              >
                Reset
              </button>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3">
            {/* Redshift Slider */}
            <div>
              <div className="flex justify-between text-[10px] text-slate-400 mb-0.5">
                <span>Redshift (z)</span>
                <span className="font-mono text-amber-300">z = {currentZ.toFixed(2)}</span>
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
              <div className="flex justify-between text-[10px] text-slate-400 mb-0.5">
                <span>Dust (Av)</span>
                <span className="font-mono text-rose-300">{currentAv.toFixed(2)} mag</span>
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
      </div>

      {/* JWST Observing Proposal Generator Modal */}
      <ProposalGeneratorModal
        isOpen={isProposalOpen}
        onClose={() => setIsProposalOpen(false)}
        galaxy={galaxy}
      />
    </aside>
  );
};
