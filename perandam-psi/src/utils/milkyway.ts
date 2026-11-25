import type { Galaxy } from '../types/galaxy.ts';
import { lookbackTimeGyr } from './cosmo3d.ts';

/**
 * Standard Modern Milky Way Benchmark Parameters (z = 0, today).
 * References:
 *  - Bland-Hawthorn & Gerhard (2016), ARA&A 54, 529: "The Galaxy in Context"
 *  - Chomiuk & Povich (2011), AJ 142, 197: "Toward a Unification of Star Formation Rates"
 *  - Licquia & Newman (2015), ApJ 806, 96: "Improved Estimates of the Milky Way's Stellar Mass"
 */
export const MILKY_WAY_BENCHMARK = {
  name: 'Milky Way (Our Galaxy)',
  redshift: 0.0,
  lookbackGyr: 0.0,
  stellarMassMsun: 6.0e10, // 6.0 x 10^10 M_sun
  logMstar: 10.78,         // log10(M_star / M_sun)
  sfr: 1.65,               // M_sun / yr
  sfrUncertainty: 0.19,    // M_sun / yr
  logSSFR: -10.54,         // log10(sSFR / yr^-1)
  dustAv: 0.38,            // Mean diffuse V-band extinction (mag)
  scaleLengthKpc: 2.6,     // Exponential disk scale length (kpc)
  effectiveRadiusKpc: 4.2, // Half-light radius R_e (kpc)
  opticalDiameterKpc: 26.8,// D_25 diameter (kpc)
  scaleHeightKpc: 0.30,    // Thin disk scale height (kpc)
  bulgeToTotal: 0.18,      // B/T luminosity/mass fraction
  morphology: 'SBbc (Barred Spiral)',
  evolutionaryPhase: 'Green Valley (Transitional Spiral)',
} as const;

/**
 * Standard Synthetic Galaxy object representing the Milky Way benchmark (z = 0)
 * compatible with the Galaxy interface for use across comparative stages and inspectors.
 */
export const MILKY_WAY_GALAXY: Galaxy = {
  id: 'MILKY_WAY',
  ra: 266.4168,
  dec: -29.0078,
  redshift: 0.0,
  stellar_mass: 6.0e10,
  log_mstar: 10.78,
  sfr: 1.65,
  av: 0.38,
  tau_diffuse: 0.38,
  tau_birth: 0.76,
  sentry_status: 'PRISTINE',
  apparent_mag: -20.5,
  fluxes: {},
  mags: {},
  sed: [],
  discovery_profile: {
    classification: 'COSMIC_NOON_SUPER_STARBURST' as any,
    class_title: 'Local Barred Spiral Benchmark',
    rarity_sigma: 0,
    rarity_percentile: 'z = 0 Local Anchor',
    observed_phenomenon: 'Barred spiral galaxy in Green Valley transition (Bland-Hawthorn & Gerhard 2016)',
    hypotheses: {
      primary: 'Quenching disk with central bar and low SFR (1.65 M☉/yr)',
      alternative: 'Secular evolution via bar-driven gas inflow',
      citations: ['Bland-Hawthorn & Gerhard 2016', 'Chomiuk & Povich 2011'],
    },
    jwst_followup: {
      instrument: 'NIRCam',
      mode: 'Wide-Field',
      exposure_time_s: 0,
      science_goal: 'Local universe benchmark calibration',
    },
  },
};

export interface MilkyWayComparison {
  targetGalaxy: Galaxy;
  lookbackGyr: number;
  massRatio: number;          // M_target / M_MW
  deltaLogMass: number;       // log(M_target) - log(M_MW)
  sfrMultiplier: number;      // SFR_target / SFR_MW
  ssfrRatio: number;          // sSFR_target / sSFR_MW
  physicalRadiusKpc: number;  // Estimated R_e in kpc
  radiusRatio: number;        // R_target / R_MW
  
