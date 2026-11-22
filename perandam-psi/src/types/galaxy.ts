export type SkyColorMode = 'rgb' | 'redshift' | 'ssfr' | 'mass';

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
  rarity_sigma: number; // Statistical distance from cosmological median (e.g. 4.6σ)
  rarity_percentile: string; // e.g. "Top 0.1% Extreme"
  observed_phenomenon: string; // Quantitative photometric signature
  hypotheses: {
    primary: string; // Leading astrophysical interpretation
    alternative: string; // Competing physical mechanism
  };
  spectral_excess?: {
    band: string; // e.g. "jwst_f444w"
    excess_factor: number; // e.g. 3.2x stellar continuum
    mechanism: string; // e.g. "Supermassive black hole accretion torus"
  };
  jwst_followup: {
    instrument: 'NIRSpec' | 'MIRI' | 'NIRCam Wide-Field Slitless';
    mode: 'PRISM / CLEAR' | 'G395H / F290LP' | 'F444W Grism';
    exposure_time_s: number;
    science_goal: string;
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
}

export interface Galaxy {
  id: string;
  ra: number;
  dec: number;
  redshift: number;
  stellar_mass: number;
  log_mstar: number;
  sfr: number;
  av: number;
  tau_diffuse: number;
  tau_birth: number;
  sentry_status: 'PRISTINE' | 'ANOMALY';
  qc_failure_code?: string;
  qc_failure_title?: string;
  qc_failure_detail?: string;
  rarity_score?: number; // Multi-dimensional σ-distance from cosmological median
  discovery_profile?: DiscoveryProfile;
  fluxes: Record<string, number>;
  mags: Record<string, number>;
  apparent_mag: number;
  sed: SedPoint[];
}

export interface CatalogManifest {
  title: string;
  description: string;
  field_center: {
    ra: number;
    dec: number;
    radius_deg: number;
  };
  filters: FilterCurveData[];
  n_galaxies: number;
  sentry_certified: boolean;
  galaxies: Galaxy[];
}
