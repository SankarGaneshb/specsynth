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


@pytest.mark.critical
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


@pytest.mark.critical
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


@pytest.mark.critical
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


@pytest.mark.critical
def test_toy_adapter():
    adapter = ToyAdapter(n_age=5, n_met=2, n_wave=50)
    data = adapter.load()
    assert isinstance(data, SSPData)
    assert len(data.ages) == 5
    assert len(data.mets) == 2
    assert len(data.wave) == 50
    assert data.ssp.shape == (10, 50)
    assert data.metadata.get("model") == "toy"


@pytest.mark.critical
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


@pytest.mark.critical
def test_ssp_data_from_3d_grid_shape_mismatch():
    ages = np.array([1e7, 1e8])
    mets = np.array([0.02])
    wave = np.array([1000.0, 2000.0])
    bad_grid = np.zeros((3, 1, 2), dtype=np.float32)  # 3 != 2 ages
    with pytest.raises(ValueError, match="grid_3d shape"):
        SSPData.from_3d_grid(ages=ages, mets=mets, wave=wave, grid_3d=bad_grid)


@pytest.mark.astrophysics
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


@pytest.mark.astrophysics
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


@pytest.mark.astrophysics
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


@pytest.mark.astrophysics
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


@pytest.mark.astrophysics
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


@pytest.mark.astrophysics
def test_fsps_adapter_import_error(monkeypatch):
    # Ensure attempting to load without python-fsps raises an informative ImportError
    import sys
    monkeypatch.setitem(sys.modules, "fsps", None)
    adapter = FSPSAdapter()
    with pytest.raises(ImportError, match="python-fsps is required"):
        adapter.load()


# ---------------------------------------------------------------------------
# Additional In-Depth Adapter Tests: FITSGrid, EMILES, FSPS, BC03
# ---------------------------------------------------------------------------

@pytest.mark.astrophysics
def test_fits_grid_adapter_fits_image_and_bintable(tmp_path):
    from astropy.io import fits

    # 1. ImageHDU format
    fits_image_file = tmp_path / "image_grid.fits"
    hdul = fits.HDUList([
        fits.PrimaryHDU(data=np.ones((2, 2, 5), dtype=np.float32)),
        fits.ImageHDU(data=np.array([1e7, 1e8]), name="AGE"),
        fits.ImageHDU(data=np.array([0.004, 0.02]), name="MET"),
        fits.ImageHDU(data=np.linspace(3000, 7000, 5), name="WAVE"),
    ])
    hdul.writeto(fits_image_file, overwrite=True)

    adapter = FITSGridAdapter(fits_image_file)
    data = adapter.load()
    assert data.ssp.shape == (4, 5)
    assert len(data.ages) == 2
    assert len(data.mets) == 2
    assert len(data.wave) == 5

    # 2. BinTableHDU format with alternate naming
    fits_bintable_file = tmp_path / "bintable_grid.fits"
    col_flux = fits.Column(name="FLUXES", format="5E", array=np.ones((4, 5), dtype=np.float32))
    hdul_table = fits.HDUList([
        fits.PrimaryHDU(),
        fits.ImageHDU(data=np.linspace(3000, 7000, 5), name="WAVELENGTH"),
        fits.ImageHDU(data=np.array([1e7, 1e8]), name="LOG_AGE"),
        fits.ImageHDU(data=np.array([0.004, 0.02]), name="Z"),
        fits.BinTableHDU.from_columns([col_flux]),
    ])
    hdul_table.writeto(fits_bintable_file, overwrite=True)

    adapter_table = FITSGridAdapter(fits_bintable_file)
    data_table = adapter_table.load()
    assert data_table.ssp.shape == (4, 5)


@pytest.mark.astrophysics
def test_fits_grid_adapter_hdf5(tmp_path):
    import h5py

    h5_file = tmp_path / "test_grid.h5"
    with h5py.File(h5_file, "w") as hf:
        hf.create_dataset("wavelength", data=np.linspace(3000, 7000, 6))
        hf.create_dataset("age", data=np.array([1e7, 1e8, 1e9]))
        hf.create_dataset("z", data=np.array([0.004, 0.02]))
        hf.create_dataset("fluxes", data=np.ones((3, 2, 6), dtype=np.float32))

    adapter = FITSGridAdapter(h5_file)
    data = adapter.load()
    assert data.ssp.shape == (6, 6)
    assert len(data.ages) == 3
    assert len(data.mets) == 2
    assert len(data.wave) == 6


