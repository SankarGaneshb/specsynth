"""
Unit tests for specsynth.sfh and specsynth.provenance modules.
Enforces P1.M2.2, P1.M2.3, P1.M2.8, and P1.M2.9 scientific standards.
"""

import numpy as np
import pytest

from specsynth.provenance import (
    generate_provenance_manifest,
    get_git_commit,
    hash_array,
    hash_file,
    validate_provenance_manifest,
)
from specsynth.sfh import (
    chabrier_surviving_mass_fraction,
    compute_constant_sfh,
    compute_delayed_tau_sfh,
    document_sfr_conventions,
)


def test_document_sfr_conventions():
    doc = document_sfr_conventions()
    assert "snapshot_sfr" in doc
    assert "model_derived_sfh" in doc
    assert "formed_vs_surviving_mass" in doc


def test_chabrier_surviving_mass_fraction():
    # Young stars: fraction ~ 0.93 - 1.0
    f_young = chabrier_surviving_mass_fraction(1e6)
    assert 0.90 <= f_young <= 1.0

    # Old stars (10 Gyr): fraction ~ 0.50 - 0.70
    f_old = chabrier_surviving_mass_fraction(1e10)
    assert 0.50 <= f_old <= 0.70

    # Monotonically decreasing with age
    ages = np.array([1e6, 1e7, 1e8, 1e9, 1e10])
    f_ages = chabrier_surviving_mass_fraction(ages)
    assert np.all(np.diff(f_ages) <= 0)


def test_compute_constant_sfh():
    sfr = np.array([2.0, 10.0])  # M_sun / yr
    durations = np.array([1.0, 0.5])  # Gyr
    ages = np.logspace(6, 10, 20)
    mets = np.array([0.019])

    sfh = compute_constant_sfh(sfr, durations, ages, mets)
    assert sfh.shape == (2, 20)
    assert np.all(sfh >= 0)


def test_provenance_manifest_generation_and_validation(tmp_path):
    dummy_grid = tmp_path / "dummy.spec"
    dummy_grid.write_text("# dummy grid", encoding="utf-8")

    manifest = generate_provenance_manifest(
        galaxy_id="G12345",
        simulation_name="IllustrisTNG-100",
        redshift=1.5,
        physical_parameters={
            "log_mstar": 10.5,
            "sfr_msun_yr": 4.2,
            "tau_diffuse": 0.4,
            "tau_birth": 0.8,
        },
        engine_name="FSPS",
        engine_version="3.2",
        grid_path=dummy_grid,
        is_genuine_engine=True,
        filter_checksums={"jwst_f200w": "abcdef123456"},
        photometry_results={"jwst_f200w": 19.85},
    )

    assert validate_provenance_manifest(manifest) is True
    assert manifest["target"]["galaxy_id"] == "G12345"
    assert manifest["sps_engine"]["grid_sha256"] != ""
    assert "code_snippet" in manifest["reproducibility"]


def test_hash_helpers():
    arr1 = np.ones((10, 10), dtype=np.float32)
    arr2 = np.ones((10, 10), dtype=np.float32)
    arr3 = np.zeros((10, 10), dtype=np.float32)

    assert hash_array(arr1) == hash_array(arr2)
    assert hash_array(arr1) != hash_array(arr3)
