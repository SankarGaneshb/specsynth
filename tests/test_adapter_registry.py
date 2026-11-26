"""
Unit tests for the dynamic adapter registry and plugin architecture.
Enforces P0.3 Zero-Core-Modification Pluggability (Issue #14, Pillar 1).
"""

import numpy as np
import pytest

from specsynth.adapters import (
    BaseAdapter,
    SSPData,
    get_adapter,
    list_adapters,
    register_adapter,
    unregister_adapter,
    validate_adapter,
)


class MockExternalEngineAdapter(BaseAdapter):
    """Simulates a third-party SPS engine adapter written by an external astrophysicist."""

    def __init__(self, custom_param: str = "default"):
        self.custom_param = custom_param

    def load(self) -> SSPData:
        ages = np.array([1e7, 1e8, 1e9], dtype=np.float64)
        mets = np.array([0.004, 0.02], dtype=np.float64)
        wave = np.linspace(2000, 8000, 30, dtype=np.float64)
        ssp = np.ones((6, 30), dtype=np.float32)
        return SSPData(
            ages=ages,
            mets=mets,
            wave=wave,
            ssp=ssp,
            metadata={"engine": "mock_external", "custom_param": self.custom_param},
        )

    def validate(self) -> bool:
        return True

    def get_capabilities(self) -> dict:
        return {
            "name": "MockExternalEngine",
            "version": "2.4.1",
            "dynamic_metallicity": True,
            "resampling_supported": True,
        }


def test_builtin_adapters_registered():
    adapters = list_adapters()
    for expected in ("toy", "bc03", "bpass", "emiles", "fits", "fsps"):
        assert expected in adapters


def test_builtin_adapter_instantiation_via_alias():
    toy1 = get_adapter("toy")
    toy2 = get_adapter("analytical")
    toy3 = get_adapter("benchmark")
    assert toy1.__class__.__name__ == "ToyAdapter"
    assert toy2.__class__.__name__ == "ToyAdapter"
    assert toy3.__class__.__name__ == "ToyAdapter"


def test_dynamic_adapter_registration():
    # Verify adapter not yet registered
    with pytest.raises(ValueError, match="Unknown adapter 'mock_engine'"):
        get_adapter("mock_engine")

    # Register external engine
    register_adapter("mock_engine", MockExternalEngineAdapter, aliases=["mock_alias"])
    try:
        assert "mock_engine" in list_adapters()
        assert validate_adapter(MockExternalEngineAdapter) is True

        # Instantiate via canonical name
        adapter = get_adapter("mock_engine", custom_param="active_run")
        assert isinstance(adapter, MockExternalEngineAdapter)
        assert adapter.custom_param == "active_run"

        # Instantiate via alias
        alias_adapter = get_adapter("mock_alias")
        assert isinstance(alias_adapter, MockExternalEngineAdapter)

        # Load data and verify contracts
        ssp_data = adapter.load()
        assert ssp_data.metadata["engine"] == "mock_external"
        assert ssp_data.ssp.shape == (6, 30)

    finally:
        # Clean up
        unregister_adapter("mock_engine")
        assert "mock_engine" not in list_adapters()


def test_register_duplicate_without_overwrite_raises():
    with pytest.raises(ValueError, match="already registered"):
        register_adapter("toy", MockExternalEngineAdapter, overwrite=False)


def test_validate_adapter_rejects_invalid_classes():
    class IncompleteAdapter:
        pass

    with pytest.raises(TypeError, match="does not inherit from BaseAdapter"):
        validate_adapter(IncompleteAdapter)

    class MissingLoadAdapter(BaseAdapter):
        pass

    with pytest.raises(TypeError, match="does not implement required abstract method 'load'"):
        validate_adapter(MissingLoadAdapter)