@pytest.mark.astrophysics
def test_fits_grid_adapter_errors_and_branches(tmp_path, monkeypatch):
    import sys
    from astropy.io import fits
    import h5py

    # 1. Missing file
    missing = tmp_path / "non_existent.fits"
    with pytest.raises(FileNotFoundError, match="File not found"):
        FITSGridAdapter(missing).load()

    # 2. Unsupported extension
    unsupported = tmp_path / "bad.txt"
    unsupported.touch()
    with pytest.raises(ValueError, match="Unsupported grid format"):
        FITSGridAdapter(unsupported).load()

    # 3. Missing key in FITS
    bad_fits = tmp_path / "bad_keys.fits"
    fits.HDUList([
        fits.PrimaryHDU(data=np.ones((2, 2, 5), dtype=np.float32)),
        fits.ImageHDU(data=np.array([1e7, 1e8]), name="AGE"),
    ]).writeto(bad_fits, overwrite=True)
    with pytest.raises(KeyError, match="Could not find array"):
        FITSGridAdapter(bad_fits).load()

    # 4. Missing key in HDF5
    bad_h5 = tmp_path / "bad_keys.h5"
    with h5py.File(bad_h5, "w") as hf:
        hf.create_dataset("age", data=np.array([1e7, 1e8]))
    with pytest.raises(KeyError, match="Could not find dataset"):
        FITSGridAdapter(bad_h5).load()

    # 5. Missing key in NPZ
    bad_npz = tmp_path / "bad_keys.npz"
    np.savez(bad_npz, age=np.array([1e7]))
    with pytest.raises(KeyError, match="Could not find array matching"):
        FITSGridAdapter(bad_npz).load()

    # 6. Age unit conversions: log10(yr) (> 5.0 and < 100.0)
    log_npz = tmp_path / "log_age.npz"
    np.savez(
        log_npz,
        wave=np.array([4000.0, 5000.0]),
        age=np.array([7.0, 8.0]),
        met=np.array([0.004, 0.02]),
        ssp=np.ones((2, 2, 2), dtype=np.float32),
    )
    d_log = FITSGridAdapter(log_npz).load()
    assert np.allclose(d_log.ages, [1e7, 1e8])

    # 7. Age unit conversions: Gyr (<= 5.0 and < 100.0)
    gyr_npz = tmp_path / "gyr_age.npz"
    np.savez(
        gyr_npz,
        wave=np.array([4000.0, 5000.0]),
        age=np.array([0.01, 1.0]),
        met=np.array([0.004, 0.02]),
        ssp=np.ones((2, 2, 2), dtype=np.float32),
    )
    d_gyr = FITSGridAdapter(gyr_npz).load()
    assert np.allclose(d_gyr.ages, [1e7, 1e9])

    # 8. 2D flux array in NPZ
    npz_2d = tmp_path / "grid_2d.npz"
    np.savez(
        npz_2d,
        wave=np.array([4000.0, 5000.0]),
        age=np.array([1e7, 1e8]),
        met=np.array([0.02]),
        ssp=np.ones((2, 2), dtype=np.float32),
    )
    d_2d = FITSGridAdapter(npz_2d).load()
    assert d_2d.ssp.shape == (2, 2)

    # 9. Invalid flux ndim (e.g. 1D or 4D)
    npz_bad_dim = tmp_path / "grid_bad_dim.npz"
    np.savez(
        npz_bad_dim,
        wave=np.array([4000.0, 5000.0]),
        age=np.array([1e7]),
        met=np.array([0.02]),
        ssp=np.ones(2, dtype=np.float32),
    )
    with pytest.raises(ValueError, match="Flux array must be 2D or 3D"):
        FITSGridAdapter(npz_bad_dim).load()

    # 10. Missing astropy / h5py import errors
    import builtins
    orig_import = builtins.__import__

    def mock_missing_astropy(name, *args, **kwargs):
        if "astropy" in name:
            raise ImportError("No module named astropy")
        return orig_import(name, *args, **kwargs)

    valid_fits = tmp_path / "valid.fits"
    valid_fits.touch()
    monkeypatch.setattr(builtins, "__import__", mock_missing_astropy)
    with pytest.raises(ImportError, match="astropy is required"):
        FITSGridAdapter(valid_fits).load()

    def mock_missing_h5py(name, *args, **kwargs):
        if "h5py" in name:
            raise ImportError("No module named h5py")
        return orig_import(name, *args, **kwargs)

    valid_h5 = tmp_path / "valid.h5"
    valid_h5.touch()
    monkeypatch.setattr(builtins, "__import__", mock_missing_h5py)
    with pytest.raises(ImportError, match="h5py is required"):
        FITSGridAdapter(valid_h5).load()


