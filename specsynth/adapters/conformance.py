"""
Specsynth Adapter Conformance Test Suite & Compatibility Policy
==============================================================
Fulfills Milestone 7 (P6 / Issue #20, Task M1.6):
"Deliver adapter conformance tests and compatibility policy."

This module provides programmatic conformance validation and formal compatibility
policies for external simulation, spectral synthesis, and galaxy-modelling engines
integrating into the Specsynth ecosystem without modifying core framework code.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Type, Union

import numpy as np

from specsynth.adapters.base import BaseAdapter, SSPData


class AdapterConformanceError(AssertionError):
    """Raised when an adapter fails Specsynth scientific or architectural conformance checks."""
    pass


@dataclass
class AdapterConformanceResult:
    """Detailed diagnostic results from running the adapter conformance suite."""
    adapter_name: str
    passed: bool
    checks_run: list[str] = field(default_factory=list)
    checks_passed: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    capabilities: dict[str, Any] = field(default_factory=dict)
    grid_summary: dict[str, Any] = field(default_factory=dict)

    def summary(self) -> str:
        status_str = "CONFORMANT" if self.passed else "NON-CONFORMANT"
        lines = [
            f"Adapter Conformance Report: {self.adapter_name} [{status_str}]",
            f"  Checks: {len(self.checks_passed)}/{len(self.checks_run)} passed",
        ]
        if self.grid_summary:
            g = self.grid_summary
            lines.append(
                f"  Grid: {g.get('n_age', 0)} ages ({g.get('age_min_yr', 0):.2e} - {g.get('age_max_yr', 0):.2e} yr), "
                f"{g.get('n_met', 0)} metallicities ({g.get('z_min', 0):.4f} - {g.get('z_max', 0):.4f}), "
                f"{g.get('n_wave', 0)} wavelengths ({g.get('wave_min_a', 0):.1f} - {g.get('wave_max_a', 0):.1f} Å)"
            )
        if self.errors:
            lines.append("  Errors:")
            for e in self.errors:
                lines.append(f"    - {e}")
        return "\n".join(lines)


class AdapterCompatibilityPolicy:
    """
    Formal Compatibility Policy for Specsynth Adapters.
    Defines versioning contracts, zero-breaking-change guarantees, and physical bounds.
    """
    SPEC_VERSION = "1.0.0"
    MIN_PYTHON_VERSION = (3, 10)

    # Contractual physical boundaries
    MIN_AGE_YR = 1e4        # 10,000 years
    MAX_AGE_YR = 2e10       # 20 Billion years
    MIN_METALLICITY_Z = 1e-6
    MAX_METALLICITY_Z = 0.10
    MIN_WAVELENGTH_A = 10.0   # 10 Angstroms (Extreme UV / soft X-ray boundary)
    MAX_WAVELENGTH_A = 1e6    # 100 microns (Far-Infrared boundary)

    @classmethod
    def get_policy_declaration(cls) -> dict[str, Any]:
        """Return the formal compatibility policy specification as a dictionary."""
        return {
            "specification_version": cls.SPEC_VERSION,
            "min_python_version": f"{cls.MIN_PYTHON_VERSION[0]}.{cls.MIN_PYTHON_VERSION[1]}+",
            "required_base_class": "specsynth.adapters.BaseAdapter",
            "required_container_class": "specsynth.adapters.SSPData",
            "physical_bounds": {
                "age_yr": [cls.MIN_AGE_YR, cls.MAX_AGE_YR],
                "metallicity_z": [cls.MIN_METALLICITY_Z, cls.MAX_METALLICITY_Z],
                "wavelength_angstrom": [cls.MIN_WAVELENGTH_A, cls.MAX_WAVELENGTH_A],
            },
            "invariants": [
                "Strictly ascending 1D ages array",
                "Strictly ascending 1D metallicities array",
                "Strictly ascending 1D rest-frame wavelength array",
                "2D SSP matrix shape (n_age * n_met, n_wave) in age-major layout",
                "Non-negative spectral luminosity L_lambda >= 0",
                "Zero NaN or Infinite values in spectral grid",
                "Deterministic wavelength resampling capability",
            ],
            "api_guarantees": [
                "Zero-core-modification dynamic pluggability via register_adapter()",
                "Semantic versioning: no breaking signature changes within major release 1.x",
                "Full CLI and MCP pass-through for custom registered adapters",
            ],
        }


def assert_adapter_conforms(
    adapter: Union[BaseAdapter, Type[BaseAdapter]],
    sample_kwargs: dict[str, Any] | None = None,
    raise_on_error: bool = True,
    verbose: bool = False,
) -> AdapterConformanceResult:
    """
    Programmatic test assertion to verify an adapter strictly adheres to
    Specsynth architectural and scientific invariants.

    Args:
        adapter: An instance of BaseAdapter or a BaseAdapter subclass.
        sample_kwargs: Optional kwargs to pass when instantiating the class.
        raise_on_error: If True, raises AdapterConformanceError on any failure.
                        If False, returns AdapterConformanceResult with error details.

    Returns:
        AdapterConformanceResult detailing all passed and failed checks.
    """
    checks_run: list[str] = []
    checks_passed: list[str] = []
    errors: list[str] = []
    capabilities: dict[str, Any] = {}
    grid_summary: dict[str, Any] = {}

    def record_check(name: str, passed: bool, error_msg: str | None = None):
        checks_run.append(name)
        if passed:
            checks_passed.append(name)
        else:
            errors.append(f"[{name}] {error_msg}")

    # 1. Class Inheritance Check
    adapter_cls = adapter if inspect.isclass(adapter) else adapter.__class__
    name = getattr(adapter_cls, "__name__", "UnknownAdapter")
    is_subclass = inspect.isclass(adapter_cls) and issubclass(adapter_cls, BaseAdapter)
    record_check(
        "class_inheritance",
        is_subclass,
        f"{name} must inherit from specsynth.adapters.BaseAdapter",
    )

    # 2. Instantiation
    instance: BaseAdapter | None = None
    if inspect.isclass(adapter):
        try:
            kwargs = sample_kwargs or {}
            instance = adapter(**kwargs)
            record_check("instantiation", True)
        except Exception as exc:
            record_check("instantiation", False, f"Failed to instantiate {name}: {exc}")
    else:
        instance = adapter
        record_check("instantiation", True)

    if instance is None or not is_subclass:
        res = AdapterConformanceResult(
            adapter_name=name,
            passed=False,
            checks_run=checks_run,
            checks_passed=checks_passed,
            errors=errors,
        )
        if raise_on_error:
            raise AdapterConformanceError(f"Adapter {name} failed basic instantiation:\n{res.summary()}")
        return res

    # 3. Required Methods Presence
    has_load = callable(getattr(instance, "load", None))
    has_validate = callable(getattr(instance, "validate", None))
    has_caps = callable(getattr(instance, "get_capabilities", None))
    record_check("has_load_method", has_load, "Missing load() method")
    record_check("has_validate_method", has_validate, "Missing validate() method")
    record_check("has_capabilities_method", has_caps, "Missing get_capabilities() method")

    # 4. Capabilities Declaration
    try:
        capabilities = instance.get_capabilities()
        is_dict = isinstance(capabilities, dict)
        record_check("capabilities_format", is_dict, "get_capabilities() must return a dictionary")
    except Exception as exc:
        record_check("capabilities_format", False, f"get_capabilities() raised exception: {exc}")

    # 5. Validation Hook Execution
    try:
        val_res = instance.validate()
        record_check("validation_hook", bool(val_res), "validate() returned False or failed")
    except Exception as exc:
        record_check("validation_hook", False, f"validate() raised exception: {exc}")

    # 6. Load Data & SSPData Invariants
    ssp_data: SSPData | None = None
    try:
        ssp_data = instance.load()
        record_check("load_execution", isinstance(ssp_data, SSPData), "load() must return an instance of SSPData")
    except Exception as exc:
        record_check("load_execution", False, f"load() raised exception during execution: {exc}")

    if ssp_data is not None and isinstance(ssp_data, SSPData):
        # 7. Coordinate Monotonicity & Invariants
        ages = ssp_data.ages
        mets = ssp_data.mets
        wave = ssp_data.wave
        ssp = ssp_data.ssp

        ages_mono = ages.ndim == 1 and len(ages) > 0 and np.all(np.diff(ages) > 0)
        record_check("ages_monotonicity", ages_mono, "ages must be non-empty 1D strictly ascending array")

        mets_mono = mets.ndim == 1 and len(mets) > 0 and (len(mets) == 1 or np.all(np.diff(mets) > 0))
        record_check("metallicities_monotonicity", mets_mono, "mets must be non-empty 1D strictly ascending array")

        wave_mono = wave.ndim == 1 and len(wave) > 0 and np.all(np.diff(wave) > 0)
        record_check("wavelength_monotonicity", wave_mono, "wave must be non-empty 1D strictly ascending array")

        # 8. Matrix Dimensions
        expected_shape = (len(ages) * len(mets), len(wave))
        shape_match = ssp.shape == expected_shape
        record_check(
            "matrix_shape",
            shape_match,
            f"ssp shape {ssp.shape} does not match expected {expected_shape} (n_age * n_met, n_wave)",
        )

        # 9. Finiteness & Non-Negativity
        is_finite = bool(np.all(np.isfinite(ssp)))
        record_check("matrix_finite", is_finite, "ssp matrix contains non-finite values (NaN, Inf)")

        # Allow float32 epsilon precision for negligible zero-flux underflow
        non_negative = bool(np.all(ssp >= -1e-6))
        record_check("matrix_non_negative", non_negative, "ssp matrix contains negative luminosities")

        non_trivial = bool(np.sum(ssp) > 0)
        record_check("matrix_non_trivial", non_trivial, "ssp matrix sum is zero (all-zero flux)")

        # 10. Resampling Capability
        try:
            target_wave = np.linspace(wave[0] + 10.0, wave[-1] - 10.0, 100)
            resampled = ssp_data.resample_wavelength(target_wave)
            resample_valid = (
                isinstance(resampled, SSPData)
                and resampled.ssp.shape == (expected_shape[0], 100)
                and bool(np.all(np.isfinite(resampled.ssp)))
            )
            record_check("resample_support", resample_valid, "resample_wavelength failed or produced invalid shape")
        except Exception as exc:
            record_check("resample_support", False, f"resample_wavelength raised exception: {exc}")

        # Summary metadata
        grid_summary = {
            "n_age": len(ages),
            "age_min_yr": float(ages[0]),
            "age_max_yr": float(ages[-1]),
            "n_met": len(mets),
            "z_min": float(mets[0]),
            "z_max": float(mets[-1]),
            "n_wave": len(wave),
            "wave_min_a": float(wave[0]),
            "wave_max_a": float(wave[-1]),
            "ssp_shape": list(ssp.shape),
            "ssp_min": float(np.min(ssp)),
            "ssp_max": float(np.max(ssp)),
        }

    all_passed = len(errors) == 0
    res = AdapterConformanceResult(
        adapter_name=name,
        passed=all_passed,
        checks_run=checks_run,
        checks_passed=checks_passed,
        errors=errors,
        capabilities=capabilities,
        grid_summary=grid_summary,
    )

    if verbose:
        print(res.summary())

    if not all_passed and raise_on_error:
        raise AdapterConformanceError(f"Adapter {name} failed conformance validation:\n{res.summary()}")

    return res
