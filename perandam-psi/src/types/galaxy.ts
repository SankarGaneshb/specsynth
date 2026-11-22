export type SkyColorMode = 'rgb' | 'redshift' | 'ssfr' | 'mass';

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
