import React from 'react';
import { Sparkles, FileText, Compass, ExternalLink } from 'lucide-react';
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
  return (
    <div className="bg-gradient-to-br from-purple-950/70 via-cosmos-900/90 to-indigo-950/70 border border-purple-600/60 rounded-xl p-3.5 space-y-2.5 text-xs shadow-xl relative overflow-hidden">
      {/* Background Auroral Glow Accent */}
      <div className="absolute -top-12 -right-12 w-32 h-32 bg-purple-500/10 rounded-full blur-2xl pointer-events-none" />

      {/* Header: Badge & Title */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-1.5 text-purple-300 font-bold">
          <Sparkles className="w-4 h-4 text-purple-400 animate-pulse flex-shrink-0" />
          <span>FRONTIER DISCOVERY CANDIDATE</span>
        </div>
        <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-purple-900/80 text-purple-200 border border-purple-500/60 font-semibold shadow-sm">
          {profile.rarity_sigma.toFixed(2)}σ Outlier • {profile.rarity_percentile}
        </span>
      </div>

      <div>
        <h3 className="text-sm font-bold text-slate-100 flex items-center space-x-1.5">
          <span>{profile.class_title}</span>
        </h3>
        <p className="text-[11px] text-purple-200/90 font-mono mt-0.5 leading-relaxed">
          {profile.observed_phenomenon}
        </p>
      </div>

      {/* Competing Scientific Hypotheses */}
      <div className="space-y-1.5 pt-1">
        <div className="text-[10px] uppercase tracking-wider text-slate-400 font-bold flex items-center space-x-1">
          <Compass className="w-3 h-3 text-indigo-400" />
          <span>Competing Astrophysical Hypotheses</span>
        </div>

        {/* Primary Hypothesis */}
        <div className="bg-cosmos-950/90 p-2.5 rounded-lg border border-purple-800/40 space-y-1">
          <div className="text-[10px] font-semibold text-emerald-400 flex items-center space-x-1">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            <span>Leading Interpretation (Hypothesis A):</span>
          </div>
          <p className="text-[11px] text-slate-200 leading-relaxed pl-2.5">
            {profile.hypotheses.primary}
          </p>
        </div>

        {/* Alternative Hypothesis */}
        <div className="bg-cosmos-950/70 p-2.5 rounded-lg border border-cosmos-800 space-y-1">
          <div className="text-[10px] font-semibold text-amber-400 flex items-center space-x-1">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
            <span>Alternative Mechanism (Hypothesis B):</span>
          </div>
          <p className="text-[11px] text-slate-300 leading-relaxed pl-2.5">
            {profile.hypotheses.alternative}
          </p>
        </div>
      </div>

      {/* Follow-up Strategy & 1-Click Proposal Action */}
      <div className="pt-1 flex items-center justify-between border-t border-purple-900/50">
        <div className="text-[10px] text-purple-300">
          <span className="font-semibold text-purple-200">Recommended Follow-up:</span>{' '}
          <span className="font-mono text-cyan-300">{profile.jwst_followup.instrument} ({profile.jwst_followup.mode})</span>
        </div>
        <button
          onClick={onOpenProposal}
          className="flex items-center space-x-1.5 px-2.5 py-1 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white rounded-lg text-[10px] font-semibold shadow-md transition-all cursor-pointer"
        >
          <FileText className="w-3 h-3" />
          <span>JWST Proposal</span>
        </button>
      </div>
    </div>
  );
};
