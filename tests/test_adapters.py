import struct
from pathlib import Path

import numpy as np
import pytest

from specsynth.adapters import (
    BC03Adapter,
    EMILESAdapter,
    FITSGridAdapter,
    FSPSAdapter,
    SSPData,
    ToyAdapter,
    get_adapter,
)


def test_ssp_data_validation():
    ages = np.array([1e7, 1e8, 1e9])
    mets = np.array([0.004, 0.02])
    wave = np.array([1000.0, 2000.0, 3000.0, 4000.0])
    ssp = np.ones((len(ages) * len(mets), len(wave)), dtype=np.float32)

    data = SSPData(ages=ages, mets=mets, wave=wave, ssp=ssp)
    assert data.ssp.shape == (6, 4)

    # Test non-monotonic ages
    with pytest.raises(ValueError, match="strictly monotonically increasing"):
        SSPData(ages=np.array([1e8, 1e7]), mets=mets, wave=wave, ssp=ssp[:4])

    # Test shape mismatch
    with pytest.raises(ValueError, match="shape mismatch"):
        SSPData(ages=ages, mets=mets, wave=wave, ssp=ssp[:3])

    # Test empty or invalid dims
    with pytest.raises(ValueError, match="ages must be a non-empty 1D array"):
        SSPData(ages=np.array([]), mets=mets, wave=wave, ssp=np.empty((0, 4)))

    with pytest.raises(ValueError, match="mets must be a non-empty 1D array"):
        SSPData(ages=ages, mets=np.array([]), wave=wave, ssp=np.empty((0, 4)))

    with pytest.raises(ValueError, match="wave must be a non-empty 1D array"):
        SSPData(ages=ages, mets=mets, wave=np.array([]), ssp=np.empty((6, 0)))

    # Non-monotonic wave
    with pytest.raises(ValueError, match="wave must be strictly monotonically increasing"):
        SSPData(ages=ages, mets=mets, wave=np.array([2000.0, 1000.0, 3000.0, 4000.0]), ssp=ssp)

    # Non-finite ssp
    bad_ssp = np.copy(ssp)
    bad_ssp[0, 0] = np.nan
    with pytest.raises(ValueError, match="ssp contains non-finite values"):
        SSPData(ages=ages, mets=mets, wave=wave, ssp=bad_ssp)


def test_ssp_data_from_3d_grid():
    ages = np.array([1e8, 1e7])  # unsorted
    mets = np.array([0.02, 0.004])  # unsorted
    wave = np.array([2000.0, 1000.0])  # unsorted
    grid_3d = np.arange(8, dtype=np.float32).reshape(2, 2, 2)

    data = SSPData.from_3d_grid(ages=ages, mets=mets, wave=wave, grid_3d=grid_3d)
    # Check that dimensions are now sorted
    assert np.all(np.diff(data.ages) > 0)
    assert np.all(np.diff(data.mets) > 0)
    assert np.all(np.diff(data.wave) > 0)
    assert data.ssp.shape == (4, 2)


def test_ssp_data_resample_wavelength():
    ages = np.array([1e7, 1e8])
    mets = np.array([0.02])
    wave = np.array([1000.0, 2000.0, 3000.0])
    ssp = np.array([[1.0, 2.0, 3.0], [2.0, 4.0, 6.0]], dtype=np.float32)

    data = SSPData(ages=ages, mets=mets, wave=wave, ssp=ssp)
    target_wave = np.array([1500.0, 2500.0])
    resampled = data.resample_wavelength(target_wave)

    assert resampled.wave.shape == (2,)
    assert resampled.ssp.shape == (2, 2)
    assert np.isclose(resampled.ssp[0, 0], 1.5)  # halfway between 1.0 and 2.0
    assert np.isclose(resampled.ssp[1, 1], 5.0)  # halfway between 4.0 and 6.0

    # Non-monotonic target_wave
    with pytest.raises(ValueError, match="target_wave must be strictly monotonically increasing"):
        data.resample_wavelength(np.array([2500.0, 1500.0]))


def test_toy_adapter():
    adapter = ToyAdapter(n_age=5, n_met=2, n_wave=50)
    data = adapter.load()
    assert isinstance(data, SSPData)
    assert len(data.ages) == 5
    assert len(data.mets) == 2
    assert len(data.wave) == 50
    assert data.ssp.shape == (10, 50)
    assert data.metadata.get("model") == "toy"


def test_get_adapter_factory():
    toy = get_adapter("toy", n_age=10, n_met=3, n_wave=100)
    assert isinstance(toy, ToyAdapter)

    bc03 = get_adapter("bc03", path="mock.spec")
    assert isinstance(bc03, BC03Adapter)

    emiles = get_adapter("emiles", path="mock_dir")
    assert isinstance(emiles, EMILESAdapter)

    fits = get_adapter("fits", filepath="mock.fits")
    assert isinstance(fits, FITSGridAdapter)

    fsps = get_adapter("fsps", filepath="mock.fsps")
    assert isinstance(fsps, FSPSAdapter)

    with pytest.raises(ValueError, match="Unknown adapter"):
        get_adapter("nonexistent_model")


def test_ssp_data_from_3d_grid_shape_mismatch():
    ages = np.array([1e7, 1e8])
    mets = np.array([0.02])
    wave = np.array([1000.0, 2000.0])
    bad_grid = np.zeros((3, 1, 2), dtype=np.float32)  # 3 != 2 ages
    with pytest.raises(ValueError, match="grid_3d shape"):
        SSPData.from_3d_grid(ages=ages, mets=mets, wave=wave, grid_3d=bad_grid)


