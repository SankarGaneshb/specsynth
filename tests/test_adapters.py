import struct
from pathlib import Path

import numpy as np
import pytest

from specsynth.adapters import (
    BC03Adapter,
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

    with pytest.raises(ValueError, match="Unknown adapter"):
        get_adapter("nonexistent_model")


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


def test_fsps_adapter_import_error():
    # If python-fsps is not installed, calling load() should raise an informative ImportError
    adapter = FSPSAdapter()
    try:
        import fsps
    except ImportError:
        with pytest.raises(ImportError, match="python-fsps is required"):
            adapter.load()