@pytest.mark.astrophysics
def test_emiles_pure_python_fits_reader(tmp_path, monkeypatch):
    import sys
    from specsynth.adapters.emiles import read_fits_1d_spectrum

    # Disable astropy to test pure-Python fallback reader
    monkeypatch.setitem(sys.modules, "astropy", None)
    monkeypatch.setitem(sys.modules, "astropy.io", None)
    monkeypatch.setitem(sys.modules, "astropy.io.fits", None)

    # Valid FITS file
    cards = [
        "SIMPLE  =                    T",
        "BITPIX  =                  -32",
        "NAXIS   =                    1",
        "NAXIS1  =                    5",
        "CRVAL1  =               3500.0",
        "CDELT1  =                100.0",
        "CRPIX1  =                  1.0",
        "END",
    ]
    hdr_bytes = "".join(c.ljust(80) for c in cards).encode("ascii")
    rem = len(hdr_bytes) % 2880
    if rem != 0:
        hdr_bytes += b" " * (2880 - rem)
    data = np.array([1.0, 2.0, 3.0, 4.0, 5.0], dtype=">f4")
    data_bytes = data.tobytes()
    rem_d = len(data_bytes) % 2880
    if rem_d != 0:
        data_bytes += b"\x00" * (2880 - rem_d)

    fits_file = tmp_path / "pure_python.fits"
    with open(fits_file, "wb") as fp:
        fp.write(hdr_bytes)
        fp.write(data_bytes)

    w, flx, hdr = read_fits_1d_spectrum(fits_file)
    assert len(w) == 5
    assert len(flx) == 5
    assert np.allclose(w, [3500.0, 3600.0, 3700.0, 3800.0, 3900.0])
    assert np.allclose(flx, [1.0, 2.0, 3.0, 4.0, 5.0])

    # Empty file error
    empty_file = tmp_path / "empty.fits"
    empty_file.touch()
    with pytest.raises(ValueError, match="Corrupted or empty FITS file"):
        read_fits_1d_spectrum(empty_file)

    # Incomplete data error
    bad_data_file = tmp_path / "bad_data.fits"
    with open(bad_data_file, "wb") as fp:
        fp.write(hdr_bytes)
        fp.write(b"\x00" * 4)  # Less than 5 * 4 = 20 bytes
    with pytest.raises(ValueError, match="Incomplete data array"):
        read_fits_1d_spectrum(bad_data_file)


