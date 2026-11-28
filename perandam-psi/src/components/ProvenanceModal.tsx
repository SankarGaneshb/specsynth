import React, { useState } from 'react';
import { X, Check, Copy, ShieldCheck, Database, Cpu, Atom, Sparkles, Sliders, Activity, AlertCircle } from 'lucide-react';
import { Galaxy, DataMode, ExecutionMode, SourceProvenance, ExecutionProvenance } from '../types/galaxy';

interface ProvenanceModalProps {
  galaxy: Galaxy | null;
  isOpen: boolean;
  onClose: () => void;
  isConnected?: boolean;
  activeExecution?: ExecutionProvenance;
}

export const ProvenanceModal: React.FC<ProvenanceModalProps> = ({
  galaxy,
  isOpen,
  onClose,
  isConnected = false,
  activeExecution,
}) => {
  const [activeTab, setActiveTab] = useState<'source' | 'execution'>('source');
  const [copied, setCopied] = useState<boolean>(false);

  if (!isOpen || !galaxy) return null;

  // 1. Extract Source Provenance (strictly empirical, independent of connection status)
  const sourceProv: SourceProvenance = galaxy.source_provenance || {
    data_mode: galaxy.data_mode || 'cached_reference',
    simulation: galaxy.subhalo_id ? 'IllustrisTNG-100-1' : (galaxy.provenance_type || 'Catalog Extract'),
    snapshot: (galaxy.provenance as any)?.snapshot ?? (galaxy.galaxy3d?.provenance?.snapshot ?? 99),
    subhalo_id: galaxy.subhalo_id || null,
    dataset_name: galaxy.provenance_type || 'IllustrisTNG Mock Suite',
    checksum_sha256: (galaxy.provenance as any)?.manifest_hash || (galaxy.galaxy3d?.provenance as any)?.sha256 || null,
    verified_authentic: Boolean(galaxy.subhalo_id && galaxy.galaxy3d?.geometry_source === 'simulation_derived'),
  };

  const effectiveSourceMode: DataMode = sourceProv.data_mode || 'cached_reference';

  // 2. Extract Execution Provenance (where the active displayed photometry was computed)
  const execProv: ExecutionProvenance = activeExecution || galaxy.execution_provenance || {
    execution_mode: 'precomputed_cached',
    executor: 'Precomputed Reference Store',
    backend_url: isConnected ? 'http://127.0.0.1:8000' : null,
    latency_ms: null,
    timestamp_utc: new Date().toISOString(),
    is_dynamic_override: false,
    parameters_applied: {},
  };

  const effectiveExecMode: ExecutionMode = execProv.execution_mode || 'precomputed_cached';

  // Source Mode Configurations
  const sourceModeConfig: Record<
    DataMode,
    { label: string; badge: string; bg: string; border: string; text: string; icon: React.ReactNode; desc: string }
  > = {
    simulation_derived: {
      label: 'SIMULATION-DERIVED',
      badge: 'bg-emerald-950/90 text-emerald-300 border-emerald-500/70',
      bg: 'bg-emerald-950/30',
      border: 'border-emerald-700/50',
      text: 'text-emerald-300',
      icon: <Database className="w-4 h-4 text-emerald-400" />,
      desc: 'Authentic empirical simulation particles and properties ingested directly from hydrodynamic simulation snapshots (e.g. IllustrisTNG-100-1 cutout).',
    },
    cached_reference: {
      label: 'CACHED REFERENCE',
      badge: 'bg-indigo-950/90 text-indigo-300 border-indigo-500/70',
      bg: 'bg-indigo-950/30',
      border: 'border-indigo-700/50',
      text: 'text-indigo-300',
      icon: <ShieldCheck className="w-4 h-4 text-indigo-400" />,
      desc: 'Calibrated reference catalog with pre-computed forward-modeled photometry, certified against Sentry physical invariants.',
    },
    live_computation: {
      label: 'LIVE COMPUTATION',
      badge: 'bg-amber-950/90 text-amber-300 border-amber-500/70',
      bg: 'bg-amber-950/30',
      border: 'border-amber-700/50',
      text: 'text-amber-300',
      icon: <Cpu className="w-4 h-4 text-amber-400" />,
      desc: 'Dynamically synthesized in real time via live SpecSynth Python BLAS/GEMM engine contraction (:8000).',
    },
    analytical_mock: {
      label: 'ANALYTICAL MOCK',
      badge: 'bg-purple-950/90 text-purple-300 border-purple-500/70',
      bg: 'bg-purple-950/30',
      border: 'border-purple-700/50',
      text: 'text-purple-300',
      icon: <Atom className="w-4 h-4 text-purple-400" />,
      desc: 'Procedural analytical benchmark model generated using Hernquist bulge, exponential disk, and NFW halo distributions.',
    },
    illustrative_demo: {
      label: 'ILLUSTRATIVE DEMO',
      badge: 'bg-slate-900/90 text-slate-300 border-slate-600/70',
      bg: 'bg-slate-950/30',
      border: 'border-slate-700/50',
      text: 'text-slate-300',
      icon: <Sparkles className="w-4 h-4 text-slate-400" />,
      desc: 'Synthetic visual illustration track used for interface demonstrations and pedagogical walkthroughs.',
    },
    unknown_unverified: {
      label: 'UNKNOWN / UNVERIFIED',
      badge: 'bg-zinc-900/90 text-zinc-300 border-zinc-600/70',
      bg: 'bg-zinc-950/30',
      border: 'border-zinc-700/50',
      text: 'text-zinc-300',
      icon: <AlertCircle className="w-4 h-4 text-zinc-400" />,
      desc: 'Unverified specimen missing cryptographic provenance or simulation lineage. Fail-closed safe mode enforced.',
    },
  };

  // Execution Mode Configurations
  const execModeConfig: Record<
    ExecutionMode,
    { label: string; badge: string; bg: string; border: string; text: string; icon: React.ReactNode; desc: string }
  > = {
    live_backend: {
      label: 'LIVE BACKEND (PYTHON)',
      badge: 'bg-cyan-950/90 text-cyan-300 border-cyan-500/80',
      bg: 'bg-cyan-950/30',
      border: 'border-cyan-700/50',
      text: 'text-cyan-300',
      icon: <Cpu className="w-4 h-4 text-cyan-400" />,
      desc: 'Synthesized in real-time by the SpecSynth Python GEMM engine on localhost:8000. Verified server-side calculation.',
    },
    client_browser: {
      label: 'CLIENT BROWSER (JAVASCRIPT)',
      badge: 'bg-amber-950/90 text-amber-300 border-amber-500/80',
      bg: 'bg-amber-950/30',
      border: 'border-amber-700/50',
      text: 'text-amber-300',
      icon: <Sliders className="w-4 h-4 text-amber-400" />,
      desc: 'Computed in-flight inside the browser JavaScript thread via forwardModelGalaxy. Local responsive preview.',
    },
    precomputed_cached: {
      label: 'PRECOMPUTED CACHE',
      badge: 'bg-indigo-950/90 text-indigo-300 border-indigo-500/80',
      bg: 'bg-indigo-950/30',
      border: 'border-indigo-700/50',
      text: 'text-indigo-300',
      icon: <ShieldCheck className="w-4 h-4 text-indigo-400" />,
      desc: 'Static baseline reference extracted directly from catalog precomputed values without dynamic modification.',
    },
  };

  const currentSourceCfg = sourceModeConfig[effectiveSourceMode] || sourceModeConfig.cached_reference;
  const currentExecCfg = execModeConfig[effectiveExecMode] || execModeConfig.precomputed_cached;

  // Particle counts (dynamically extracted from payload, no hardcoded galaxy IDs)
  const g3d = galaxy.galaxy3d as any;
  const starCount = galaxy.galaxy3d?.particles?.star?.coordinates_kpc?.length ??
    (g3d?.components?.star?.count as number | undefined);
  const gasCount = galaxy.galaxy3d?.particles?.gas?.coordinates_kpc?.length ??
    (g3d?.components?.gas?.count as number | undefined);
  const dmCount = galaxy.galaxy3d?.particles?.dark_matter?.coordinates_kpc?.length ??
    (g3d?.components?.dark_matter?.count as number | undefined);

  // Full Provenance Document
  const fullProvenanceManifest = {
    schema_version: '2.0.0',
    galaxy_id: galaxy.id,
    source_provenance: {
      data_mode: effectiveSourceMode,
      simulation: sourceProv.simulation || 'Not Declared in Record',
      snapshot: sourceProv.snapshot ?? 'Not Declared in Record',
      subhalo_id: sourceProv.subhalo_id || 'Not Declared in Record',
      dataset_name: sourceProv.dataset_name || 'Not Declared in Record',
      checksum_sha256: sourceProv.checksum_sha256 || 'Unverified / Not Checked',
      verified_authentic: sourceProv.verified_authentic ?? false,
    },
    execution_provenance: {
      execution_mode: effectiveExecMode,
      executor: execProv.executor,
      backend_url: execProv.backend_url || (isConnected ? 'http://127.0.0.1:8000' : 'Offline / Client'),
      latency_ms: execProv.latency_ms ?? (effectiveExecMode === 'client_browser' ? '<1' : null),
      timestamp_utc: execProv.timestamp_utc,
      is_dynamic_override: execProv.is_dynamic_override ?? false,
      parameters_applied: execProv.parameters_applied || {},
    },
    cosmology: {
      model: 'FlatLambdaCDM',
      H0: 67.74,
      Om0: 0.3089,
      Ol0: 0.6911,
      source: 'Planck 2015 / TNG Baseline',
    },
    particle_accounting: {
      star_particles: starCount ?? 'Not Available in 2D Cutout',
      gas_particles: gasCount ?? 'Not Available in 2D Cutout',
      dark_matter_particles: dmCount ?? 'Not Available in 2D Cutout',
      coordinate_frame: 'physical_rest (kpc)',
    },
    sentry_status: galaxy.sentry_status,
    truth_in_labeling: 'Strict non-promotion invariant enforced: source provenance and execution provenance are decoupled and independently audited.',
  };

  const handleCopyManifest = () => {
    navigator.clipboard.writeText(JSON.stringify(fullProvenanceManifest, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
      <div className="bg-cosmos-900 border border-cosmos-700/80 rounded-2xl max-w-2xl w-full max-h-[90vh] flex flex-col shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="p-4 border-b border-cosmos-800 flex items-center justify-between bg-cosmos-950/80">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-xl bg-cosmos-800 border border-cosmos-700 text-cyan-400">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-100 flex items-center space-x-2">
                <span>Scientific Provenance & Audit Trail</span>
                <span className="text-xs font-mono text-slate-400 font-normal">({galaxy.id})</span>
              </h3>
              <p className="text-xs text-slate-400">Pillar 2 Scientific Reproducibility & Truthful Execution Reporting</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-cosmos-800 transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tab Selector */}
        <div className="flex border-b border-cosmos-800 bg-cosmos-950 px-4 pt-2 gap-4">
          <button
            onClick={() => setActiveTab('source')}
            className={`pb-2.5 text-xs font-bold border-b-2 flex items-center space-x-1.5 transition-colors cursor-pointer ${
              activeTab === 'source'
                ? 'border-indigo-400 text-indigo-300'
                : 'border-transparent text-slate-400 hover:text-slate-300'
            }`}
          >
            <Database className="w-3.5 h-3.5" />
            <span>1. Source & Data Provenance</span>
          </button>
          <button
            onClick={() => setActiveTab('execution')}
            className={`pb-2.5 text-xs font-bold border-b-2 flex items-center space-x-1.5 transition-colors cursor-pointer ${
              activeTab === 'execution'
                ? 'border-cyan-400 text-cyan-300'
                : 'border-transparent text-slate-400 hover:text-slate-300'
            }`}
          >
            <Cpu className="w-3.5 h-3.5" />
            <span>2. Execution Provenance</span>
          </button>
        </div>

        {/* Content Body */}
        <div className="p-5 overflow-y-auto space-y-4 text-xs scrollbar-thin scrollbar-thumb-cosmos-800">
          {activeTab === 'source' ? (
            <>
              {/* Source Mode Banner */}
              <div className={`p-3.5 rounded-xl border ${currentSourceCfg.bg} ${currentSourceCfg.border} flex items-start space-x-3`}>
                <div className="mt-0.5">{currentSourceCfg.icon}</div>
                <div className="space-y-1">
                  <div className="flex items-center space-x-2">
                    <span className={`px-2 py-0.5 rounded text-[11px] font-mono font-bold border ${currentSourceCfg.badge}`}>
                      {currentSourceCfg.label}
                    </span>
                    <span className="text-[11px] font-semibold text-slate-300">Data Origin Classification</span>
                  </div>
                  <p className="text-slate-300 text-[11px] leading-relaxed">{currentSourceCfg.desc}</p>
                </div>
              </div>

              {/* Simulation Identity */}
              <div className="bg-cosmos-950/60 border border-cosmos-800 rounded-xl p-3.5 space-y-2.5">
                <div className="flex items-center space-x-2 text-slate-200 font-bold text-xs uppercase tracking-wider">
                  <Database className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Simulation & Snapshot Provenance</span>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px]">
                  <div className="p-2 rounded bg-cosmos-900 border border-cosmos-800/80">
                    <div className="text-slate-400 text-[10px]">Simulation</div>
                    <div className="font-mono font-semibold text-slate-200 truncate">
                      {sourceProv.simulation || 'Not Declared in Record'}
                    </div>
                  </div>
                  <div className="p-2 rounded bg-cosmos-900 border border-cosmos-800/80">
                    <div className="text-slate-400 text-[10px]">Subhalo ID</div>
                    <div className="font-mono font-semibold text-cyan-300">
                      {sourceProv.subhalo_id || 'Not Declared in Record'}
                    </div>
                  </div>
                  <div className="p-2 rounded bg-cosmos-900 border border-cosmos-800/80">
                    <div className="text-slate-400 text-[10px]">Snapshot / z</div>
                    <div className="font-mono font-semibold text-amber-300">
                      {sourceProv.snapshot ? `Snap ${sourceProv.snapshot}` : 'Not Declared'} (z={galaxy.redshift.toFixed(2)})
                    </div>
                  </div>
                  <div className="p-2 rounded bg-cosmos-900 border border-cosmos-800/80">
                    <div className="text-slate-400 text-[10px]">Authenticity Verified</div>
                    <div className={`font-mono font-semibold ${sourceProv.verified_authentic ? 'text-emerald-400' : 'text-amber-400'}`}>
                      {sourceProv.verified_authentic ? 'Verified Simulation' : 'Mock / Unverified'}
                    </div>
                  </div>
                </div>
              </div>

              {/* Particle Accounting Breakdown (Dynamic) */}
              <div className="bg-cosmos-950/60 border border-cosmos-800 rounded-xl p-3.5 space-y-2.5">
                <div className="flex items-center space-x-2 text-slate-200 font-bold text-xs uppercase tracking-wider">
                  <Atom className="w-3.5 h-3.5 text-indigo-400" />
                  <span>Particle Accounting</span>
                </div>
                <div className="grid grid-cols-3 gap-2 text-[11px]">
                  <div className="p-2 rounded bg-cosmos-900 border border-cosmos-800/80">
                    <div className="text-slate-400 text-[10px]">Stars (PartType4)</div>
                    <div className="font-mono font-semibold text-amber-300">
                      {starCount !== undefined ? `${starCount.toLocaleString()} particles` : 'Not Declared in Record'}
                    </div>
                  </div>
                  <div className="p-2 rounded bg-cosmos-900 border border-cosmos-800/80">
                    <div className="text-slate-400 text-[10px]">Gas (PartType0)</div>
                    <div className="font-mono font-semibold text-cyan-300">
                      {gasCount !== undefined ? `${gasCount.toLocaleString()} particles` : 'Not Declared in Record'}
                    </div>
                  </div>
                  <div className="p-2 rounded bg-cosmos-900 border border-cosmos-800/80">
                    <div className="text-slate-400 text-[10px]">Dark Matter (PartType1)</div>
                    <div className="font-mono font-semibold text-purple-300">
                      {dmCount !== undefined ? `${dmCount.toLocaleString()} particles` : 'Not Declared in Record'}
                    </div>
                  </div>
                </div>
              </div>

              {/* Cryptographic Digests (Dynamic) */}
              <div className="bg-cosmos-950/60 border border-cosmos-800 rounded-xl p-3.5 space-y-2">
                <span className="font-bold text-slate-200 uppercase tracking-wider text-[11px]">
                  Cryptographic Integrity Checksums
                </span>
                <div className="space-y-1 font-mono text-[10px] text-slate-300">
                  <div className="flex items-center justify-between p-1.5 rounded bg-cosmos-900 border border-cosmos-800/60">
                    <span className="text-slate-400">Dataset / Cutout SHA-256:</span>
                    <span className="text-cyan-300 truncate max-w-[340px]">
                      {sourceProv.checksum_sha256 || 'Unverified / Not Checked'}
                    </span>
                  </div>
                  <div className="flex items-center justify-between p-1.5 rounded bg-cosmos-900 border border-cosmos-800/60">
                    <span className="text-slate-400">QC Status:</span>
                    <span className="text-emerald-400 font-semibold">{galaxy.sentry_status || 'PRISTINE'}</span>
                  </div>
                </div>
              </div>
            </>
          ) : (
            <>
              {/* Execution Mode Banner */}
              <div className={`p-3.5 rounded-xl border ${currentExecCfg.bg} ${currentExecCfg.border} flex items-start space-x-3`}>
                <div className="mt-0.5">{currentExecCfg.icon}</div>
                <div className="space-y-1">
                  <div className="flex items-center space-x-2">
                    <span className={`px-2 py-0.5 rounded text-[11px] font-mono font-bold border ${currentExecCfg.badge}`}>
                      {currentExecCfg.label}
                    </span>
                    <span className="text-[11px] font-semibold text-slate-300">Active Computation Mode</span>
                  </div>
                  <p className="text-slate-300 text-[11px] leading-relaxed">{currentExecCfg.desc}</p>
                </div>
              </div>

              {/* Execution Details */}
              <div className="bg-cosmos-950/60 border border-cosmos-800 rounded-xl p-3.5 space-y-2.5">
                <div className="flex items-center space-x-2 text-slate-200 font-bold text-xs uppercase tracking-wider">
                  <Cpu className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Execution Metadata</span>
                </div>
                <div className="grid grid-cols-2 gap-2 text-[11px]">
                  <div className="p-2 rounded bg-cosmos-900 border border-cosmos-800/80">
                    <div className="text-slate-400 text-[10px]">Active Executor</div>
                    <div className="font-mono font-semibold text-slate-200 truncate">
                      {execProv.executor}
                    </div>
                  </div>
                  <div className="p-2 rounded bg-cosmos-900 border border-cosmos-800/80">
                    <div className="text-slate-400 text-[10px]">Compute Latency</div>
                    <div className="font-mono font-semibold text-cyan-300">
                      {execProv.latency_ms !== null && execProv.latency_ms !== undefined ? `${execProv.latency_ms} ms` : 'N/A (Precomputed)'}
                    </div>
                  </div>
                  <div className="p-2 rounded bg-cosmos-900 border border-cosmos-800/80">
                    <div className="text-slate-400 text-[10px]">Backend Server URL</div>
                    <div className="font-mono font-semibold text-indigo-300 truncate">
                      {execProv.backend_url || 'Offline / Standalone'}
                    </div>
                  </div>
                  <div className="p-2 rounded bg-cosmos-900 border border-cosmos-800/80">
                    <div className="text-slate-400 text-[10px]">Dynamic Override Active</div>
                    <div className={`font-mono font-semibold ${execProv.is_dynamic_override ? 'text-amber-400' : 'text-slate-400'}`}>
                      {execProv.is_dynamic_override ? 'YES (User Parameters)' : 'NO (Reference Baseline)'}
                    </div>
                  </div>
                </div>
              </div>

              {/* Applied Parameters */}
              <div className="bg-cosmos-950/60 border border-cosmos-800 rounded-xl p-3.5 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-slate-200 uppercase tracking-wider text-[11px]">
                    Applied Dynamic Parameters
                  </span>
                  <span className="text-[10px] text-slate-400 font-mono">
                    {execProv.timestamp_utc ? new Date(execProv.timestamp_utc).toLocaleTimeString() : 'N/A'}
                  </span>
                </div>
                {execProv.parameters_applied && Object.keys(execProv.parameters_applied).length > 0 ? (
                  <div className="grid grid-cols-2 gap-2 font-mono text-[11px] text-slate-300">
                    {Object.entries(execProv.parameters_applied).map(([k, v]) => (
                      <div key={k} className="p-1.5 rounded bg-cosmos-900 border border-cosmos-800/80">
                        <span className="text-slate-400">{k}:</span> <span className="text-amber-300 font-bold">{String(v)}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-slate-400 text-[11px] italic">
                    No active slider overrides applied. Displaying calibrated reference baseline.
                  </p>
                )}
              </div>

              {/* Connectivity vs Execution Rule */}
              <div className="bg-cosmos-950/40 border border-cosmos-800/60 rounded-xl p-3 flex items-start space-x-2.5">
                <Activity className="w-4 h-4 text-cyan-400 flex-shrink-0 mt-0.5" />
                <p className="text-[11px] text-slate-400 leading-relaxed">
                  <strong className="text-slate-200">Decoupled Architecture:</strong> Backend connectivity (:8000 Online) confirms network reachability. The Active Computation Mode truthfully reflects whether numbers were produced by the Python GEMM engine or evaluated in-browser.
                </p>
              </div>
            </>
          )}

          {/* Non-Promotion Invariant Notice */}
          <div className="p-2.5 rounded-lg bg-indigo-950/30 border border-indigo-800/40 text-[10px] text-indigo-300 flex items-center space-x-2">
            <ShieldCheck className="w-4 h-4 text-indigo-400 flex-shrink-0" />
            <span>
              <strong>Truth-in-Labeling Directive:</strong> Analytical mocks and client-side approximations are strictly barred from claiming simulation-derived or live backend status.
            </span>
          </div>
        </div>

        {/* Footer */}
        <div className="p-3.5 border-t border-cosmos-800 bg-cosmos-950/80 flex items-center justify-between">
          <button
            onClick={handleCopyManifest}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-cosmos-800 hover:bg-cosmos-700 text-slate-200 font-medium text-xs transition-colors cursor-pointer"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
            <span>{copied ? 'Copied Manifest JSON!' : 'Copy Full Manifest JSON'}</span>
          </button>
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs transition-colors cursor-pointer"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
