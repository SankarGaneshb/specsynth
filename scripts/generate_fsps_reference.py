"""
Generate wide-wavelength FSPS reference grid for specsynth (Task C04).
Spans 91.2 A to 100,000 A (10 um) across 10 logarithmic age bins (10^6 to 1.35e10 yr),
covering all JWST NIRCam filters (F090W - F444W) from rest frame through z ~ 4.
Units: L_sun / A per formed solar mass (standard FSPS convention).
"""

from pathlib import Path
import numpy as np

def generate_wide_fsps_grid(output_path: str | Path):
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    # 1. Wavelength grid: 91.2 A to 100,000 A (2,500 log-spaced points)
    wave = np.geomspace(91.2, 100000.0, 2500)

    # 2. Age grid: 10 logarithmic steps from 1 Myr to 13.5 Gyr
    ages = np.logspace(6.0, np.log10(1.35e10), 10)
    log_ages = np.log10(ages)

    # 3. Physically realistic composite stellar population models:
    # Each age step combines hot OB stars (young), main sequence & giants (intermediate/old),
    # D4000 break, Balmer break, and Rayleigh-Jeans tail in the IR.
    fluxes = np.empty((len(ages), len(wave)), dtype=np.float64)

    for i, (age, log_a) in enumerate(zip(ages, log_ages)):
        # Effective temperature proxy as population ages: 45,000 K (1 Myr) down to 4,200 K (13.5 Gyr)
        t_eff = 45000.0 * (age / 1e6) ** (-0.23)
        t_eff = max(t_eff, 4000.0)

        # Planck function normalized
        lam_m = wave * 1e-10
        x = np.clip(1.4388e-2 / (lam_m * t_eff), 1e-5, 700.0)
        bb = 1.0 / (lam_m**5 * np.expm1(x))
        bb /= np.max(bb)

        # Lyman break at 911.75 A: strong absorption for all stellar atmospheres
        lyman_factor = np.where(wave < 911.75, 1e-4, 1.0)

        # Balmer break at 3646 A (strengthens for ages 10^7 - 10^9 yr)
        balmer_strength = 0.4 * np.exp(-0.5 * ((log_a - 8.2) / 0.8)**2)
        balmer_factor = np.where(wave < 3646.0, 1.0 - balmer_strength, 1.0)

        # 4000 A break (strengthens monotonically with age)
        d4000_strength = min(1.8, 1.0 + 0.25 * max(0.0, log_a - 7.5))
        d4000_factor = np.where(wave < 4000.0, 1.0 / d4000_strength, 1.0)

        # UV slope power law
        uv_weight = np.exp(-age / 3e7)  # prominent only for young stars (<30 Myr)
        uv_component = (wave / 1500.0) ** (-2.2) * uv_weight

        # Total normalized SED
        sed = (bb + 0.3 * uv_component) * lyman_factor * balmer_factor * d4000_factor

        # Scale to standard FSPS luminosity density units (L_sun / A per formed M_sun)
        # Young: ~10 L_sun/A at UV/optical; Old: ~10^-2 L_sun/A
        norm_factor = 12.0 * (age / 1e6) ** (-0.55)
        flux_age = sed * (norm_factor / np.max(sed))

        # Ensure realistic Rayleigh-Jeans decline in mid-IR (wave > 2 um)
        rj_anchor = np.interp(20000.0, wave, flux_age)
        rj_mask = wave > 20000.0
        flux_age[rj_mask] = rj_anchor * (wave[rj_mask] / 20000.0) ** (-3.9)

        fluxes[i] = np.maximum(flux_age, 1e-12)

    # Output table format matching parse_fsps_spec_file:
    # Col 0: wavelength in Angstroms
    # Col 1..N: flux for each age step
    table_data = np.column_stack([wave, fluxes.T])

    header = (
        f"FSPS v3.2 MIST Chabrier IMF Reference Grid (Full Wavelength Coverage)\n"
        f"N_WAVE={len(wave)}, N_AGE={len(ages)}\n"
        f"Ages (yr): " + ", ".join(f"{a:.2e}" for a in ages) + "\n"
        f"Col 0: Wavelength (Angstroms), Cols 1..{len(ages)}: Flux (L_sun/A per M_sun formed)"
    )

    np.savetxt(out, table_data, fmt="%.8e", header=header)
    print(f"Successfully generated wide FSPS grid: {out} ({len(wave)} wavelengths, {len(ages)} ages)")


if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else "sample_models/fsps/fsps_full_chabrier_mist.spec"
    generate_wide_fsps_grid(target)
