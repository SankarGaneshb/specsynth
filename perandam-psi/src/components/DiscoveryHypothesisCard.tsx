import React from 'react';
import { Sparkles, FileText, Activity, BookOpen, AlertCircle } from 'lucide-react';
import { DiscoveryProfile } from '../types/galaxy';

interface DiscoveryHypothesisCardProps {
  galaxyId: string;
  profile: DiscoveryProfile;
  onOpenProposal: () => void;
}

export const DiscoveryHypothesisCard: React.FC<DiscoveryHypothesisCardProps> = ({
  galaxyId,
  profile,
  onOpenProposal,
}) => {
  const chi2Val = profile.rarity_chi2 ?? Number((profile.rarity_sigma * profile.rarity_sigma).toFixed(2));
  const pVal = profile.rarity_p_value ? profile.rarity_p_value.toExponential(2) : '< 1e-3';

  return (
    <div className="bg-gradient-to-br from-purple-950/70 via-cosmos-900/90 to-indigo-950/70 border border-purple-600/60 rounded-xl p-3.5 space-y-3 text-xs shadow-xl relative overflow-hidden">
      {/* Background Auroral Glow Accent */}
      <div className="absolute -top-12 -right-12 w-32 h-32 bg-purple-500/15 rounded-full blur-2xl pointer-events-none" />

      {/* Header: Class Title & 1-Click Action */}
      <div className="flex items-center justify-between gap-2 border-b border-purple-800/40 pb-2">
        <div className="flex items-center space-x-2 min-w-0">
          <Sparkles className="w-4 h-4 text-purple-400 animate-pulse flex-shrink-0" />
          <h3 className="text-sm font-bold text-slate-100 truncate">
            {profile.class_title}
          </h3>
        </div>
        <button
          onClick={onOpenProposal}
          className="flex items-center space-x-1.5 px-2.5 py-1 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white rounded-lg text-xs font-semibold shadow transition-all cursor-pointer flex-shrink-0"
          title="Open JWST Observing Feasibility & Planning Sheet"
        >
          <FileText className="w-3.5 h-3.5" />
          <span>JWST Feasibility</span>
        </button>
      </div>

      {/* Multidimensional Statistical Grounding Banner (Issue #6 Adjustment 4) */}
      <div className="bg-cosmos-950/90 rounded-lg p-2.5 border border-purple-900/60 space-y-1 font-mono text-[11px]">
        <div className="flex items-center justify-between text-purple-300">
          <div className="flex items-center space-x-1">
            <Activity className="w-3 h-3 text-purple-400" />
            <span className="font-bold">Mahalanobis Rarity: D_M = {profile.rarity_sigma.toFixed(2)}</span>
          </div>
          <span className="text-amber-300 font-semibold">{profile.rarity_percentile}</span>
        </div>
        <div className="flex items-center justify-between text-[10px] text-slate-400 pt-0.5 border-t border-cosmos-800/80">
          <span>χ²₆ = {chi2Val.toFixed(1)} (df = 6, p = {pVal})</span>
          <span className="text-slate-500">Basis: [M*, SFR, z, Av, C₁₅₀₋₄₄₄, C₂₀₀₋₂₇₇]</span>
        </div>
      </div>

      {/* Quantitative Observed Phenomenon */}
      <p className="text-[11.5px] text-purple-200/90 font-mono leading-relaxed">
        {profile.observed_phenomenon}
      </p>

      {/* Competing Scientific Interpretations with Confidence & Citations */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
        {/* Interpretation A */}
        <div className="bg-cosmos-950/90 p-2.5 rounded-lg border border-purple-800/50 space-y-1.5 flex flex-col justify-between">
          <div>
            <div className="text-[10px] font-semibold text-emerald-400 flex items-center justify-between">
              <span className="flex items-center space-x-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                <span>Candidate Interpretation A</span>
              </span>
              <span className="px-1.5 py-0.2 bg-emerald-950 text-emerald-300 rounded text-[9px] border border-emerald-800/60">
                {profile.hypotheses.confidence || 'HIGH'} CONFIDENCE
              </span>
            </div>
            <p className="text-[11px] text-slate-300 leading-relaxed mt-1">
              {profile.hypotheses.primary}
            </p>
          </div>
        </div>

        {/* Interpretation B */}
        <div className="bg-cosmos-950/90 p-2.5 rounded-lg border border-cosmos-800 space-y-1.5 flex flex-col justify-between">
          <div>
            <div className="text-[10px] font-semibold text-amber-400 flex items-center justify-between">
              <span className="flex items-center space-x-1">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                <span>Candidate Interpretation B</span>
              </span>
              <span className="px-1.5 py-0.2 bg-amber-950 text-amber-300 rounded text-[9px] border border-amber-800/60">
                ALTERNATIVE
              </span>
            </div>
            <p className="text-[11px] text-slate-300 leading-relaxed mt-1">
              {profile.hypotheses.alternative}
            </p>
          </div>
        </div>
      </div>

      {/* Missing Observations / Critical Discriminator */}
      {profile.hypotheses.required_observations && (
        <div className="bg-amber-950/30 border border-amber-800/40 rounded-lg p-2 text-[10.5px] text-amber-200/90 font-mono flex items-start space-x-1.5">
          <AlertCircle className="w-3.5 h-3.5 text-amber-400 flex-shrink-0 mt-0.5" />
          <span>{profile.hypotheses.required_observations}</span>
        </div>
      )}

      {/* Target Follow-up Specifications & Target Acquisition */}
      <div className="text-[11px] text-purple-300/90 pt-1.5 border-t border-purple-900/50 space-y-1 font-mono">
        <div className="flex items-center justify-between">
          <div>
            <span className="text-slate-400">Target Follow-up:</span>{' '}
            <span className="text-cyan-300 font-semibold">{profile.jwst_followup.instrument} ({profile.jwst_followup.mode})</span>
          </div>
          <span className="text-slate-400">{profile.jwst_followup.exposure_time_s}s</span>
        </div>

        {profile.jwst_followup.target_acquisition && (
          <div className="text-[10px] text-slate-400">
            <span className="text-indigo-400">Target Acquisition:</span> {profile.jwst_followup.target_acquisition}
          </div>
        )}
      </div>
    </div>
  );
};