def test_bc03_adapter_ascii(tmp_path):
    # Create mock ASCII file: column 0 = wavelength, columns 1..N = flux at ages
    wave = np.linspace(1000, 3000, 20)
    flux1 = np.ones(20) * 1.5
    flux2 = np.ones(20) * 2.5
    table = np.column_stack([wave, flux1, flux2])

    ascii_file = tmp_path / "bc2003_lr_m62_chab_ssp.spec"
    np.savetxt(ascii_file, table)

    adapter = BC03Adapter(path=ascii_file)
    data = adapter.load()
    assert len(data.wave) == 20
    assert len(data.mets) == 1
    assert data.mets[0] == 0.02  # inferred from 'm62'
    assert data.ssp.shape == (2, 20)


def test_bc03_adapter_ised_binary(tmp_path):
    # Create a mock Fortran unformatted .ised file
    n_age = 3
    n_wave = 5
    ages = np.array([1e7, 1e8, 1e9], dtype=np.float32)
    wave = np.array([1000.0, 2000.0, 3000.0, 4000.0, 5000.0], dtype=np.float32)

    ised_file = tmp_path / "bc2003_lr_m42_chab_ssp.ised"
    with open(ised_file, "wb") as f:
        # Record 1: ages
        rec1_payload = struct.pack("=i", n_age) + ages.tobytes()
        f.write(struct.pack("=i", len(rec1_payload)) + rec1_payload + struct.pack("=i", len(rec1_payload)))

        # Record 2: wavelengths
        rec2_payload = struct.pack("=i", n_wave) + wave.tobytes()
        f.write(struct.pack("=i", len(rec2_payload)) + rec2_payload + struct.pack("=i", len(rec2_payload)))

        # Spectra records per age
        for a in ages:
            flux = np.ones(n_wave, dtype=np.float32) * (a / 1e8)
            f.write(struct.pack("=i", len(flux.tobytes())) + flux.tobytes() + struct.pack("=i", len(flux.tobytes())))

    adapter = BC03Adapter(path=ised_file)
    data = adapter.load()
    assert len(data.ages) == 3
    assert len(data.wave) == 5
    assert data.mets[0] == 0.004  # inferred from 'm42'
    assert data.ssp.shape == (3, 5)


def test_fits_grid_adapter_npz(tmp_path):
    npz_file = tmp_path / "test_grid.npz"
    ages = np.array([1e7, 5e8, 1e9])
    mets = np.array([0.008, 0.02])
    wave = np.linspace(3000, 7000, 40)
    grid_3d = np.ones((len(ages), len(mets), len(wave)), dtype=np.float32)

    np.savez(npz_file, age=ages, met=mets, wave=wave, ssp=grid_3d)

    adapter = FITSGridAdapter(filepath=npz_file, age_key="age", met_key="met", wave_key="wave", flux_key="ssp")
    data = adapter.load()
    assert len(data.ages) == 3
    assert len(data.mets) == 2
    assert len(data.wave) == 40
    assert data.ssp.shape == (6, 40)


def test_emiles_adapter_directory(tmp_path):
    # Create mock FITS files matching E-MILES filename conventions:
    # Ebi1.30Zp0.06T01.0000_iTp0.00_baseFe.fits
    # Ebi1.30Zm0.40T05.0000_iTp0.00_baseFe.fits
    n_wave = 10
    crval1, cdelt1 = 3500.0, 100.0

    def write_mock_fits(filepath, flux_val):
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
            data = np.full(n_wave, flux_val, dtype=np.float32)
            fits.writeto(filepath, data, hdr, overwrite=True)
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
            data = np.full(n_wave, flux_val, dtype=">f4")
            data_bytes = data.tobytes()
            rem_d = len(data_bytes) % 2880
            if rem_d != 0:
                data_bytes += b"\x00" * (2880 - rem_d)
            with open(filepath, "wb") as fp:
                fp.write(hdr_bytes)
                fp.write(data_bytes)

    f1 = tmp_path / "Ebi1.30Zp0.06T01.0000_iTp0.00_baseFe.fits"
    f2 = tmp_path / "Ebi1.30Zm0.40T05.0000_iTp0.00_baseFe.fits"
    write_mock_fits(f1, 2.0)
    write_mock_fits(f2, 3.0)

    adapter = EMILESAdapter(path=tmp_path)
    data = adapter.load()
    assert len(data.ages) == 2
    assert len(data.mets) == 2
    assert len(data.wave) == 10
    assert np.isclose(data.wave[0], 3500.0)
    assert np.isclose(data.wave[-1], 3500.0 + 9 * 100.0)
    assert data.ssp.shape == (4, 10)


def test_fsps_adapter_ascii_file(tmp_path):
    # Mock ASCII spstot_*.spec output from Fortran FSPS
    wave = np.linspace(1000, 5000, 15)
    flux1 = np.ones(15) * 0.8
    flux2 = np.ones(15) * 1.6
    table = np.column_stack([wave, flux1, flux2])

    fsps_file = tmp_path / "spstot_chabrier.spec"
    np.savetxt(fsps_file, table, header="15 wavelengths, 2 age steps")

    adapter = FSPSAdapter(filepath=fsps_file, metallicity=0.019)
    data = adapter.load()
    assert len(data.wave) == 15
    assert len(data.mets) == 1
    assert data.ssp.shape == (2, 15)


def test_fsps_adapter_import_error():
    # If python-fsps is not installed, calling load() without a filepath should raise an informative ImportError
    adapter = FSPSAdapter()
    try:
        import fsps
    except ImportError:
        with pytest.raises(ImportError, match="python-fsps is required"):
            adapter.load()
