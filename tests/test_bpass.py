import os
import tempfile
from pathlib import Path
import numpy as np
import pytest

from specsynth.adapters import get_adapter
from specsynth.adapters.bpass import BPASSAdapter


def test_bpass_adapter_factory():
    adapter = get_adapter("bpass", input_file="fake.dat", metallicity=0.01)
    assert isinstance(adapter, BPASSAdapter)


def test_bpass_adapter_missing_metallicity_single_file():
    with tempfile.NamedTemporaryFile(suffix=".dat", delete=False) as tf:
        tf.write(b"1000.0 " + b"1.0 " * 51 + b"\n")
        path = tf.name
    try:
        adapter = BPASSAdapter(input_file=path)
        with pytest.raises(ValueError, match="Explicit --metallicity must be provided"):
            adapter.load()
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_bpass_adapter_invalid_column_count():
    with tempfile.NamedTemporaryFile(suffix=".dat", delete=False) as tf:
        tf.write(b"1000.0\n2000.0\n")
        path = tf.name
    try:
        adapter = BPASSAdapter(input_file=path, metallicity=0.02)
        with pytest.raises(ValueError, match="Expected at least 2 columns"):
            adapter.load()
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_bpass_adapter_empty_directory():
    with tempfile.TemporaryDirectory() as td:
        adapter = BPASSAdapter(input_path=td)
        with pytest.raises(FileNotFoundError, match="No BPASS .dat or .txt files found"):
            adapter.load()


def test_bpass_adapter_directory_success():
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        f1 = tdp / "spectra-bin-imf135_300.z001.dat"
        f2 = tdp / "spectra-bin-imf135_300.z020.dat"

        wave = np.array([1000.0, 1500.0, 2000.0])
        ages = 10 ** np.linspace(6.0, 11.0, 51)

        def write_bpass_file(path, factor):
            with open(path, "w") as f:
                f.write("# BPASS test header\n")
                for w in wave:
                    row = [f"{w:.1f}"] + [f"{factor * (w/1000.0):.4e}"] * 51
                    f.write(" ".join(row) + "\n")

        write_bpass_file(f1, 1.0)
        write_bpass_file(f2, 2.0)

        adapter = BPASSAdapter(input_path=td)
        ssp_data = adapter.load()

        assert ssp_data.ssp.shape == (51 * 2, len(wave))
        assert len(ssp_data.ages) == 51
        assert len(ssp_data.mets) == 2
        assert np.isclose(ssp_data.mets[0], 0.001)
        assert np.isclose(ssp_data.mets[1], 0.02)
        assert np.all(ssp_data.ssp > 0.0)