  // Progenitor analysis (van Dokkum et al. 2013 assembly track)
  expectedProgenitorMass: number;    // expected log M* at redshift z
  expectedProgenitorSfr: number;     // expected SFR at redshift z
  progenitorMassRatio: number;       // target mass / expected progenitor mass
  progenitorScorePercent: number;    // 0 - 100% match to MW evolutionary ancestor
  isProgenitorCandidate: boolean;    // score >= 65%
  classificationTitle: string;       // Human-readable comparative verdict
  researchSignificance: string;      // Research and proposal context
}

/**
 * Predicts the expected stellar mass and SFR of the Milky Way's direct progenitor
 * at a given redshift z using the empirical constant cumulative number density track
 * from van Dokkum et al. (2013) and Papovich et al. (2015).
 */
export function getMilkyWayProgenitorExpected(z: number): {
  logMass: number;
  stellarMassMsun: number;
  sfr: number;
  radiusKpc: number;
} {
  const clampedZ = Math.max(0, Math.min(8.5, z));
  
  // van Dokkum et al. (2013) assembly track: log M*(z) ~ 10.78 - 0.40 * z
  const logMass = 10.78 - 0.40 * clampedZ;
  const stellarMassMsun = Math.pow(10, logMass);

  // Star formation rate evolution of progenitor: SFR(z) ~ 1.65 * (1 + z)^2.2
  const sfr = 1.65 * Math.pow(1.0 + clampedZ, 2.2);

  // van der Wel et al. (2014) mass-size relation evolution: R_e(z) ~ R_e,0 * (1 + z)^(-0.75)
  const radiusKpc = MILKY_WAY_BENCHMARK.effectiveRadiusKpc * Math.pow(1.0 + clampedZ, -0.75);

  return {
    logMass,
    stellarMassMsun,
    sfr,
    radiusKpc,
  };
}

/**
 * Estimates the physical half-light radius R_e in kpc from stellar mass and redshift
 * based on the 3D-HST / CANDELS mass-size relation (van der Wel et al. 2014).
 */
export function estimatePhysicalRadiusKpc(logMstar: number, z: number, isQuenched: boolean = false): number {
  const clampedZ = Math.max(0, z);
  const massPivot = 5.0e10;
  const m = Math.pow(10, logMstar);
  const massRatio = m / massPivot;

  if (isQuenched) {
    // Early-type / Quenched galaxies: steeper mass dependence, smaller sizes
    return Math.max(0.5, 2.5 * Math.pow(massRatio, 0.55) * Math.pow(1.0 + clampedZ, -1.2));
  } else {
    // Late-type / Star-forming disks: shallower mass dependence
    return Math.max(0.8, 4.2 * Math.pow(massRatio, 0.22) * Math.pow(1.0 + clampedZ, -0.75));
  }
}

/**
 * Compares an observed galaxy with the Milky Way benchmark and progenitor evolutionary tracks.
 */