@pytest.mark.astrophysics
def test_emiles_single_file_and_errors(tmp_path):
    from astropy.io import fits

    def write_simple_fits(path, n_wave=5, crval1=3500.0, cdelt1=100.0, flux_val=1.0):
        hdr = fits.Header()
        hdr["SIMPLE"] = True
        hdr["BITPIX"] = -32
        hdr["NAXIS"] = 1
        hdr["NAXIS1"] = n_wave
        hdr["CRVAL1"] = crval1
        hdr["CDELT1"] = cdelt1
        hdr["CRPIX1"] = 1.0
        data = np.full(n_wave, flux_val, dtype=np.float32)
        fits.writeto(path, data, hdr, overwrite=True)

    # 1. Single file with matching EMILES filename
    matched_single = tmp_path / "Ebi1.30Zp0.06T02.5000_iTp0.00_baseFe.fits"
    write_simple_fits(matched_single, n_wave=5, flux_val=2.5)
    ad_s = EMILESAdapter(matched_single)
    d_s = ad_s.load()
    assert d_s.ssp.shape == (1, 5)
    assert np.isclose(d_s.ages[0], 2.5e9)
    assert np.isclose(d_s.mets[0], 0.019 * (10.0**0.06))

    # 2. Single file with non-matching filename (fallback Z and age)
    unmatched_single = tmp_path / "custom_model.fits"
    write_simple_fits(unmatched_single, n_wave=5)
    ad_un = EMILESAdapter(unmatched_single)
    d_un = ad_un.load()
    assert d_un.ssp.shape == (1, 5)
    assert np.isclose(d_un.ages[0], 1e9)
    assert np.isclose(d_un.mets[0], 0.019)

    # 3. Non-existent path
    with pytest.raises(FileNotFoundError, match="does not exist"):
        EMILESAdapter(tmp_path / "non_existent_dir").load()

    # 4. Empty directory
    empty_dir = tmp_path / "empty_dir"
    empty_dir.mkdir()
    with pytest.raises(FileNotFoundError, match="No FITS files found"):
        EMILESAdapter(empty_dir).load()

    # 5. IMF filter matching nothing
    filter_dir = tmp_path / "filter_dir"
    filter_dir.mkdir()
    write_simple_fits(filter_dir / "Ebi1.30Zp0.06T01.0000_iTp0.00_baseFe.fits")
    with pytest.raises(ValueError, match="matched IMF filter"):
        EMILESAdapter(filter_dir, imf_filter="kroupa").load()

    # 6. Unparseable filenames
    unparseable_dir = tmp_path / "unparseable_dir"
    unparseable_dir.mkdir()
    write_simple_fits(unparseable_dir / "other_model.fits")
    with pytest.raises(ValueError, match="Could not parse E-MILES filename"):
        EMILESAdapter(unparseable_dir).load()

    # 7. Multiple files with differing wavelength grids (triggers interpolation) and duplicates
    interp_dir = tmp_path / "interp_dir"
    interp_dir.mkdir()
    f1 = interp_dir / "Ebi1.30Zp0.06T01.0000_iTp0.00_baseFe.fits"
    f2 = interp_dir / "Ebi1.30Zm0.40T05.0000_iTp0.00_baseFe.fits"
    # Duplicate with same age and met
    f3 = interp_dir / "Ebi1.30Zm0.40T05.0000_iTp0.00_baseFe_dup.fits"
    write_simple_fits(f1, n_wave=8, crval1=3500.0, cdelt1=100.0, flux_val=2.0)
    write_simple_fits(f2, n_wave=10, crval1=3400.0, cdelt1=90.0, flux_val=3.0)
    write_simple_fits(f3, n_wave=10, crval1=3400.0, cdelt1=90.0, flux_val=3.0)

    ad_interp = EMILESAdapter(interp_dir)
    d_interp = ad_interp.load()
    assert d_interp.ssp.shape == (4, 10)
    assert len(d_interp.wave) == 10


@pytest.mark.astrophysics
def test_fsps_parse_spec_file_invalid(tmp_path):
    from specsynth.adapters.fsps import parse_fsps_spec_file

    # 1D array raising ValueError
    bad_file = tmp_path / "bad_1d.spec"
    np.savetxt(bad_file, np.array([1000.0, 2000.0, 3000.0]))
    with pytest.raises(ValueError, match="Unable to automatically parse FSPS table"):
        parse_fsps_spec_file(bad_file)


