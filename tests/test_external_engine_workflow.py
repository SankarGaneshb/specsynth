"""
Automated Test Suite for Genuine External-Engine Conformance & Workflow (Issue #28 / P6).
========================================================================================
Validates:
1. Dynamic entry point discovery of third-party external adapters with zero core modifications.
2. 11-point scientific and architectural conformance suite on external reference adapter.
3. End-to-end forward modeling matching independent float64 reference integration (|Δm| < 0.005 mag).
4. Deterministic numerical reproducibility across repeated workflow executions.
5. Strict truth-in-labeling: CB2026 mock fixture is quarantined (is_mock=True, data_mode="illustrative_demo").
6. Dimensional correctness and AB magnitude zero-point compliance with Astropy standards.
"""

from __future__ import annotations

import math
from pathlib import Path
import sys

import numpy as np
import pytest

# Ensure external plugin directory is importable
plugin_dir = Path(__file__).parents[1] / "examples" / "external_engine_plugin"
if str(plugin_dir) not in sys.path:
    sys.path.insert(0, str(plugin_dir))

from specsynth.adapters import (
    assert_adapter_conforms,
    discover_entry_point_adapters,
    get_adapter,
    list_adapters,
)
from specsynth.contracts import (
    PhotometryPointContract,
    SSPGridContract,
    SyntheticObservationContract,
)
from specsynth.filters import C_AA_S, flux_to_ab_mag, get_filter

from cb2026_engine import CB2026Engine
from external_adapter import CB2026Adapter
from fsps_external_adapter import FSPSExternalAdapter
from run_genuine_external_workflow import run_genuine_conformance_workflow

pytestmark = pytest.mark.astrophysics


def test_external_engine_entry_point_discovery():
    """Verify external adapters are discoverable via entry points without core modifications."""
    discovered = discover_entry_point_adapters()
    assert "fsps_external" in discovered or "fsps_external" in list_adapters()
    assert "cb2026_mock" in discovered or "cb2026" in list_adapters()

    adapter = get_adapter("fsps_external")
    assert isinstance(adapter, FSPSExternalAdapter)
    caps = adapter.get_capabilities()
    assert caps["is_mock"] is False
    assert caps["data_mode"] == "genuine_external_engine"
    assert caps["zero_core_mod"] is True


def test_fsps_external_adapter_conformance():
    """Verify FSPSExternalAdapter satisfies all 11 scientific invariants of the conformance suite."""
    result = assert_adapter_conforms(FSPSExternalAdapter, verbose=False)
    assert result.passed, f"Conformance checks failed: {result.errors}"
    assert len(result.errors) == 0


def test_fsps_external_grid_loading_and_contract_validation():
    """Verify authentic FSPS grid loads cleanly and passes canonical SSPGridContract validation."""
    adapter = FSPSExternalAdapter()
    ssp_data = adapter.load()

    assert len(ssp_data.ages) == 25
    assert len(ssp_data.mets) >= 1
    assert len(ssp_data.wave) == 2500
    assert ssp_data.ssp.shape == (len(ssp_data.ages) * len(ssp_data.mets), len(ssp_data.wave))
    assert np.all(np.isfinite(ssp_data.ssp))
    assert np.all(ssp_data.ssp >= 0.0)

    contract = SSPGridContract(
        source_engine="fsps",
        engine_version="3.2",
        imf="chabrier",
        isochrones="mist_v1.2",
        ages_yr=ssp_data.ages,
        mets_z=ssp_data.mets,
        wave_angstrom=ssp_data.wave,
        ssp_flux_2d=ssp_data.ssp,
        metadata={"data_mode": "genuine_external_engine", "is_mock": False},
    )
    contract.validate()


def test_end_to_end_photometric_parity_with_independent_reference(tmp_path):
    """
    Verify end-to-end synthetic forward modeling achieves |Δm_AB| < 0.005 mag
    parity against an independent float64 trapezoidal reference integration.
    """
    manifest_file = tmp_path / "test_manifest.json"
    result = run_genuine_conformance_workflow(
        galaxy_id="TEST-GALAXY-P6",
        redshift=1.5,
        tolerance_mag=0.005,
        manifest_output_path=manifest_file,
    )

    assert result["parity_passed"] is True
    assert result["max_delta_mag"] < 0.005
    assert manifest_file.exists()

    # Check that all 6 JWST NIRCam bands pass individual parity
    for fname, delta in result["delta_mags"].items():
        assert delta < 0.005, f"Filter {fname} exceeded tolerance: Δm = {delta:.4f} mag"


def test_workflow_deterministic_reproducibility():
    """Verify that rerunning the identical workflow reproduces exact photometric outputs."""
    res1 = run_genuine_conformance_workflow(galaxy_id="REPRO-001", redshift=2.0)
    res2 = run_genuine_conformance_workflow(galaxy_id="REPRO-001", redshift=2.0)

    for fname in res1["specsynth_mags"]:
        mag1 = res1["specsynth_mags"][fname]
        mag2 = res2["specsynth_mags"][fname]
        assert abs(mag1 - mag2) < 1e-6, f"Reproducibility divergence in {fname}: {mag1} vs {mag2}"


def test_mock_fixture_quarantine_and_truth_in_labeling():
    """Verify procedural CB2026 engine is quarantined and explicitly labeled as an illustrative fixture."""
    engine = CB2026Engine()
    assert engine.is_mock is True
    assert engine.data_mode == "illustrative_demo"
    assert engine.engine_type == "mock_contract_fixture"

    adapter = CB2026Adapter()
    caps = adapter.get_capabilities()
    assert caps["is_mock"] is True
    assert caps["data_mode"] == "illustrative_demo"
    assert caps["scientific_validation"] is False
    assert "Mock" in caps["full_name"] or "Mock" in caps["engine_source"]


def test_dimensional_correctness_and_ab_zero_point():
    """
    Verify dimensional correctness:
    1. A source with F_nu = 3631 Jy must yield m_AB = 0.0000 mag (< 1e-4 precision).
    2. Units conversion between F_lambda and F_nu obeys F_nu = F_lambda * lambda^2 / c.
    """
    import astropy.units as u

    # 3631 Jy standard definition
    f_nu_cgs = (3631.0 * u.Jy).to(u.erg / u.s / u.cm**2 / u.Hz).value
    mag = flux_to_ab_mag(f_nu_cgs)
    assert abs(mag) < 1e-4, f"AB magnitude zero point mismatch: {mag:.6f} mag"

    # Wavelength conversion
    wave = 15000.0  # 1.5 um in Angstroms
    f_lam = 1.0e-16  # erg/s/cm2/A
    f_nu_manual = f_lam * (wave**2) / C_AA_S
    # Cross check with Astropy
    f_lam_u = f_lam * (u.erg / u.s / u.cm**2 / u.AA)
    f_nu_astro = f_lam_u.to(u.erg / u.s / u.cm**2 / u.Hz, equivalencies=u.spectral_density(wave * u.AA)).value
    assert np.isclose(f_nu_manual, f_nu_astro, rtol=1e-5)
