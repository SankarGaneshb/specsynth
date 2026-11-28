export type SkyColorMode = 'rgb' | 'redshift' | 'ssfr' | 'mass';
export type ViewportMode = '2d' | 'twin' | '3d';

export type DataMode =
  | 'simulation_derived'
  | 'cached_reference'
  | 'live_computation'
  | 'analytical_mock'
  | 'illustrative_demo'
  | 'unknown_unverified';

export type ExecutionMode = 'live_backend' | 'client_browser' | 'precomputed_cached';

export interface SourceProvenance {
  data_mode: DataMode;
  simulation?: string | null;
  snapshot?: number | string | null;
  subhalo_id?: number | string | null;
  dataset_name?: string | null;
  checksum_sha256?: string | null;
  catalog_file?: string | null;
  verified_authentic?: boolean;
}

export interface ExecutionProvenance {
  execution_mode: ExecutionMode;
  executor: string;
  backend_url?: string | null;
  latency_ms?: number | null;
  timestamp_utc: string;
  is_dynamic_override?: boolean;
  parameters_applied?: Record<string, any>;
}

export interface GalaxyProvenance {
  data_mode: DataMode;
  source?: string;
  simulation?: string;
  snapshot?: number | string;
  subhalo_id?: number | string;
  redshift?: number;
  cosmology?: {
    h0?: number;
    om0?: number;
    ol0?: number;
  };
  total_particles?: number;
  particle_counts?: {
    star?: number;
    gas?: number;
    dark_matter?: number;
  };
  physical_properties?: Record<string, any>;
  software_versions?: Record<string, string>;
  timestamp_utc?: string;
  git_sha?: string;
  manifest_hash?: string;
  sentry_certified?: boolean;
}

export type DiscoveryClass =
  | 'COSMIC_NOON_SUPER_STARBURST'
  | 'EARLY_QUENCHED_GIANT'
  | 'ANCIENT_MASSIVE_TITAN'
  | 'LITTLE_RED_DOT'
  | 'EXTREME_EMISSION_LINE'
  | 'HST_DARK_MONSTER';

export interface DiscoveryProfile {
  classification: DiscoveryClass;
  class_title: string;
  rarity_sigma: number; // Mahalanobis distance D_M
  rarity_chi2?: number; // χ²_6 statistic
  rarity_p_value?: number; // Analytical survival probability p-value
  rarity_percentile: string; // e.g. "Top 0.05% Frontier Discovery"
  observed_phenomenon: string; // Quantitative photometric signature
  hypotheses: {
    primary: string; // Leading astrophysical interpretation
    alternative: string; // Competing physical mechanism
    citations?: string[]; // Academic literature references
    confidence?: 'HIGH' | 'MEDIUM' | 'LOW';
    required_observations?: string; // Missing observations required to resolve ambiguity
  };
  spectral_excess?: {
    band: string; // e.g. "jwst_f444w"
    excess_factor: number; // e.g. 3.2x stellar continuum
    mechanism: string; // e.g. "Supermassive black hole accretion torus"
  };
  jwst_followup: {
    instrument: 'NIRSpec' | 'MIRI' | 'NIRCam Wide-Field Slitless' | 'NIRCam';
    mode: string;
    exposure_time_s: number;
    science_goal: string;
    target_acquisition?: string; // e.g. WATA acquisition constraint vs direct imaging
  };
}

export interface SedPoint {
  wave: number;
  flux: number;
}

export interface FilterCurveData {
  name: string;
  pivot_wavelength: number;
  wave: number[];
  transmission: number[];
  sha256?: string;
  throughput_source?: string;
}

export interface ParticleData3D {
  particle_type: 'star' | 'gas' | 'dark_matter' | 'black_hole';
  coordinates_kpc: number[][]; // [N, 3] in physical kpc
  masses_msun: number[]; // [N]
  velocities_km_s?: number[][]; // [N, 3]
  ages_yr?: number[]; // [N]
  metallicities_z?: number[]; // [N]
}

export interface ProgenitorNode {
  redshift: number;
  cosmic_time_gyr: number;
  lookback_time_gyr: number;
  comoving_coords_mpc: [number, number, number];
  physical_coords_kpc: [number, number, number];
  stellar_mass_msun: number;
  sfr_msun_per_yr: number;
  metallicity_z: number;
  half_mass_radius_kpc: number;
  photometry: Record<string, number>;
  sed?: SedPoint[];
  snapshot_id?: string | number;
  subhalo_id?: string | number;
}

export interface MergerEvent {
  redshift: number;
  lookback_time_gyr: number;
  mass_ratio: number;
  merger_type: 'major' | 'minor';
  secondary_galaxy_id: string;
}

export interface SplinePoint3D {
  x: number;
  y: number;
  z_coord: number;
  redshift: number;
  lookback_gyr: number;
}

export interface EvolutionaryTrack {
  version: string;
  galaxy_id: string;
  main_branch: ProgenitorNode[];
  mergers: MergerEvent[];
  spline_trajectory: SplinePoint3D[];
  provenance?: Record<string, any>;
}

export interface Galaxy3DModel {
  version: string;
  galaxy_id: string;
  data_mode?: DataMode;
  geometry_source: 'simulation_derived' | 'procedural_illustrative';
  coordinate_frame: 'physical_rest' | 'comoving_box' | 'observer_sky';
  redshift: number;
  center_of_mass_kpc: [number, number, number];
  half_mass_radius_kpc: number;
  total_stellar_mass_msun: number;
  particles: Record<string, ParticleData3D>;
  provenance?: {
    simulation?: string;
    snapshot?: number | string;
    subhalo_id?: number | string;
    redshift?: number;
    git_sha?: string;
    pipeline?: string;
    [key: string]: any;
  };
}

export interface Galaxy {
  id: string;
  subhalo_id?: string;
  data_mode?: DataMode;
  source_provenance?: SourceProvenance;
  execution_provenance?: ExecutionProvenance;
  provenance?: GalaxyProvenance | Record<string, any>;
  ra: number;
  dec: number;
  redshift: number;
  stellar_mass: number;
  log_mstar: number;
  sfr: number;
  av: number;
  tau_diffuse: number;
  tau_birth: number;
  t_onset?: number;
  tau?: number;
  metallicity?: number;
  is_synthetic_scenario?: boolean;
  provenance_type?: string;
  galaxy3d?: Galaxy3DModel;
  evolution_track?: EvolutionaryTrack;
  sentry_status: 'PRISTINE' | 'ANOMALY';
  qc_failure_code?: string;
  qc_failure_title?: string;
  qc_failure_detail?: string;
  rarity_score?: number; // Mahalanobis distance D_M
  rarity_chi2?: number;
  rarity_p_value?: number;
  rarity_percentile?: string;
  discovery_profile?: DiscoveryProfile;
  fluxes: Record<string, number>;
  mags: Record<string, number>;
  mag_errs?: Record<string, number>;
  snr?: Record<string, number>;
  apparent_mag: number;
  sed: SedPoint[];
}

export interface CatalogManifest {
  title: string;
  description: string;
  dataset_type?: string;
  ssp_model?: string;
  is_genuine_fsps?: boolean;
  coordinates_note?: string;
  provenance?: string;
  field_center: {
    ra: number;
    dec: number;
    radius_deg: number;
  };
  filters: FilterCurveData[];
  n_galaxies: number;
  n_discoveries?: number;
  n_anomalies?: number;
  sentry_certified: boolean;
  galaxies: Galaxy[];
}
