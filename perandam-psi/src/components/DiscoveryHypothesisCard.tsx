import React from 'react';
import { Sparkles, FileText } from 'lucide-react';
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
    <div className="bg-gradient-to-br from-purple-950/60 via-cosmos-900/80 to-indigo-950/60 border border-purple-600/50 rounded-xl p-3 space-y-2.5 text-xs shadow-lg relative overflow-hidden">
      {/* Background Auroral Glow Accent */}
      <div className="absolute -top-10 -right-10 w-28 h-28 bg-purple-500/10 rounded-full blur-2xl pointer-events-none" />

      {/* Header: Class Title & 1-Click Action */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center space-x-1.5 min-w-0">
          <Sparkles className="w-4 h-4 text-purple-400 animate-pulse flex-shrink-0" />
          <h3 className="text-sm font-bold text-slate-100 truncate">
            {profile.class_title}
          </h3>
        </div>
        <button
          onClick={onOpenProposal}
          className="flex items-center space-x-1.5 px-2.5 py-1 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white rounded-lg text-[10.5px] font-semibold shadow transition-all cursor-pointer flex-shrink-0"
          title="Open STScI APT Observing Proposal Generator"
        >
          <FileText className="w-3 h-3" />
          <span>JWST Proposal</span>
        </button>
      </div>

      {/* Observed Phenomenon */}
      <p className="text-[11px] text-purple-200/90 font-mono leading-relaxed">
        {profile.observed_phenomenon}
      </p>

      {/* Competing Scientific Hypotheses: Compact Side-by-Side Grid */}
      <div className="grid grid-cols-2 gap-2 text-xs">
        {/* Leading Hypothesis A */}
        <div className="bg-cosmos-950/90 p-2.5 rounded-lg border border-purple-800/40 space-y-1">
          <div className="text-[10px] font-semibold text-emerald-400 flex items-center space-x-1">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 flex-shrink-0" />
            <span className="truncate">Hypothesis A (Leading)</span>
          </div>
          <p className="text-[11px] text-slate-300 leading-relaxed">
            {profile.hypotheses.primary}
          </p>
        </div>

        {/* Alternative Hypothesis B */}
        <div className="bg-cosmos-950/90 p-2.5 rounded-lg border border-cosmos-800 space-y-1">
          <div className="text-[10px] font-semibold text-amber-400 flex items-center space-x-1">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400 flex-shrink-0" />
            <span className="truncate">Hypothesis B (Alternative)</span>
          </div>
          <p className="text-[11px] text-slate-300 leading-relaxed">
            {profile.hypotheses.alternative}
          </p>
        </div>
      </div>

      {/* Recommended Follow-up Footer */}
      <div className="flex items-center justify-between text-[11px] text-purple-300/90 pt-1 border-t border-purple-900/40">
        <div className="truncate">
          <span className="text-slate-400">Target Follow-up:</span>{' '}
          <span className="font-mono text-cyan-300 font-semibold">{profile.jwst_followup.instrument} ({profile.jwst_followup.mode})</span>
        </div>
        <span className="text-[10px] font-mono text-purple-400/80 flex-shrink-0 pl-1">{profile.rarity_percentile}</span>
      </div>
    </div>
  );
};
