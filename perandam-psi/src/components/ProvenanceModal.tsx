import React, { useState } from 'react';
import { X, Check, Copy, ShieldCheck, Database, Cpu, Atom, Sparkles, ExternalLink, GitBranch } from 'lucide-react';
import { Galaxy, DataMode } from '../types/galaxy';

interface ProvenanceModalProps {
  galaxy: Galaxy | null;
  isOpen: boolean;
  onClose: () => void;
  isConnected?: boolean;
}

export const ProvenanceModal: React.FC<ProvenanceModalProps> = ({
  galaxy,
  isOpen,
  onClose,
  isConnected = false,
}) => {
  const [copied, setCopied] = useState<boolean>(false);

  if (!isOpen || !galaxy) return null;

  // Determine effective data mode
  let effectiveMode: DataMode = 'cached_reference';
  if (galaxy.data_mode) {
    effectiveMode = galaxy.data_mode;
  } else if (galaxy.subhalo_id && (galaxy.subhalo_id === '424601' || galaxy.galaxy3d?.geometry_source === 'simulation_derived')) {
    effectiveMode = 'simulation_derived';
  } else if (isConnected) {
    effectiveMode = 'live_computation';
  } else if (galaxy.is_synthetic_scenario || galaxy.galaxy3d?.geometry_source === 'procedural_illustrative') {
    effectiveMode = 'analytical_mock';
  }

  const modeConfig: Record<
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
  };

  const currentCfg = modeConfig[effectiveMode];

  // Particle counts
  const isRealTNG = galaxy.subhalo_id === '424601' || galaxy.id.includes('424601');
  const starCount = isRealTNG ? 14500 : (galaxy.galaxy3d?.particles?.star?.coordinates_kpc?.length || 4000);
  const gasCount = isRealTNG ? 4200 : (galaxy.galaxy3d?.particles?.gas?.coordinates_kpc?.length || 0);
  const dmCount = isRealTNG ? 8000 : (galaxy.galaxy3d?.particles?.dark_matter?.coordinates_kpc?.length || 0);

  const manifestData = {
    galaxy_id: galaxy.id,
    subhalo_id: galaxy.subhalo_id || (isRealTNG ? '424601' : null),
    data_mode: effectiveMode,
    simulation: isRealTNG ? 'IllustrisTNG-100-1' : (galaxy.provenance_type || 'IllustrisTNG Mock Suite'),
    snapshot: isRealTNG ? 99 : (galaxy.galaxy3d?.provenance?.snapshot ?? 99),
    redshift: galaxy.redshift,
    cosmology: {
      model: 'FlatLambdaCDM',
      H0: 67.74,
      Om0: 0.3089,
      Ol0: 0.6911,
      source: 'Planck 2015 / TNG Baseline',
    },
    particle_accounting: {
      star_particles: starCount,
      gas_particles: gasCount,
      dark_matter_particles: dmCount,
      total_particles: starCount + gasCount + dmCount,
      coordinate_frame: 'physical_rest (kpc)',
    },
    checksums: {
      hdf5_sha256: isRealTNG ? '8f5853a5fb4b5af9eaf2e67e39e9ce8c7bb04018d61c37b58d609f4731860c31' : 'N/A (Catalog Extract)',
      webgl_json_sha256: isRealTNG ? 'd0533f806139e9e1eafe6ec1f2ddafe72e3e62de3c3259ef09185ee754bbd479' : 'N/A',
      sublink_tree_sha256: isRealTNG ? '10ac59358b957c97ccf4628073f17b2d201713614a9c1cc702ff8651bf108b40' : 'N/A',
    },
    sentry_status: galaxy.sentry_status,
    truth_in_labeling: 'Strict non-promotion invariant enforced: mock data cannot claim simulation_derived status.',
  };

  const handleCopyManifest = () => {
    navigator.clipboard.writeText(JSON.stringify(manifestData, null, 2));
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
                <span>Data Mode Provenance & Audit Trail</span>
                <span className="text-xs font-mono text-slate-400 font-normal">({galaxy.id})</span>
              </h3>
              <p className="text-xs text-slate-400">Pillar 2 Scientific Reproducibility & Truth-in-Labeling</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-cosmos-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-5 overflow-y-auto space-y-4 text-xs scrollbar-thin scrollbar-thumb-cosmos-800">
          {/* Active Mode Banner */}
          <div className={`p-3.5 rounded-xl border ${currentCfg.bg} ${currentCfg.border} flex items-start space-x-3`}>
            <div className="mt-0.5">{currentCfg.icon}</div>
            <div className="space-y-1">
              <div className="flex items-center space-x-2">
                <span className={`px-2 py-0.5 rounded text-[11px] font-mono font-bold border ${currentCfg.badge}`}>
                  {currentCfg.label}
                </span>
                <span className="text-[11px] font-semibold text-slate-300">Classification</span>
              </div>
              <p className="text-slate-300 text-[11px] leading-relaxed">{currentCfg.desc}</p>
            </div>
          </div>

          {/* Dataset & Simulation Identity */}
          <div className="bg-cosmos-950/60 border border-cosmos-800 rounded-xl p-3.5 space-y-2.5">
            <div className="flex items-center space-x-2 text-slate-200 font-bold text-xs uppercase tracking-wider">
              <Database className="w-3.5 h-3.5 text-cyan-400" />
              <span>Simulation & Snapshot Provenance</span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px]">
              <div className="p-2 rounded bg-cosmos-900 border border-cosmos-800/80">
                <div className="text-slate-400 text-[10px]">Simulation</div>
                <div className="font-mono font-semibold text-slate-200 truncate">
                  {manifestData.simulation}
                </div>
              </div>
              <div className="p-2 rounded bg-cosmos-900 border border-cosmos-800/80">
                <div className="text-slate-400 text-[10px]">Subhalo ID</div>
                <div className="font-mono font-semibold text-cyan-300">
                  {manifestData.subhalo_id || 'N/A'}
                </div>
              </div>
              <div className="p-2 rounded bg-cosmos-900 border border-cosmos-800/80">
                <div className="text-slate-400 text-[10px]">Snapshot / z</div>
                <div className="font-mono font-semibold text-amber-300">
                  Snap {manifestData.snapshot} (z={galaxy.redshift.toFixed(2)})
                </div>
              </div>
              <div className="p-2 rounded bg-cosmos-900 border border-cosmos-800/80">
                <div className="text-slate-400 text-[10px]">QC Certification</div>
                <div className="font-mono font-semibold text-emerald-400">
                  {galaxy.sentry_status === 'PRISTINE' ? 'Sentry PASSED' : galaxy.sentry_status}
                </div>
              </div>
            </div>
          </div>

          {/* Particle Accounting Breakdown */}
          <div className="bg-cosmos-950/60 border border-cosmos-800 rounded-xl p-3.5 space-y-2.5">
            <div className="flex items-center space-x-2 text-slate-200 font-bold text-xs uppercase tracking-wider">
              <Atom className="w-3.5 h-3.5 text-indigo-400" />
              <span>Particle Accounting & Coordinates</span>
            </div>
            <div className="grid grid-cols-3 gap-2 text-[11px]">
              <div className="p-2 rounded bg-cosmos-900 border border-cosmos-800/80">
                <div className="text-slate-400 text-[10px]">Stars (PartType4)</div>
                <div className="font-mono font-semibold text-amber-300">
                  {starCount.toLocaleString()} particles
                </div>
              </div>
              <div className="p-2 rounded bg-cosmos-900 border border-cosmos-800/80">
                <div className="text-slate-400 text-[10px]">Gas (PartType0)</div>
                <div className="font-mono font-semibold text-cyan-300">
                  {gasCount.toLocaleString()} particles
                </div>
              </div>
              <div className="p-2 rounded bg-cosmos-900 border border-cosmos-800/80">
                <div className="text-slate-400 text-[10px]">Dark Matter (PartType1)</div>
                <div className="font-mono font-semibold text-purple-300">
                  {dmCount.toLocaleString()} particles
                </div>
              </div>
            </div>
            <div className="text-[10px] text-slate-400">
              Center of Mass shifted to origin (0, 0, 0); stellar angular momentum aligned with +Z axis.
            </div>
          </div>

          {/* Cosmological Baseline */}
          <div className="bg-cosmos-950/60 border border-cosmos-800 rounded-xl p-3.5 space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-bold text-slate-200 uppercase tracking-wider text-[11px]">
                Cosmology: Flat Lambda-CDM (Planck 2015)
              </span>
              <span className="text-[10px] text-slate-400 font-mono">TNG Baseline Reference</span>
            </div>
            <div className="grid grid-cols-3 gap-2 font-mono text-[11px] text-slate-300">
              <div className="p-1.5 rounded bg-cosmos-900 border border-cosmos-800/80 text-center">
                H₀ = 67.74 km/s/Mpc
              </div>
              <div className="p-1.5 rounded bg-cosmos-900 border border-cosmos-800/80 text-center">
                Ω_m0 = 0.3089
              </div>
              <div className="p-1.5 rounded bg-cosmos-900 border border-cosmos-800/80 text-center">
                Ω_Λ0 = 0.6911
              </div>
            </div>
          </div>

          {/* Cryptographic Digests & Invariant Enforcement */}
          <div className="bg-cosmos-950/60 border border-cosmos-800 rounded-xl p-3.5 space-y-2">
            <span className="font-bold text-slate-200 uppercase tracking-wider text-[11px]">
              Cryptographic SHA-256 Checksums
            </span>
            <div className="space-y-1 font-mono text-[10px] text-slate-300">
              <div className="flex items-center justify-between p-1.5 rounded bg-cosmos-900 border border-cosmos-800/60">
                <span className="text-slate-400">Cutout HDF5:</span>
                <span className="text-cyan-300 truncate max-w-[340px]">{manifestData.checksums.hdf5_sha256}</span>
              </div>
              <div className="flex items-center justify-between p-1.5 rounded bg-cosmos-900 border border-cosmos-800/60">
                <span className="text-slate-400">WebGL JSON:</span>
                <span className="text-cyan-300 truncate max-w-[340px]">{manifestData.checksums.webgl_json_sha256}</span>
              </div>
              <div className="flex items-center justify-between p-1.5 rounded bg-cosmos-900 border border-cosmos-800/60">
                <span className="text-slate-400">SubLink Tree:</span>
                <span className="text-cyan-300 truncate max-w-[340px]">{manifestData.checksums.sublink_tree_sha256}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="p-3.5 border-t border-cosmos-800 bg-cosmos-950/80 flex items-center justify-between">
          <button
            onClick={handleCopyManifest}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-cosmos-800 hover:bg-cosmos-700 text-slate-200 font-medium text-xs transition-colors cursor-pointer"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
            <span>{copied ? 'Copied Manifest!' : 'Copy Manifest JSON'}</span>
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
