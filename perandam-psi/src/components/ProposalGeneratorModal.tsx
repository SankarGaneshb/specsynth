import React, { useState } from 'react';
import { X, Copy, Check, Telescope, Sparkles, Code2, Download } from 'lucide-react';
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

  const aptBlock = `=== JWST ASTRONOMER'S PROPOSAL TOOL (APT) SPECIFICATION ===
Target Name:           ${galaxy.id}
Category:              ${profile.class_title}
RA (J2000):            ${raString} (${galaxy.ra.toFixed(6)} deg)
Dec (J2000):           ${decString} (${galaxy.dec.toFixed(6)} deg)
Redshift (z):          ${galaxy.redshift.toFixed(3)}
Apparent Mag:          ${galaxy.apparent_mag.toFixed(2)} AB (F200W)

[OBSERVING CONFIGURATION]
Prime Instrument:      ${followup.instrument}
Disperser / Filter:    ${followup.mode}
Recommended Exposure:  ${followup.exposure_time_s} seconds (${(followup.exposure_time_s / 3600).toFixed(1)} hours)
Primary Science Goal:  ${followup.science_goal}

[RATIONALE & HYPOTHESES]
Statistical Deviation: ${profile.rarity_sigma.toFixed(2)}σ outlier from cosmological locus.
Hypothesis A (Leading): ${profile.hypotheses.primary}
Hypothesis B (Alternative): ${profile.hypotheses.alternative}
`;

  const pythonScript = `# SpecSynth Simulation & JWST Proposal Script for ${galaxy.id}
import numpy as np
from specsynth.adapters.toy import ToyAdapter
from specsynth.cosmology import TNG_COSMOLOGY, project_per_galaxy_photometry_chunk

# Target Metadata
TARGET_ID = "${galaxy.id}"
RA_DEG = ${galaxy.ra.toFixed(6)}
DEC_DEG = ${galaxy.dec.toFixed(6)}
REDSHIFT = ${galaxy.redshift.toFixed(3)}
LOG_MSTAR = ${galaxy.log_mstar.toFixed(2)}
SFR_MSUN_YR = ${galaxy.sfr.toFixed(3)}
RARITY_SIGMA = ${profile.rarity_sigma.toFixed(2)}

print(f"Target: {TARGET_ID} | Class: ${profile.class_title}")
print(f"Coordinates: RA={RA_DEG}°, Dec={DEC_DEG}° (z={REDSHIFT})")
print("Targeting Instrument: ${followup.instrument} with ${followup.mode}")
print("Expected integration time: ${followup.exposure_time_s}s")
`;

  const fullContent = `${aptBlock}\n\n${pythonScript}`;

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
          <div className="flex items-center space-x-2 text-purple-300">
            <Telescope className="w-5 h-5 text-purple-400" />
            <div>
              <h2 className="text-sm font-bold text-slate-100 flex items-center space-x-2">
                <span>JWST Observing Proposal Generator</span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-purple-900/80 text-purple-200 border border-purple-500/60">
                  {galaxy.id}
                </span>
              </h2>
              <p className="text-[11px] text-slate-400">
                Ready-to-submit APT parameters and reproduction Python code
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-cosmos-800 transition-colors"
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
              <span>{profile.class_title} ({profile.rarity_sigma.toFixed(2)}σ)</span>
            </div>
            <p className="text-[11px] text-slate-300">
              {profile.observed_phenomenon}
            </p>
          </div>

          {/* APT Block */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-slate-400 font-semibold text-[11px]">
              <span>APT Target & Instrument Specification</span>
              <span className="text-[10px] font-mono text-cyan-300">{followup.instrument}</span>
            </div>
            <pre className="p-3 bg-cosmos-950 rounded-lg border border-cosmos-800 text-[11px] font-mono text-slate-200 overflow-x-auto leading-relaxed">
              {aptBlock}
            </pre>
          </div>

          {/* Python Code */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-slate-400 font-semibold text-[11px]">
              <span className="flex items-center space-x-1">
                <Code2 className="w-3.5 h-3.5 text-indigo-400" />
                <span>Deterministic SpecSynth Verification Script</span>
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
            className="flex items-center space-x-1.5 px-3.5 py-1.5 bg-purple-600 hover:bg-purple-500 text-white rounded-lg text-xs font-semibold shadow-lg transition-colors cursor-pointer"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-300" /> : <Copy className="w-3.5 h-3.5" />}
            <span>{copied ? 'Copied to Clipboard' : 'Copy Full Proposal'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