export function compareWithMilkyWay(galaxy: Galaxy): MilkyWayComparison {
  const z = typeof galaxy.redshift === 'number' && !isNaN(galaxy.redshift) ? Math.max(0, galaxy.redshift) : 1.0;
  const lookback = lookbackTimeGyr(z);
  const mstar = typeof galaxy.log_mstar === 'number' && !isNaN(galaxy.log_mstar) ? galaxy.log_mstar : 9.5;
  const mstarLinear = Math.pow(10, mstar);
  const sfr = typeof galaxy.sfr === 'number' && !isNaN(galaxy.sfr) ? Math.max(0, galaxy.sfr) : 1.0;

  // Mass & SFR ratios compared to modern Milky Way
  const massRatio = mstarLinear / MILKY_WAY_BENCHMARK.stellarMassMsun;
  const deltaLogMass = mstar - MILKY_WAY_BENCHMARK.logMstar;
  const sfrMultiplier = sfr / MILKY_WAY_BENCHMARK.sfr;

  const targetSSFR = sfr / mstarLinear;
  const mwSSFR = MILKY_WAY_BENCHMARK.sfr / MILKY_WAY_BENCHMARK.stellarMassMsun;
  const ssfrRatio = targetSSFR / mwSSFR;

  // Physical radius estimation
  const isQuenched = targetSSFR < 1e-11;
  const physicalRadiusKpc = estimatePhysicalRadiusKpc(mstar, z, isQuenched);
  const radiusRatio = physicalRadiusKpc / MILKY_WAY_BENCHMARK.effectiveRadiusKpc;

  // Progenitor comparison at redshift z
  const progenitor = getMilkyWayProgenitorExpected(z);
  const massDeltaToProg = Math.abs(mstar - progenitor.logMass);
  const sfrRatioToProg = Math.abs(Math.log10(Math.max(1e-4, sfr) / Math.max(1e-4, progenitor.sfr)));

  // Progenitor score (Gaussian likelihood combining mass and SFR consistency)
  const massScore = Math.exp(-0.5 * Math.pow(massDeltaToProg / 0.35, 2));
  const sfrScore = Math.exp(-0.5 * Math.pow(sfrRatioToProg / 0.45, 2));
  const progenitorScorePercent = Math.round(massScore * sfrScore * 100);
  const isProgenitorCandidate = progenitorScorePercent >= 60;

  // Qualitative classification verdict
  let classificationTitle = 'Distant Galaxy';
  let researchSignificance = '';

  if (galaxy.discovery_profile?.classification === 'LITTLE_RED_DOT') {
    classificationTitle = 'Exotic Super-Compact Black Hole Core (Little Red Dot)';
    researchSignificance = `Confined to a radius ~${(physicalRadiusKpc).toFixed(1)} kpc (${(radiusRatio * 100).toFixed(0)}% of MW), this early universe nugget harbors an AGN/torus producing extreme infrared excess unseen in the local Milky Way.`;
  } else if (isProgenitorCandidate && z >= 1.2) {
    classificationTitle = `Milky Way Progenitor Candidate (${progenitorScorePercent}% match)`;
    researchSignificance = `Matches the expected mass (${(massRatio * 100).toFixed(0)}% modern MW) and starburst activity (${sfrMultiplier.toFixed(1)}x modern MW) of our home galaxy's ancestor at Lookback ~${lookback.toFixed(1)} Gyr. Ideal for tracing early disk assembly.`;
  } else if (z < 0.6 && Math.abs(deltaLogMass) < 0.25) {
    classificationTitle = 'Milky Way Twin / Morphological Analogue';
    researchSignificance = `Shares close mass (~${(massRatio).toFixed(2)}x MW) and late-epoch disk structure with the modern Milky Way, making it an excellent laboratory for testing local Galactic evolutionary physics.`;
  } else if (sfrMultiplier > 15) {
    classificationTitle = `Hyper-Starburst Monster (${sfrMultiplier.toFixed(0)}x MW SFR)`;
    researchSignificance = `Forming stars at an astonishing rate of ${sfr.toFixed(1)} M☉/yr (${sfrMultiplier.toFixed(0)}x the Milky Way), exhausting its cold gas reservoir on rapid sub-Gyr timescales.`;
  } else if (deltaLogMass > 0.4) {
    classificationTitle = `Ancient Massive Titan (${massRatio.toFixed(1)}x MW Mass)`;
    researchSignificance = `Exceeds the Milky Way's stellar mass by a factor of ${massRatio.toFixed(1)}x, likely representing the brightest central cluster galaxy (BCG) of a massive dark matter halo.`;
  } else {
    classificationTitle = `Sub-Milky Way Dwarf/Intermediate (${(massRatio * 100).toFixed(0)}% MW Mass)`;
    researchSignificance = `An intermediate-mass galaxy (${(massRatio * 100).toFixed(1)}% of MW mass) undergoing secular disk growth.`;
  }

  return {
    targetGalaxy: galaxy,
    lookbackGyr: lookback,
    massRatio,
    deltaLogMass,
    sfrMultiplier,
    ssfrRatio,
    physicalRadiusKpc,
    radiusRatio,
    expectedProgenitorMass: progenitor.logMass,
    expectedProgenitorSfr: progenitor.sfr,
    progenitorMassRatio: mstarLinear / progenitor.stellarMassMsun,
    progenitorScorePercent,
    isProgenitorCandidate,
    classificationTitle,
    researchSignificance,
  };
}
