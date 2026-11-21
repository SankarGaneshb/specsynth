"""
Utility script to generate sample model files for E-MILES, FSPS, BC03, and generic FITS/HDF5 grids
to test and validate specsynth adapters without downloading multi-gigabyte datasets.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import struct
import numpy as np


def make_sample_bc03(target_file: Path, n_age: int = 15, n_wave: int = 200):
    """Generate a valid BC03 binary Fortran unformatted .ised file."""
    target_file.parent.mkdir(parents=True, exist_ok=True)
    ages = np.logspace(6.0, 10.0, n_age, dtype=np.float32)
    wave = np.linspace(912.0, 25000.0, n_wave, dtype=np.float32)

    with open(target_file, "wb") as f:
        # Record 1: ages
        rec1_payload = struct.pack("=i", n_age) + ages.tobytes()
        f.write(struct.pack("=i", len(rec1_payload)) + rec1_payload + struct.pack("=i", len(rec1_payload)))

        # Record 2: wavelengths
        rec2_payload = struct.pack("=i", n_wave) + wave.tobytes()
        f.write(struct.pack("=i", len(rec2_payload)) + rec2_payload + struct.pack("=i", len(rec2_payload)))

        # Spectra records per age
        for a in ages:
            flux = (np.exp(-wave / 5000.0) * (5e9 / float(a)) ** 0.5).astype(np.float32)
            f.write(struct.pack("=i", len(flux.tobytes())) + flux.tobytes() + struct.pack("=i", len(flux.tobytes())))

    print(f"  [+] Wrote BC03 .ised binary: {target_file} ({n_age} ages x {n_wave} wavelengths)")


def make_sample_emiles(target_dir: Path, n_wave: int = 200):
    """Generate sample FITS files matching standard E-MILES directory layout."""
    target_dir.mkdir(parents=True, exist_ok=True)
    crval1, cdelt1 = 1680.0, 10.0

    def write_fits_1d(filepath: Path, flux: np.ndarray):
        try:
            from astropy.io import fits
            hdr = fits.Header()
            hdr["SIMPLE"] = True
            hdr["BITPIX"] = -32
            hdr["NAXIS"] = 1
            hdr["NAXIS1"] = n_wave
            hdr["CRVAL1"] = crval1
            hdr["CDELT1"] = cdelt1
            hdr["CRPIX1"] = 1.0
            fits.writeto(filepath, flux.astype(np.float32), hdr, overwrite=True)
        except ImportError:
            cards = [
                "SIMPLE  =                    T",
                "BITPIX  =                  -32",
                "NAXIS   =                    1",
                f"NAXIS1  =                 {n_wave:4d}",
                f"CRVAL1  =             {crval1:8.1f}",
                f"CDELT1  =               {cdelt1:6.1f}",
                "CRPIX1  =                  1.0",
                "END",
            ]
            hdr_bytes = "".join(c.ljust(80) for c in cards).encode("ascii")
            rem = len(hdr_bytes) % 2880
            if rem != 0:
                hdr_bytes += b" " * (2880 - rem)
            data_bytes = flux.astype(">f4").tobytes()
            rem_d = len(data_bytes) % 2880
            if rem_d != 0:
                data_bytes += b"\x00" * (2880 - rem_d)
            with open(filepath, "wb") as f:
                f.write(hdr_bytes)
                f.write(data_bytes)

    f1 = target_dir / "Ebi1.30Zp0.06T01.0000_iTp0.00_baseFe.fits"
    f2 = target_dir / "Ebi1.30Zm0.40T05.0000_iTp0.00_baseFe.fits"
    f3 = target_dir / "Ebi1.30Zp0.06T05.0000_iTp0.00_baseFe.fits"
    f4 = target_dir / "Ebi1.30Zm0.40T01.0000_iTp0.00_baseFe.fits"
    write_fits_1d(f1, np.linspace(1.0, 5.0, n_wave, dtype=">f4"))
    write_fits_1d(f2, np.linspace(0.5, 3.5, n_wave, dtype=">f4"))
    write_fits_1d(f3, np.linspace(0.8, 4.0, n_wave, dtype=">f4"))
    write_fits_1d(f4, np.linspace(0.7, 3.2, n_wave, dtype=">f4"))
    print(f"  [+] Wrote E-MILES models:    {target_dir} (4 sample FITS files)")


def make_sample_fsps(target_file: Path, n_wave: int = 200):
    """Generate sample ASCII table matching standalone Fortran FSPS output."""
    target_file.parent.mkdir(parents=True, exist_ok=True)
    wave = np.linspace(1000, 10000, n_wave)
    flux_age1 = np.exp(-wave / 4000.0) * 10.0
    flux_age2 = np.exp(-wave / 6000.0) * 5.0
    table = np.column_stack([wave, flux_age1, flux_age2])
    np.savetxt(target_file, table, header="Sample FSPS spectrum: col 0 = wave(A), cols 1..2 = flux")
    print(f"  [+] Wrote FSPS ASCII:       {target_file} ({n_wave} wavelengths)")


def make_sample_fits_grid(target_file: Path, n_age: int = 5, n_met: int = 3, n_wave: int = 100):
    """Generate 3D multi-dimensional FITS grid."""
    target_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        from astropy.io import fits
        ages = np.logspace(7.0, 9.5, n_age)
        mets = np.array([-1.0, 0.0, 0.2])
        wave = np.linspace(1000, 10000, n_wave)
        flux_grid = np.random.uniform(0.1, 10.0, (n_age, n_met, n_wave)).astype(np.float32)

        hdul = fits.HDUList([
            fits.PrimaryHDU(flux_grid),
            fits.ImageHDU(wave, name="WAVE"),
            fits.ImageHDU(ages, name="AGE"),
            fits.ImageHDU(mets, name="MET"),
        ])
        hdul.writeto(target_file, overwrite=True)
        print(f"  [+] Wrote FITS grid:        {target_file} ({n_age}x{n_met}x{n_wave})")
    except Exception as e:
        print(f"  [-] Skipped FITS grid: {e}")


def make_sample_hdf5_grid(target_file: Path, n_age: int = 5, n_met: int = 3, n_wave: int = 100):
    """Generate multi-dimensional HDF5 grid."""
    target_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        import h5py
        ages = np.logspace(7.0, 9.5, n_age)
        mets = np.array([-1.0, 0.0, 0.2])
        wave = np.linspace(1000, 10000, n_wave)
        flux_grid = np.random.uniform(0.1, 10.0, (n_age, n_met, n_wave)).astype(np.float32)

        with h5py.File(target_file, "w") as hf:
            hf.create_dataset("FLUX", data=flux_grid)
            hf.create_dataset("WAVE", data=wave)
            hf.create_dataset("AGE", data=ages)
            hf.create_dataset("MET", data=mets)
        print(f"  [+] Wrote HDF5 grid:        {target_file} ({n_age}x{n_met}x{n_wave})")
    except Exception as e:
        print(f"  [-] Skipped HDF5 grid: {e}")


def main():
    parser = argparse.ArgumentParser(description="Generate sample external SPS library files (BC03, E-MILES, FSPS, FITS/HDF5 grids).")
    parser.add_argument("--output-dir", "-o", default="sample_models", help="Directory to save sample models")
    args = parser.parse_args()

    base = Path(args.output_dir)
    print(f"\nGenerating sample external SPS model libraries in '{base}'...")
    make_sample_bc03(base / "bc03" / "bc2003_hr_stelib_chab_ssp.ised")
    make_sample_emiles(base / "emiles")
    make_sample_fsps(base / "fsps" / "spstot_chab.spec")
    make_sample_fits_grid(base / "fits_grid" / "ssp_grid.fits")
    make_sample_hdf5_grid(base / "fits_grid" / "ssp_grid.h5")
    print("\nAll sample SPS model libraries successfully generated!\n")


if __name__ == "__main__":
    main()
