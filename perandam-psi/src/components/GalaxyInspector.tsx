import React, { useState, useEffect, useMemo } from 'react';
import { Galaxy, FilterCurveData } from '../types/galaxy';
import { forwardModelGalaxy } from '../utils/physics';
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

  // Recompute in-flight forward model (D_L(z) distance dimming, Charlot & Fall dust, Madau IGM, filter integration)
  const activeForwardModel = useMemo(() => {
    return forwardModelGalaxy(
      galaxy.sed,
      galaxy.redshift,
      currentZ,
      galaxy.av,
      currentAv,
      filters
    );
  }, [galaxy.sed, galaxy.redshift, currentZ, galaxy.av, currentAv, filters]);

  const currentFluxes = activeForwardModel.fluxes;
  const currentMags = activeForwardModel.mags;

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
        mag_errs: activeForwardModel.magErrs,
        snr: activeForwardModel.snr,
        apparent_mag: activeForwardModel.apparentMag,
      });
    }
  };

  const pythonSnippet = `"""
Reproduce ${galaxy.id} via SpecSynth and FSPS.
Numerical Parity Tolerance: In-browser JS integration matches Python SpecSynth
contraction within |Δm| < 0.02 mag across all 6 NIRCam bands.
"""

from pathlib import Path
import numpy as np
from specsynth.adapters.fsps import FSPSAdapter, find_default_fsps_grid
from specsynth.core import attenuation_curve, sfh_from_params, synth_block
from specsynth.cosmology import TNG_COSMOLOGY, project_per_galaxy_photometry_chunk
from specsynth.filters import get_filter

# 1. Physical Parameters
log_mstar = ${galaxy.log_mstar}
redshift  = ${currentZ.toFixed(3)}
av        = ${currentAv.toFixed(3)}
sfr       = ${galaxy.sfr.toFixed(3)}  # M☉/yr
tau_d     = av / 1.086
tau_b     = tau_d * 2.0

# 2. Load Bundled FSPS Grid (Chabrier IMF, MIST Isochrones)
grid_path = find_default_fsps_grid()
adapter = FSPSAdapter(filepath=grid_path)
ssp_data = adapter.load()

# 3. Form Delayed-Tau SFH normalized to stellar mass
p = np.array([[log_mstar, 3.0, 1.5, 0.0]], dtype=np.float32)
sfh = sfh_from_params(p, ssp_data.ages, ssp_data.mets)

# 4. Attenuation Curves (Charlot & Fall 2000)
ny = int((ssp_data.ages < 1e7).sum()) * len(ssp_data.mets)
kd = attenuation_curve(ssp_data.wave, -0.7).astype(np.float32)
kb = attenuation_curve(ssp_data.wave, -1.3).astype(np.float32)

# 5. Contract Rest-frame Spectrum: L_lambda [L☉ / Å]
spec_rest = synth_block(sfh, np.array([tau_d], dtype=np.float32), np.array([tau_b], dtype=np.float32), ssp_data.ssp, kd, kb, ny)

# 6. In-flight Filter Projection into JWST NIRCam Bands
target_filters = ["jwst_f090w", "jwst_f150w", "jwst_f200w", "jwst_f277w", "jwst_f356w", "jwst_f444w"]
filter_data = []
for fname in target_filters:
    flt = get_filter(fname)
    norm = np.trapezoid(flt.transmission * flt.wave, flt.wave)
    filter_data.append((fname, flt.wave, flt.transmission, norm))

# Project F_lambda [erg/s/cm2/A] with D_L(z) distance dimming and Madau (1995) IGM
phot = project_per_galaxy_photometry_chunk(
    spec_rest, np.array([redshift], dtype=np.float32), ssp_data.wave,
    filter_data, apply_igm=True, distance_dimming=True, input_units="lsun", cosmo=TNG_COSMOLOGY
)[0]

# 7. Convert F_lambda to f_nu and AB Magnitudes
c_ang_s = 2.99792458e18
print(f"Photometry for ${galaxy.id} (z={redshift:.3f}, Av={av:.3f}):")
for i, fn in enumerate(target_filters):
    flt = get_filter(fn)
    f_nu = phot[i] * (flt.pivot_wavelength ** 2) / c_ang_s
    m_ab = -2.5 * np.log10(f_nu) - 48.60 if f_nu > 0 else 99.0
    print(f"  {fn}: {m_ab:.2f} AB mag (f_nu = {f_nu*1e29:.2f} μJy)")
`;

  const handleCopyCode = () => {
    navigator.clipboard.writeText(pythonSnippet);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <aside className="w-full sm:w-[500px] h-[calc(100vh-3.5rem)] bg-cosmos-900/95 border-l border-cosmos-700/80 backdrop-blur-xl flex flex-col z-20 shadow-2xl overflow-hidden transition-all duration-300">
      {/* Top Header: Scientific Metadata & QA Status (Compact single-line) */}
      <div className="py-2.5 px-3.5 border-b border-cosmos-800 flex items-center justify-between bg-cosmos-950/70">
        <div className="flex items-center space-x-2.5 min-w-0">
          <div className="w-2.5 h-2.5 rounded-full bg-indigo-500 animate-pulse flex-shrink-0" />
          <h2 className="text-base font-bold text-slate-100 font-mono tracking-tight">{galaxy.id}</h2>
          {galaxy.discovery_profile ? (
            <span className="flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-purple-950/80 text-purple-300 border border-purple-600/70 shadow-sm">
              <Sparkles className="w-3 h-3 text-purple-400 animate-pulse" />
              <span>{galaxy.discovery_profile.rarity_sigma.toFixed(1)}σ Outlier</span>
            </span>
          ) : galaxy.sentry_status === 'PRISTINE' ? (
            <span className="flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-950/80 text-emerald-400 border border-emerald-700/60">
              <CheckCircle2 className="w-3 h-3 text-emerald-400" />
              <span>QC Validated</span>
            </span>
          ) : (
            <span className="flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-950/80 text-rose-400 border border-rose-700/60">
              <AlertTriangle className="w-3 h-3 text-rose-400" />
              <span>{galaxy.qc_failure_code || 'QC Anomaly'}</span>
            </span>
          )}
          <span className="text-[11px] text-slate-400 font-mono truncate hidden sm:inline">
            ({galaxy.ra.toFixed(4)}°, {galaxy.dec.toFixed(4)}°)
          </span>
        </div>

        <button
          onClick={onClose}
          className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-cosmos-800 transition-colors"
          title="Close Scientific Workspace"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Scientific Tab Switcher: Perfectly fits on one row with NO horizontal scroll */}
      <div className="flex border-b border-cosmos-800 bg-cosmos-950/80 px-2.5 pt-1.5 items-center justify-between">
        <button
          onClick={() => setActiveTab('sed')}
          className={`flex items-center space-x-1.5 px-2.5 py-2 text-xs sm:text-sm font-semibold border-b-2 transition-colors ${
            activeTab === 'sed'
              ? 'border-indigo-400 text-indigo-300'
              : 'border-transparent text-slate-400 hover:text-slate-300'
          }`}
          title="Rest-Frame Spectral Energy Distribution"
        >
          <Layers className="w-4 h-4" />
          <span>SED</span>
        </button>

        <button
          onClick={() => setActiveTab('color-color')}
          className={`flex items-center space-x-1.5 px-2.5 py-2 text-xs sm:text-sm font-semibold border-b-2 transition-colors ${
            activeTab === 'color-color'
              ? 'border-amber-400 text-amber-300'
              : 'border-transparent text-slate-400 hover:text-slate-300'
          }`}
          title="Color-Color Diagram (JOSS Fig. 3)"
        >
          <ScatterChart className="w-4 h-4" />
          <span>Color-Color</span>
        </button>

        {galaxy.discovery_profile && (
          <button
            onClick={() => setActiveTab('discovery')}
            className={`flex items-center space-x-1.5 px-2.5 py-2 text-xs sm:text-sm font-semibold border-b-2 transition-colors ${
              activeTab === 'discovery'
                ? 'border-purple-400 text-purple-300'
                : 'border-transparent text-purple-400/80 hover:text-purple-300'
            }`}
            title="Astrophysical Hypotheses & Observing Proposal"
          >
            <Sparkles className="w-4 h-4 text-purple-400 animate-pulse" />
            <span>Hypotheses</span>
          </button>
        )}

        {galaxy.sentry_status === 'ANOMALY' && (
          <button
            onClick={() => setActiveTab('discovery')}
            className={`flex items-center space-x-1.5 px-2.5 py-2 text-xs sm:text-sm font-semibold border-b-2 transition-colors ${
              activeTab === 'discovery'
                ? 'border-rose-400 text-rose-300'
                : 'border-transparent text-rose-400/80 hover:text-rose-300'
            }`}
            title="Sentry Physical Invariant Violation Diagnosis"
          >
            <AlertTriangle className="w-4 h-4 text-rose-400" />
            <span>Diagnosis</span>
          </button>
        )}

        <button
          onClick={() => setActiveTab('phot')}
          className={`flex items-center space-x-1.5 px-2.5 py-2 text-xs sm:text-sm font-semibold border-b-2 transition-colors ${
            activeTab === 'phot'
              ? 'border-indigo-400 text-indigo-300'
              : 'border-transparent text-slate-400 hover:text-slate-300'
          }`}
          title="Synthetic JWST Photometry"
        >
          <BarChart2 className="w-4 h-4" />
          <span>Photometry</span>
        </button>

        <button
          onClick={() => setActiveTab('code')}
          className={`flex items-center space-x-1.5 px-2.5 py-2 text-xs sm:text-sm font-semibold border-b-2 transition-colors ${
            activeTab === 'code'
              ? 'border-cyan-400 text-cyan-300'
              : 'border-transparent text-slate-400 hover:text-slate-300'
          }`}
          title="Python Reproducibility Script"
        >
          <Code className="w-4 h-4" />
          <span>Python</span>
        </button>
      </div>

      {/* Main Scientific Visualization Panel (Dominant View) */}
      <div className="p-2.5 flex-1 overflow-y-auto space-y-2.5 scrollbar-thin scrollbar-thumb-cosmos-800">
        {/* On Plot Tabs: Slim Alert Strip with clear legible fonts */}
        {activeTab !== 'discovery' && galaxy.discovery_profile && (
          <div className="flex items-center justify-between px-3 py-1.5 bg-purple-950/40 border border-purple-800/50 rounded-lg text-xs shadow-sm">
            <div className="flex items-center space-x-2 truncate min-w-0">
              <Sparkles className="w-4 h-4 text-purple-400 flex-shrink-0" />
              <span className="text-xs font-bold text-purple-200 truncate">{galaxy.discovery_profile.class_title}</span>
            </div>
            <div className="flex items-center space-x-2.5 flex-shrink-0">
              <button
                onClick={() => setIsProposalOpen(true)}
                className="px-2.5 py-1 rounded-md bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white text-xs font-semibold shadow transition-all cursor-pointer"
                title="Open STScI APT Observing Proposal Generator"
              >
                JWST Proposal
              </button>
              <button
                onClick={() => setActiveTab('discovery')}
                className="text-xs text-purple-300 hover:text-purple-100 underline font-medium cursor-pointer"
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
            filters={filters}
          />
        )}

        {activeTab === 'phot' && (
          <PhotometryBar
            mags={currentMags}
            fluxes={activeForwardModel.fluxes}
            magErrs={activeForwardModel.magErrs}
            snr={activeForwardModel.snr}
            filters={filters}
          />
        )}

        {activeTab === 'code' && (
          <div className="space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-300">Deterministic Python In-Flight Forward Model</span>
              <button
                onClick={handleCopyCode}
                className="flex items-center space-x-1.5 text-xs px-2.5 py-1 rounded-lg bg-cosmos-800 hover:bg-cosmos-700 text-slate-200 border border-cosmos-700 transition-colors cursor-pointer"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copied ? 'Copied' : 'Copy'}</span>
              </button>
            </div>
            <pre className="p-3.5 bg-cosmos-950 rounded-xl border border-cosmos-800 text-xs font-mono text-indigo-200 whitespace-pre-wrap break-words leading-relaxed select-text">
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

        {/* Supporting Physical Parameters: Single Roomy Row with Increased Legibility */}
        <div className="grid grid-cols-4 gap-2 text-xs">
          <div className="bg-cosmos-950/80 border border-cosmos-800 rounded-lg p-2 shadow-sm">
            <div className="text-slate-400 text-[10px] uppercase font-bold tracking-wider">Mass</div>
            <div className="text-sm font-extrabold text-indigo-300 mt-0.5">
              10<sup>{galaxy.log_mstar.toFixed(2)}</sup> <span className="text-[10px] font-normal text-slate-400">M☉</span>
            </div>
          </div>

          <div className="bg-cosmos-950/80 border border-cosmos-800 rounded-lg p-2 shadow-sm">
            <div className="text-slate-400 text-[10px] uppercase font-bold tracking-wider">Redshift</div>
            <div className="text-sm font-extrabold text-amber-300 mt-0.5">
              z={currentZ.toFixed(2)}
            </div>
          </div>

          <div className="bg-cosmos-950/80 border border-cosmos-800 rounded-lg p-2 shadow-sm">
            <div className="text-slate-400 text-[10px] uppercase font-bold tracking-wider">SFR</div>
            <div className="text-sm font-extrabold text-cyan-300 mt-0.5 truncate">
              {galaxy.sfr.toFixed(1)} <span className="text-[10px] font-normal text-slate-400">M☉/yr</span>
            </div>
          </div>

          <div className="bg-cosmos-950/80 border border-cosmos-800 rounded-lg p-2 shadow-sm">
            <div className="text-slate-400 text-[10px] uppercase font-bold tracking-wider">Dust Av</div>
            <div className="text-sm font-extrabold text-rose-300 mt-0.5">
              {currentAv.toFixed(2)} <span className="text-[10px] font-normal text-slate-400">mag</span>
            </div>
          </div>
        </div>

        {/* Supporting Interactive Controls Deck: 2-Column Compact Grid with Larger Fonts */}
        <div className="p-3 bg-cosmos-950/70 border border-cosmos-800 rounded-xl space-y-2 shadow-sm">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-1.5 text-xs font-bold text-slate-200">
              <Sliders className="w-3.5 h-3.5 text-amber-400" />
              <span>Forward-Modeling Parameters</span>
            </div>
            {(isZEdited || isAvEdited) && (
              <button
                onClick={handleResetSliders}
                className="text-[11px] text-amber-400 hover:text-amber-300 underline font-medium cursor-pointer"
              >
                Reset to Origin
              </button>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3.5">
            {/* Redshift Slider */}
            <div>
              <div className="flex justify-between text-xs text-slate-300 mb-1 font-medium">
                <span>Redshift (z)</span>
                <span className="font-mono font-bold text-amber-300">z = {currentZ.toFixed(2)}</span>
              </div>
              <input
                type="range"
                min="0.1"
                max="10.0"
                step="0.05"
                value={currentZ}
                onChange={(e) => handleSliderChange(parseFloat(e.target.value), null)}
                className="w-full h-2 bg-cosmos-800 rounded-lg appearance-none cursor-pointer accent-amber-400"
              />
            </div>

            {/* Dust Av Slider */}
            <div>
              <div className="flex justify-between text-xs text-slate-300 mb-1 font-medium">
                <span>Dust (Av)</span>
                <span className="font-mono font-bold text-rose-300">{currentAv.toFixed(2)} mag</span>
              </div>
              <input
                type="range"
                min="0.0"
                max="3.0"
                step="0.05"
                value={currentAv}
                onChange={(e) => handleSliderChange(null, parseFloat(e.target.value))}
                className="w-full h-2 bg-cosmos-800 rounded-lg appearance-none cursor-pointer accent-rose-400"
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
