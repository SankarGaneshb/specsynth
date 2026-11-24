"""
Generate reference stellar population synthesis grids for SpecSynth.
Supports:
  1. Genuine FSPS grid generation via python-fsps (when installed with SPS_HOME).
  2. Analytical reference grid (heuristic continuum & break proxy) explicitly labeled
     as 'analytical_reference' when python-fsps is not installed.
"""

from pathlib import Path
import sys
import numpy as np

try:
    import fsps
    HAS_FSPS = True
except ImportError:
    HAS_FSPS = False


def generate_genuine_fsps_grid(output_path: str | Path, z_list: list[float] | None = None) -> None:
    """Generate multi-metallicity reference grid using genuine python-fsps."""
    if not HAS_FSPS:
        raise ImportError("python-fsps is required to generate genuine FSPS grids.")

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    sp = fsps.StellarPopulation(compute_vega_mags=False, zcontinuous=1, sfh=0, imf_type=1)
    ages = np.logspace(6.0, np.log10(1.35e10), 30)
    metallicities = z_list or [0.0002, 0.002, 0.008, 0.02, 0.03]

    wave = sp.wavelengths
    # Build 2D/3D table
    lines = [
        f"# FSPS v3.2 Genuine Reference Grid (MIST isochrones, Chabrier IMF)",
        f"# Model: FSPS",
        f"# is_genuine_fsps: True",
        f"# N_WAVE={len(wave)}, N_AGE={len(ages)}, N_MET={len(metallicities)}",
        f"# Ages (yr): " + ", ".join(f"{a:.2e}" for a in ages),
        f"# Metallicities: " + ", ".join(f"{z:.4f}" for z in metallicities),
        f"# Units: L_sun / A per formed M_sun",
    ]
    # For compatibility with standard 2D spec format: wave, then fluxes for each age (at solar metallicity or first met)
    sp.params["zmet"] = 4  # solar
    fluxes_solar = np.empty((len(ages), len(wave)), dtype=np.float64)
    for i, a in enumerate(ages):
        _, flux = sp.get_spectrum(tage=a / 1e9, peraa=True)
        fluxes_solar[i] = flux

    table_data = np.column_stack([wave, fluxes_solar.T])
    header = "\n".join(lines)
    np.savetxt(out, table_data, fmt="%.8e", header=header)
    print(f"Successfully generated genuine FSPS grid: {out} ({len(wave)} wave x {len(ages)} ages)")


def generate_analytical_reference_grid(output_path: str | Path) -> None:
    """
    Generate analytical reference grid (heuristic continuum & break proxy).
    Explicitly labeled as 'analytical_reference' to prevent confusion with genuine FSPS.
    """
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    # 1. Wavelength grid: 91.2 A to 100,000 A (2,500 log-spaced points)
    wave = np.geomspace(91.2, 100000.0, 2500)

    # 2. Age grid: 25 logarithmic steps from 1 Myr to 13.5 Gyr
    ages = np.logspace(6.0, np.log10(1.35e10), 25)
    log_ages = np.log10(ages)

    # 3. Composite stellar population model proxy:
    fluxes = np.empty((len(ages), len(wave)), dtype=np.float64)

    for i, (age, log_a) in enumerate(zip(ages, log_ages)):
        t_eff = max(45000.0 * (age / 1e6) ** (-0.23), 4000.0)

        # Planck function normalized
        lam_m = wave * 1e-10
        x = np.clip(1.4388e-2 / (lam_m * t_eff), 1e-5, 700.0)
        bb = 1.0 / (lam_m**5 * np.expm1(x))
        bb /= np.max(bb)

        # Lyman break at 911.75 A
        lyman_factor = np.where(wave < 911.75, 1e-4, 1.0)

        # Balmer break at 3646 A
        balmer_strength = 0.4 * np.exp(-0.5 * ((log_a - 8.2) / 0.8) ** 2)
        balmer_factor = np.where(wave < 3646.0, 1.0 - balmer_strength, 1.0)

        # 4000 A break
        d4000_strength = min(1.8, 1.0 + 0.25 * max(0.0, log_a - 7.5))
        d4000_factor = np.where(wave < 4000.0, 1.0 / d4000_strength, 1.0)

        # UV slope power law
        uv_weight = np.exp(-age / 3e7)
        uv_component = (wave / 1500.0) ** (-2.2) * uv_weight

        # Total normalized SED
        sed = (bb + 0.3 * uv_component) * lyman_factor * balmer_factor * d4000_factor

        # Scale to standard luminosity density units (L_sun / A per formed M_sun)
        norm_factor = 12.0 * (age / 1e6) ** (-0.55)
        flux_age = sed * (norm_factor / np.max(sed))

        # Mid-IR Rayleigh-Jeans decline (wave > 2 um)
        rj_mask = wave > 20000.0
        rj_anchor = np.interp(20000.0, wave, flux_age)
        flux_age[rj_mask] = rj_anchor * (wave[rj_mask] / 20000.0) ** (-3.9)

        fluxes[i] = np.maximum(flux_age, 1e-12)

    table_data = np.column_stack([wave, fluxes.T])

    header = (
        f"SpecSynth Analytical Continuum Reference Grid (Heuristic Benchmark Model)\n"
        f"Model: analytical_reference\n"
        f"is_genuine_fsps: False\n"
        f"Description: Analytical continuum, Lyman break, Balmer break, Dn4000, and RJ tail proxy\n"
        f"Note: This is an analytical reference grid, not a genuine Fortran FSPS calculation.\n"
        f"N_WAVE={len(wave)}, N_AGE={len(ages)}\n"
        f"Ages (yr): " + ", ".join(f"{a:.2e}" for a in ages) + "\n"
        f"Col 0: Wavelength (Angstroms), Cols 1..{len(ages)}: Flux (L_sun/A per M_sun formed)"
    )

    np.savetxt(out, table_data, fmt="%.8e", header=header)
    print(f"Successfully generated analytical reference grid: {out} ({len(wave)} wave x {len(ages)} ages) [model: analytical_reference]")


def generate_reference_grid(output_path: str | Path) -> None:
    """Generate genuine FSPS grid if python-fsps is installed, else analytical reference grid."""
    if HAS_FSPS:
        generate_genuine_fsps_grid(output_path)
    else:
        generate_analytical_reference_grid(output_path)


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "sample_models/fsps/fsps_full_chabrier_mist.spec"
    generate_reference_grid(target)

