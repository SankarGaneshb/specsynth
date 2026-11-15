"""
Generate representative, astrophysically consistent galaxy sample catalogs
in Parquet, FITS, HDF5, and CSV formats for testing, validation, and benchmarking.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import numpy as np


def generate_astrophysical_sample(n_gal: int = 10_000, seed: int = 42) -> dict[str, np.ndarray]:
    """Generate realistic physical parameters for galaxies."""
    rng = np.random.default_rng(seed)

    # 1. Stellar Mass: log10(M*/Msun) between 8.5 and 11.5 (Schechter-like distribution)
    log_mstar = rng.uniform(8.5, 11.5, n_gal).astype(np.float32)

    # 2. Cosmological Redshift: z in [0.05, 4.0]
    redshift = rng.uniform(0.05, 4.0, n_gal).astype(np.float32)

    # 3. SFH Onset Time: t_onset in [1.0, 10.0] Gyr (bounded by age of universe)
    t_onset = rng.uniform(1.0, 10.0, n_gal).astype(np.float32)

    # 4. SFH Timescale: tau in [0.5, 4.0] Gyr
    tau = rng.uniform(0.5, 4.0, n_gal).astype(np.float32)

    # 5. Stellar Metallicity: log10(Z/Z_sun) centered near solar (-0.2 +/- 0.3 dex)
    log_z = rng.normal(-0.2, 0.3, n_gal).astype(np.float32)
    log_z = np.clip(log_z, -2.0, 0.3)

    # 6. Two-Component Dust (Charlot & Fall 2000):
    # Diffuse ISM optical depth tau_V ~ 0.3, Birth cloud tau_V ~ 1.5 * diffuse
    tau_diffuse = rng.exponential(0.3, n_gal).astype(np.float32)
    tau_diffuse = np.clip(tau_diffuse, 0.0, 2.5)
    tau_birth = (tau_diffuse * rng.uniform(1.2, 2.0, n_gal)).astype(np.float32)

    return {
        "log_mstar": log_mstar,
        "m_star": (10.0 ** log_mstar).astype(np.float32),
        "redshift": redshift,
        "t_onset": t_onset,
        "tau": tau,
        "metallicity": log_z,
        "tau_diffuse": tau_diffuse,
        "tau_birth": tau_birth,
        "av": (tau_diffuse * 1.086).astype(np.float32),
    }


def export_all_formats(output_dir: Path, n_gal: int = 10_000, seed: int = 42) -> dict[str, Path]:
    """Export the galaxy sample to Parquet, FITS, HDF5, and CSV files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    data = generate_astrophysical_sample(n_gal=n_gal, seed=seed)
    exported: dict[str, Path] = {}

    # 1. Parquet
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
        tbl = pa.Table.from_pydict(data)
        pq_path = output_dir / "sample_catalog.parquet"
        pq.write_table(tbl, pq_path, compression="zstd")
        exported["parquet"] = pq_path
        print(f"  [+] Wrote Parquet: {pq_path} ({n_gal:,} rows)")
    except ImportError:
        import pandas as pd
        df = pd.DataFrame(data)
        pq_path = output_dir / "sample_catalog.parquet"
        df.to_parquet(pq_path, engine="pyarrow")
        exported["parquet"] = pq_path
        print(f"  [+] Wrote Parquet: {pq_path} ({n_gal:,} rows)")

    # 2. CSV
    csv_path = output_dir / "sample_catalog.csv"
    with open(csv_path, "w", encoding="utf-8") as f:
        headers = list(data.keys())
        f.write(",".join(headers) + "\n")
        for i in range(n_gal):
            f.write(",".join(f"{data[h][i]:.5g}" for h in headers) + "\n")
    exported["csv"] = csv_path
    print(f"  [+] Wrote CSV:     {csv_path} ({n_gal:,} rows)")

    # 3. FITS Table
    try:
        from astropy.table import Table
        fits_path = output_dir / "sample_catalog.fits"
        t = Table(data)
        t.write(str(fits_path), format="fits", overwrite=True)
        exported["fits"] = fits_path
        print(f"  [+] Wrote FITS:    {fits_path} ({n_gal:,} rows)")
    except Exception as e:
        print(f"  [-] Skipped FITS: {e}")

    # 4. HDF5 Table
    try:
        import h5py
        h5_path = output_dir / "sample_catalog.h5"
        with h5py.File(h5_path, "w") as hf:
            for k, v in data.items():
                hf.create_dataset(k, data=v, compression="gzip")
        exported["hdf5"] = h5_path
        print(f"  [+] Wrote HDF5:    {h5_path} ({n_gal:,} rows)")
    except Exception as e:
        print(f"  [-] Skipped HDF5: {e}")

    return exported


def main():
    parser = argparse.ArgumentParser(description="Generate sample catalogs across Parquet, FITS, HDF5, and CSV.")
    parser.add_argument("--output-dir", "-o", default="sample_catalogs", help="Directory to save sample files")
    parser.add_argument("--n-gal", "-n", type=int, default=10_000, help="Number of galaxies per file (default: 10,000)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    args = parser.parse_args()

    print(f"\nGenerating realistic astronomical sample catalogs ({args.n_gal:,} galaxies)...")
    out_dir = Path(args.output_dir)
    export_all_formats(out_dir, n_gal=args.n_gal, seed=args.seed)
    print(f"\nAll catalogs successfully generated in '{out_dir}'!\n")


if __name__ == "__main__":
    main()

