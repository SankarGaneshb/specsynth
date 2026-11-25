export type SkyColorMode = 'rgb' | 'redshift' | 'ssfr' | 'mass';
export type ViewportMode = '2d' | 'twin' | '3d';

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

export interface Galaxy {
  id: string;
  subhalo_id?: string;
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
