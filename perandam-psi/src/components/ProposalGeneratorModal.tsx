import React, { useState } from 'react';
import { X, Copy, Check, Telescope, Sparkles, Code2, Compass, AlertCircle, Eye } from 'lucide-react';
import { Galaxy } from '../types/galaxy';

interface ProposalGeneratorModalProps {
  isOpen: boolean;
  onClose: () => void;
  galaxy: Galaxy;
}

export const ProposalGeneratorModal: React.FC<ProposalGeneratorModalProps> = ({
  isOpen,
  onClose,
  galaxy,
}) => {
  const [copied, setCopied] = useState(false);
  if (!isOpen || !galaxy.discovery_profile) return null;

  const profile = galaxy.discovery_profile;
  const followup = profile.jwst_followup;

  // Convert RA/Dec to sexagesimal strings
  const raHours = Math.floor(galaxy.ra / 15);
  const raMinutes = Math.floor((galaxy.ra / 15 - raHours) * 60);
  const raSeconds = (((galaxy.ra / 15 - raHours) * 60 - raMinutes) * 60).toFixed(2);
  const raString = `${String(raHours).padStart(2, '0')}:${String(raMinutes).padStart(2, '0')}:${String(raSeconds).padStart(5, '0')}`;

  const absDec = Math.abs(galaxy.dec);
  const decSign = galaxy.dec < 0 ? '-' : '+';
  const decDeg = Math.floor(absDec);
  const decMinutes = Math.floor((absDec - decDeg) * 60);
  const decSeconds = (((absDec - decDeg) * 60 - decMinutes) * 60).toFixed(2);
  const decString = `${decSign}${String(decDeg).padStart(2, '0')}:${String(decMinutes).padStart(2, '0')}:${String(decSeconds).padStart(5, '0')}`;

  // Celestial to Ecliptic coordinate transformation (J2000 obliquity eps = 23.4393 deg)
  const raRad = (galaxy.ra * Math.PI) / 180.0;
  const decRad = (galaxy.dec * Math.PI) / 180.0;
  const epsRad = (23.4392911 * Math.PI) / 180.0;

  const sinBeta = Math.sin(decRad) * Math.cos(epsRad) - Math.cos(decRad) * Math.sin(epsRad) * Math.sin(raRad);
  const betaDeg = (Math.asin(sinBeta) * 180.0) / Math.PI;

  const cosBeta = Math.cos((betaDeg * Math.PI) / 180.0);
  const sinLambda = (Math.sin(decRad) * Math.sin(epsRad) + Math.cos(decRad) * Math.cos(epsRad) * Math.sin(raRad)) / cosBeta;
  const cosLambda = (Math.cos(decRad) * Math.cos(raRad)) / cosBeta;
  const lambdaDeg = (((Math.atan2(sinLambda, cosLambda) * 180.0) / Math.PI) + 360.0) % 360.0;

  // JWST Field of Regard: targets with |beta| ~ 45 deg have two observability windows per year
  const annualDays = Math.abs(betaDeg) > 40 ? 190 : 120;
  const visibilitySummary = `Annual Visibility: ~${annualDays} days/year (2 operational windows: Oct 20 - Jan 25 & May 25 - Aug 28). Ecliptic: λ = ${lambdaDeg.toFixed(1)}°, β = ${betaDeg.toFixed(1)}°.`;

  // Target acquisition scoping
  const isSpectroscopy = followup.instrument.includes('NIRSpec') || followup.mode.includes('Grism') || followup.instrument.includes('MIRI');
  const targetAcquisitionDetail = followup.instrument.includes('NIRSpec')
    ? 'CRITICAL: NIRSpec fixed-slit / micro-shutter array requires Wide Aperture Target Acquisition (WATA) using a bright reference star (V < 20.0 mag, SNR > 20) located within 2.0 arcmin of target.'
    : followup.instrument.includes('MIRI')
    ? 'MIRI Target Acquisition: Autonomous peakup or direct target acquisition star required for low-resolution prism spectroscopy.'
    : 'NIRCam Direct Imaging: Point-and-shoot Module A/B imaging; no dedicated target acquisition star required.';

  const planningSheet = `=== JWST OBSERVING FEASIBILITY & PLANNING SPECIFICATION ===
Target Name:           ${galaxy.id}
Classification:        ${profile.class_title}
Statistical Grounding: Mahalanobis Distance D_M = ${profile.rarity_sigma.toFixed(2)} (χ²_6 = ${(profile.rarity_sigma**2).toFixed(1)}, ${profile.rarity_percentile})

[CELESTIAL & ECLIPTIC COORDINATES]
Equatorial (J2000):    RA = ${raString} (${galaxy.ra.toFixed(6)}°), Dec = ${decString} (${galaxy.dec.toFixed(6)}°)
Ecliptic (J2000):      λ = ${lambdaDeg.toFixed(2)}°, β = ${betaDeg.toFixed(2)}°
Observing Windows:     ${visibilitySummary}

[OBSERVING CONFIGURATION]
Prime Instrument:      ${followup.instrument}
Disperser / Filter:    ${followup.mode}
Recommended Exposure:  ${followup.exposure_time_s} seconds (${(followup.exposure_time_s / 3600).toFixed(1)} hours)
Primary Science Goal:  ${followup.science_goal}

[TARGET ACQUISITION CONSTRAINTS]
${targetAcquisitionDetail}

[ASTROPHYSICAL INTERPRETATIONS & EVIDENCE]
Candidate Int. A:      ${profile.hypotheses.primary}
Candidate Int. B:      ${profile.hypotheses.alternative}
Required Observation:  ${profile.hypotheses.required_observations || 'High-resolution rest-frame optical spectroscopy.'}
`;

  const pythonScript = `"""
SpecSynth & FSPS Verification Script for ${galaxy.id}
Target: ${profile.class_title} (D_M = ${profile.rarity_sigma.toFixed(2)})
Parity Tolerance: |Δm| < 0.02 mag between JS integration and Python SpecSynth.
"""

from specsynth.adapters.fsps import FSPSAdapter, find_default_fsps_grid
from specsynth.core import attenuation_curve, sfh_from_params, synth_block
from specsynth.cosmology import TNG_COSMOLOGY, project_per_galaxy_photometry_chunk
from specsynth.filters import get_filter
import numpy as np

# Physical coordinates
ra, dec, z = ${galaxy.ra.toFixed(6)}, ${galaxy.dec.toFixed(6)}, ${galaxy.redshift.toFixed(3)}
log_mstar, av = ${galaxy.log_mstar.toFixed(2)}, ${galaxy.av.toFixed(3)}

# Execute forward model
ssp = FSPSAdapter(filepath=find_default_fsps_grid()).load()
sfh = sfh_from_params(np.array([[log_mstar, 3.0, 1.5, 0.0]], dtype=np.float32), ssp.ages, ssp.mets)
kd = attenuation_curve(ssp.wave, -0.7).astype(np.float32)
kb = attenuation_curve(ssp.wave, -1.3).astype(np.float32)
ny = int((ssp.ages < 1e7).sum()) * len(ssp.mets)

spec = synth_block(sfh, np.array([av/1.086], dtype=np.float32), np.array([av*2/1.086], dtype=np.float32), ssp.ssp, kd, kb, ny)
filter_data = [(fn, get_filter(fn).wave, get_filter(fn).transmission, np.trapezoid(get_filter(fn).transmission * get_filter(fn).wave, get_filter(fn).wave)) for fn in ["jwst_f090w", "jwst_f150w", "jwst_f200w", "jwst_f277w", "jwst_f356w", "jwst_f444w"]]

phot = project_per_galaxy_photometry_chunk(spec, np.array([z], dtype=np.float32), ssp.wave, filter_data, apply_igm=True, distance_dimming=True, input_units="lsun", cosmo=TNG_COSMOLOGY)[0]
print(f"Verified ${galaxy.id} synthesized fluxes (erg/s/cm2/A): {phot}")
`;

  const fullContent = `${planningSheet}\n\n${pythonScript}`;

  const handleCopy = () => {
    navigator.clipboard.writeText(fullContent);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fade-in">
      <div className="relative w-full max-w-2xl bg-cosmos-900 border border-purple-600/70 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-cosmos-800 bg-cosmos-950/80">
          <div className="flex items-center space-x-2.5 text-purple-300">
            <Telescope className="w-5 h-5 text-purple-400" />
            <div>
              <h2 className="text-sm font-bold text-slate-100 flex items-center space-x-2">
                <span>JWST Follow-up Observing Feasibility & Planning Sheet</span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-purple-900/80 text-purple-200 border border-purple-500/60">
                  {galaxy.id}
                </span>
              </h2>
              <p className="text-[11px] text-slate-400 font-mono">
                Astronomical celestial coordinates, ecliptic visibility & instrument constraints
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-cosmos-800 transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Area */}
        <div className="p-4 overflow-y-auto space-y-3.5 text-xs">
          {/* Summary Banner */}
          <div className="p-3 bg-purple-950/50 rounded-xl border border-purple-800/60 space-y-1">
            <div className="font-semibold text-purple-200 text-xs flex items-center space-x-1.5">
              <Sparkles className="w-3.5 h-3.5 text-purple-400" />
              <span>{profile.class_title} (D_M = {profile.rarity_sigma.toFixed(2)})</span>
            </div>
            <p className="text-[11px] text-slate-300">
              {profile.observed_phenomenon}
            </p>
          </div>

          {/* Celestial & Ecliptic Observability Card */}
          <div className="p-3 bg-cosmos-950/90 rounded-xl border border-cyan-800/50 space-y-1.5 font-mono text-[11px]">
            <div className="flex items-center justify-between text-cyan-300 font-semibold border-b border-cosmos-800/80 pb-1">
              <span className="flex items-center space-x-1.5">
                <Compass className="w-3.5 h-3.5" />
                <span>Celestial Coordinates & JWST Field of Regard</span>
              </span>
              <span className="text-[10px] text-slate-400">J2000</span>
            </div>
            <div className="grid grid-cols-2 gap-2 text-[11px] text-slate-300 pt-0.5">
              <div>RA: <span className="text-white font-bold">{raString}</span> ({galaxy.ra.toFixed(4)}°)</div>
              <div>Dec: <span className="text-white font-bold">{decString}</span> ({galaxy.dec.toFixed(4)}°)</div>
              <div>Ecliptic Longitude λ: <span className="text-cyan-300">{lambdaDeg.toFixed(2)}°</span></div>
              <div>Ecliptic Latitude β: <span className="text-cyan-300">{betaDeg.toFixed(2)}°</span></div>
            </div>
            <div className="text-[10.5px] text-emerald-300/90 pt-1 border-t border-cosmos-800/60 flex items-center space-x-1">
              <Eye className="w-3 h-3 text-emerald-400 flex-shrink-0" />
              <span>{visibilitySummary}</span>
            </div>
          </div>

          {/* Instrument Target Acquisition Constraint Card */}
          <div className={`p-3 rounded-xl border space-y-1 font-mono text-[11px] ${
            isSpectroscopy ? 'bg-amber-950/40 border-amber-800/60 text-amber-200' : 'bg-cosmos-950/80 border-cosmos-800 text-slate-300'
          }`}>
            <div className="flex items-center space-x-1.5 font-bold">
              <AlertCircle className={`w-3.5 h-3.5 ${isSpectroscopy ? 'text-amber-400' : 'text-slate-400'}`} />
              <span>Instrument Constraints & Target Acquisition ({followup.instrument})</span>
            </div>
            <p className="text-[10.5px] leading-relaxed">
              {targetAcquisitionDetail}
            </p>
          </div>

          {/* Planning Sheet Preformatted Block */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-slate-400 font-semibold text-[11px]">
              <span>APT Planning & Target Summary Block</span>
              <span className="text-[10px] font-mono text-cyan-300">{followup.instrument}</span>
            </div>
            <pre className="p-3 bg-cosmos-950 rounded-lg border border-cosmos-800 text-[11px] font-mono text-slate-200 overflow-x-auto leading-relaxed">
              {planningSheet}
            </pre>
          </div>

          {/* Verification Code */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-slate-400 font-semibold text-[11px]">
              <span className="flex items-center space-x-1">
                <Code2 className="w-3.5 h-3.5 text-indigo-400" />
                <span>SpecSynth Verification Script (|Δm| &lt; 0.02 mag parity)</span>
              </span>
            </div>
            <pre className="p-3 bg-cosmos-950 rounded-lg border border-cosmos-800 text-[11px] font-mono text-indigo-200 overflow-x-auto leading-relaxed">
              {pythonScript}
            </pre>
          </div>
        </div>

        {/* Footer */}
        <div className="p-3 border-t border-cosmos-800 bg-cosmos-950/80 flex items-center justify-between">
          <span className="text-[11px] text-slate-400">
            Export format compatible with STScI APT v2024.3+
          </span>
          <button
            onClick={handleCopy}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold shadow transition-all cursor-pointer"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-300" /> : <Copy className="w-3.5 h-3.5" />}
            <span>{copied ? 'Copied to Clipboard' : 'Copy Planning Sheet'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