@pytest.mark.astrophysics
def test_fsps_dynamic_mode_mocked(monkeypatch):
    import sys
    from unittest.mock import MagicMock

    mock_fsps = MagicMock()
    mock_sp = MagicMock()
    mock_fsps.StellarPopulation.return_value = mock_sp
    mock_sp.zlegend = np.array([-0.4, 0.0])
    mock_sp.wavelengths = np.linspace(3000, 7000, 5)
    mock_sp.params = {}
    mock_sp.get_spectrum.return_value = (None, np.ones(5, dtype=np.float32) * 2.0)

    monkeypatch.setitem(sys.modules, "fsps", mock_fsps)

    # 1. Default metallicities=None (uses sp.zlegend)
    ad1 = FSPSAdapter(ages=[1e7, 1e8])
    d1 = ad1.load()
    assert d1.ssp.shape == (4, 5)
    assert len(d1.mets) == 2
    assert np.allclose(d1.mets, [(10.0**-0.4) * 0.019, 0.019])

    # 2. Explicit metallicities and string IMF
    ad2 = FSPSAdapter(
        ages=[1e7, 1e8, 1e9],
        metallicities=[0.004, 0.02],
        imf_type="salpeter",
        add_nebular_emission=True,
    )
    d2 = ad2.load()
    assert d2.ssp.shape == (6, 5)
    assert len(d2.mets) == 2
    assert d2.metadata["imf"] == "salpeter"
    assert d2.metadata["nebular"] is True

    # 3. Numeric IMF code
    ad3 = FSPSAdapter(ages=[1e7], metallicities=[0.02], imf_type=1)
    d3 = ad3.load()
    assert d3.ssp.shape == (1, 5)


@pytest.mark.astrophysics
def test_bc03_fortran_record_errors(tmp_path):
    from specsynth.adapters.bc03 import read_fortran_record

    # Corrupt tail: EOF before tail
    bad_rec1 = tmp_path / "bad_rec1.bin"
    with open(bad_rec1, "wb") as f:
        f.write(struct.pack("=i", 8) + b"12345678")  # No end length (4 bytes)
    with open(bad_rec1, "rb") as f:
        with pytest.raises(ValueError, match="unexpected EOF waiting for tail length"):
            read_fortran_record(f)

    # Mismatched length: start != end
    bad_rec2 = tmp_path / "bad_rec2.bin"
    with open(bad_rec2, "wb") as f:
        f.write(struct.pack("=i", 8) + b"12345678" + struct.pack("=i", 4))
    with open(bad_rec2, "rb") as f:
        with pytest.raises(ValueError, match="start 8 != end 4"):
            read_fortran_record(f)


@pytest.mark.astrophysics
def test_bc03_parse_ised_errors_and_alternate_layout(tmp_path):
    from specsynth.adapters.bc03 import parse_ised_binary

    # 1. Empty file
    empty_file = tmp_path / "empty.ised"
    empty_file.touch()
    with pytest.raises(ValueError, match="Empty or invalid .ised file"):
        parse_ised_binary(empty_file)

    # 2. Alternate packed layout
    n_age, n_wave = 2, 3
    ages = np.array([1e7, 1e8], dtype=np.float32)
    wave = np.array([1000.0, 2000.0, 3000.0], dtype=np.float32)
    rec1 = struct.pack("=i", n_age) + ages.tobytes()
    rec2 = struct.pack("=i", n_wave) + wave.tobytes()
    all_flux = np.ones(n_age * n_wave, dtype=np.float32) * 5.0

    alt_file = tmp_path / "alt_layout.ised"
    with open(alt_file, "wb") as f:
        f.write(struct.pack("=i", len(rec1)) + rec1 + struct.pack("=i", len(rec1)))
        f.write(struct.pack("=i", len(rec2)) + rec2 + struct.pack("=i", len(rec2)))
        # 0-length record to break individual record loop without parsing fluxes
        f.write(struct.pack("=i", 0) + struct.pack("=i", 0))
        # Packed record with all fluxes
        f.write(struct.pack("=i", len(all_flux.tobytes())) + all_flux.tobytes() + struct.pack("=i", len(all_flux.tobytes())))

    a, w, flx = parse_ised_binary(alt_file)
    assert flx.shape == (2, 3)
    assert np.allclose(flx, 5.0)

    # 3. Mismatched flux count
    mismatch_file = tmp_path / "mismatch.ised"
    with open(mismatch_file, "wb") as f:
        # Record 1: 3 ages
        rec_m1 = struct.pack("=i", 3) + np.array([1e7, 1e8, 1e9], dtype=np.float32).tobytes()
        f.write(struct.pack("=i", len(rec_m1)) + rec_m1 + struct.pack("=i", len(rec_m1)))
        # Record 2: 3 waves
        rec_m2 = struct.pack("=i", 3) + np.array([1000.0, 2000.0, 3000.0], dtype=np.float32).tobytes()
        f.write(struct.pack("=i", len(rec_m2)) + rec_m2 + struct.pack("=i", len(rec_m2)))
        # Only 1 flux record written
        rec_flux = np.ones(3, dtype=np.float32).tobytes()
        f.write(struct.pack("=i", len(rec_flux)) + rec_flux + struct.pack("=i", len(rec_flux)))

    with pytest.raises(ValueError, match="Expected 3 age spectra"):
        parse_ised_binary(mismatch_file)


