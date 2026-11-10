"""
Utility script to generate sample model files for E-MILES, FSPS, and BC03
to test and validate specsynth adapters without downloading multi-gigabyte datasets.
"""

from pathlib import Path
import numpy as np

def make_sample_emiles(target_dir: Path):
    target_dir.mkdir(parents=True, exist_ok=True)
    # Generate 2 sample FITS files with standard E-MILES names:
    # 1) Ebi1.30Zp0.06T01.0000_iTp0.00_baseFe.fits  ([M/H] = +0.06, Age = 1.0 Gyr)
    # 2) Ebi1.30Zm0.40T05.0000_iTp0.00_baseFe.fits  ([M/H] = -0.40, Age = 5.0 Gyr)
    n_wave = 100
    crval1, cdelt1 = 3500.0, 10.0
    flux1 = np.linspace(1.0, 5.0, n_wave, dtype=">f4")
    flux2 = np.linspace(0.5, 3.5, n_wave, dtype=">f4")

    def write_fits_1d(filepath: Path, flux: np.ndarray):
        cards = [
            "SIMPLE  =                    T / file conforms to FITS standard             ",
            "BITPIX  =                  -32 / number of bits per data pixel                  ",
            "NAXIS   =                    1 / number of data axes                            ",
            f"NAXIS1  =                  {n_wave:4d} / length of data axis 1                         ",
            f"CRVAL1  =             {crval1:8.1f} / reference value                              ",
            f"CDELT1  =               {cdelt1:6.1f} / coordinate increment                        ",
            "CRPIX1  =                  1.0 / reference pixel                                ",
            "END                                                                             ",
        ]
        hdr_bytes = "".join(cards).encode("ascii")
        hdr_bytes += b" " * (2880 - (len(hdr_bytes) % 2880))
        data_bytes = flux.tobytes()
        rem = len(data_bytes) % 2880
        if rem != 0:
            data_bytes += b"\x00" * (2880 - rem)
        with open(filepath, "wb") as f:
            f.write(hdr_bytes)
            f.write(data_bytes)

    f1 = target_dir / "Ebi1.30Zp0.06T01.0000_iTp0.00_baseFe.fits"
    f2 = target_dir / "Ebi1.30Zm0.40T05.0000_iTp0.00_baseFe.fits"
    write_fits_1d(f1, flux1)
    write_fits_1d(f2, flux2)
    print(f"Created sample E-MILES FITS files in: {target_dir}")


def make_sample_fsps(target_file: Path):
    target_file.parent.mkdir(parents=True, exist_ok=True)
    # Generate sample ASCII table matching standalone Fortran FSPS output
    wave = np.linspace(1000, 10000, 100)
    flux_age1 = np.exp(-wave / 4000.0) * 10.0
    flux_age2 = np.exp(-wave / 6000.0) * 5.0
    table = np.column_stack([wave, flux_age1, flux_age2])
    np.savetxt(target_file, table, header="Sample FSPS spectrum: col 0 = wave(A), cols 1..2 = flux")
    print(f"Created sample FSPS ASCII file: {target_file}")


def main():
    base = Path("sample_data")
    make_sample_emiles(base / "emiles")
    make_sample_fsps(base / "fsps" / "spstot_chab.spec")
    print("\nSample data generated successfully!")


if __name__ == "__main__":
    main()
