"""
Unit & Integration Tests for Specsynth Adapter Conformance & Compatibility Policy.
Fulfills Milestone 7 (Issue #20 / Task M1.6).
"""

from __future__ import annotations

import numpy as np
import pytest

from specsynth.adapters import (
    AdapterCompatibilityPolicy,
    AdapterConformanceError,
    AdapterConformanceResult,
    BaseAdapter,
    SSPData,
    ToyAdapter,
    assert_adapter_conforms,
    register_adapter,
    unregister_adapter,
)


class GoodExternalAdapter(BaseAdapter):
    """Fully conformant simulated external adapter."""

    def __init__(self, scale: float = 1.0):
        super().__init__()
        self.scale = scale

    def load(self, wave_resample: np.ndarray | None = None) -> SSPData:
        ages = np.array([1e7, 1e8, 1e9], dtype=np.float64)
        mets = np.array([0.004, 0.02], dtype=np.float64)
        wave = np.linspace(1000.0, 10000.0, 500, dtype=np.float64)
        n_grid = len(ages) * len(mets)

        # Non-negative, finite emission spectra
        ssp = np.ones((n_grid, len(wave)), dtype=np.float32) * self.scale
        data = SSPData(ages=ages, mets=mets, wave=wave, ssp=ssp)
        if wave_resample is not None:
            return data.resample_wavelength(wave_resample)
        return data

    def validate(self) -> bool:
        return True

    def get_capabilities(self) -> dict:
        return {
            "name": "good_external",
            "imf": "chabrier",
            "resolution": "R~2000",
            "wavelength_range_aa": [1000.0, 10000.0],
            "age_range_yr": [1e7, 1e9],
            "metallicity_range": [0.004, 0.02],
        }


class BadNegativeFluxAdapter(BaseAdapter):
    """Non-conformant: returns negative flux."""

    def load(self, wave_resample: np.ndarray | None = None) -> SSPData:
        ages = np.array([1e7, 1e8], dtype=np.float64)
        mets = np.array([0.02], dtype=np.float64)
        wave = np.array([1000.0, 2000.0, 3000.0], dtype=np.float64)
        ssp = np.array([[-1.0, 2.0, 3.0], [4.0, 5.0, 6.0]], dtype=np.float32)
        return SSPData(ages=ages, mets=mets, wave=wave, ssp=ssp)

    def validate(self) -> bool:
        return True

    def get_capabilities(self) -> dict:
        return {"name": "bad_negative"}


class BadNonFiniteAdapter(BaseAdapter):
    """Non-conformant: returns NaN / Inf flux."""

    def load(self, wave_resample: np.ndarray | None = None) -> SSPData:
        ages = np.array([1e7, 1e8], dtype=np.float64)
        mets = np.array([0.02], dtype=np.float64)
        wave = np.array([1000.0, 2000.0, 3000.0], dtype=np.float64)
        ssp = np.array([[np.nan, 2.0, 3.0], [4.0, 5.0, 6.0]], dtype=np.float32)
        # Directly bypass SSPData validation for test harness check
        obj = object.__new__(SSPData)
        object.__setattr__(obj, "ages", ages)
        object.__setattr__(obj, "mets", mets)
        object.__setattr__(obj, "wave", wave)
        object.__setattr__(obj, "ssp", ssp)
        return obj

    def validate(self) -> bool:
        return True

    def get_capabilities(self) -> dict:
        return {"name": "bad_nan"}


class NotAnAdapter:
    """Class that does not inherit from BaseAdapter."""
    pass


class IncompleteAdapter(BaseAdapter):
    """Adapter missing load implementation."""
    pass


@pytest.mark.critical
def test_conformance_toy_adapter():
    """Verify built-in ToyAdapter passes full conformance test suite."""
    toy = ToyAdapter(n_age=10, n_met=3, n_wave=100)
    result = assert_adapter_conforms(toy, verbose=False)

    assert isinstance(result, AdapterConformanceResult)
    assert result.passed is True
    assert len(result.errors) == 0
    assert len(result.checks_passed) >= 10
    assert "wavelength_monotonicity" in result.checks_passed
    assert "matrix_non_negative" in result.checks_passed
    assert "resample_support" in result.checks_passed
    summary_text = result.summary()
    assert "CONFORMANT" in summary_text
    assert "ToyAdapter" in summary_text


@pytest.mark.critical
def test_conformance_good_external_adapter():
    """Verify clean third-party external adapter passes conformance."""
    result = assert_adapter_conforms(GoodExternalAdapter, verbose=False)
    assert result.passed is True
    assert len(result.errors) == 0
    assert result.grid_summary["n_age"] == 3
    assert result.grid_summary["n_met"] == 2
    assert result.grid_summary["n_wave"] == 500


@pytest.mark.critical
def test_conformance_fails_not_subclass():
    """Verify non-subclass fails conformance."""
    with pytest.raises(AdapterConformanceError, match=r"must inherit from .*BaseAdapter"):
        assert_adapter_conforms(NotAnAdapter, verbose=False)


@pytest.mark.critical
def test_conformance_fails_incomplete_adapter():
    """Verify adapter with uninstantiable / abstract methods fails."""
    with pytest.raises(AdapterConformanceError, match="Failed to instantiate|Missing load"):
        assert_adapter_conforms(IncompleteAdapter, verbose=False)


@pytest.mark.critical
def test_conformance_fails_negative_flux():
    """Verify adapter with negative flux fails conformance."""
    with pytest.raises(AdapterConformanceError, match="matrix_non_negative"):
        assert_adapter_conforms(BadNegativeFluxAdapter, verbose=False)


@pytest.mark.critical
def test_conformance_fails_non_finite_flux():
    """Verify adapter with NaN flux fails conformance."""
    with pytest.raises(AdapterConformanceError, match="matrix_finite"):
        assert_adapter_conforms(BadNonFiniteAdapter, verbose=False)


@pytest.mark.critical
def test_adapter_compatibility_policy_declaration():
    """Verify compatibility policy returns formal declaration and constraints."""
    policy = AdapterCompatibilityPolicy.get_policy_declaration()

    assert policy["specification_version"] == "1.0.0"
    assert "min_python_version" in policy
    assert policy["required_base_class"] == "specsynth.adapters.BaseAdapter"
    assert policy["required_container_class"] == "specsynth.adapters.SSPData"
    assert len(policy["invariants"]) >= 7
    assert len(policy["api_guarantees"]) >= 3

    # Check physical bounds
    bounds = policy["physical_bounds"]
    assert bounds["age_yr"][0] <= 1e4
    assert bounds["age_yr"][1] >= 1e10
    assert bounds["wavelength_angstrom"][0] <= 10.0
    assert bounds["wavelength_angstrom"][1] >= 1e5


@pytest.mark.critical
def test_dynamic_registration_and_conformance_flow():
    """Verify external adapter registration, conformance check, and unregistration."""
    name = "custom_test_engine"
    register_adapter(name, GoodExternalAdapter, aliases=["cte_alias"], overwrite=True)

    try:
        from specsynth.adapters import get_adapter
        inst = get_adapter(name, scale=2.5)
        assert isinstance(inst, GoodExternalAdapter)
        assert inst.scale == 2.5

        # Check conformance on retrieved instance
        result = assert_adapter_conforms(inst, verbose=False)
        assert result.passed is True

        # Check alias retrieval
        inst_alias = get_adapter("cte_alias")
        assert isinstance(inst_alias, GoodExternalAdapter)
    finally:
        unregister_adapter(name)