@pytest.mark.astrophysics
def test_bc03_directory_mode_and_errors(tmp_path):
    # 1. Directory with multiple ASCII .spec files (m42 and m62)
    ascii_dir = tmp_path / "bc03_ascii_dir"
    ascii_dir.mkdir()
    wave = np.linspace(1000, 3000, 5)
    f_m42 = np.column_stack([wave, np.ones(5) * 1.0, np.ones(5) * 1.5])
    f_m62 = np.column_stack([wave, np.ones(5) * 2.0, np.ones(5) * 2.5])
    np.savetxt(ascii_dir / "bc03_m42.spec", f_m42)
    np.savetxt(ascii_dir / "bc03_m62.spec", f_m62)

    ad_dir = BC03Adapter(ascii_dir)
    data_dir = ad_dir.load()
    assert data_dir.ssp.shape == (4, 5)
    assert len(data_dir.mets) == 2
    assert np.allclose(data_dir.mets, [0.004, 0.02])

    # 2. Directory with multiple .ised binary files
    ised_dir = tmp_path / "bc03_ised_dir"
    ised_dir.mkdir()
    def write_mini_ised(filepath):
        n_age, n_wave = 2, 4
        ages = np.array([1e7, 1e8], dtype=np.float32)
        wave = np.array([1000.0, 2000.0, 3000.0, 4000.0], dtype=np.float32)
        r1 = struct.pack("=i", n_age) + ages.tobytes()
        r2 = struct.pack("=i", n_wave) + wave.tobytes()
        with open(filepath, "wb") as f:
            f.write(struct.pack("=i", len(r1)) + r1 + struct.pack("=i", len(r1)))
            f.write(struct.pack("=i", len(r2)) + r2 + struct.pack("=i", len(r2)))
            for _ in range(n_age):
                flx = np.ones(n_wave, dtype=np.float32).tobytes()
                f.write(struct.pack("=i", len(flx)) + flx + struct.pack("=i", len(flx)))

    write_mini_ised(ised_dir / "bc03_m32.ised")
    write_mini_ised(ised_dir / "bc03_m52.ised")
    ad_ised = BC03Adapter(ised_dir)
    data_ised = ad_ised.load()
    assert data_ised.ssp.shape == (4, 4)
    assert len(data_ised.mets) == 2
    assert np.allclose(data_ised.mets, [0.0004, 0.008])

    # 3. Non-existent path
    with pytest.raises(FileNotFoundError, match="Path does not exist"):
        BC03Adapter(tmp_path / "ghost_path").load()

    # 4. Empty directory
    empty_dir = tmp_path / "empty_dir"
    empty_dir.mkdir()
    with pytest.raises(FileNotFoundError, match="No BC03 model files"):
        BC03Adapter(empty_dir).load()

    # 5. Directory with unparseable metallicity files
    bad_code_dir = tmp_path / "bad_code_dir"
    bad_code_dir.mkdir()
    np.savetxt(bad_code_dir / "unrelated.spec", f_m42)
    with pytest.raises(ValueError, match="Could not infer metallicity codes"):
        BC03Adapter(bad_code_dir).load()

    # 6. Single file with unmatched metallicity code (falls back to solar 0.02)
    unmatched_file = tmp_path / "no_code_model.spec"
    np.savetxt(unmatched_file, f_m42)
    ad_fallback = BC03Adapter(unmatched_file)
    data_fallback = ad_fallback.load()
    assert data_fallback.mets[0] == 0.02

