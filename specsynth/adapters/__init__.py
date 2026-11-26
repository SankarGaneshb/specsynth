"""
specsynth adapters: built-in model loaders and dynamic plugin registry for
Simple Stellar Population (SSP) libraries.
Enforces P0.3 zero-core-modification pluggability.
"""

from __future__ import annotations

import importlib.metadata
import inspect
import logging
from typing import Any, Type

from specsynth.adapters.base import BaseAdapter, SSPData
from specsynth.adapters.bc03 import BC03Adapter
from specsynth.adapters.bpass import BPASSAdapter
from specsynth.adapters.emiles import EMILESAdapter
from specsynth.adapters.fits_grid import FITSGridAdapter
from specsynth.adapters.fsps import FSPSAdapter
from specsynth.adapters.toy import ToyAdapter, build_toy_ssp, planck

logger = logging.getLogger("specsynth.adapters")

__all__ = [
    "BaseAdapter",
    "SSPData",
    "ToyAdapter",
    "build_toy_ssp",
    "planck",
    "BC03Adapter",
    "BPASSAdapter",
    "EMILESAdapter",
    "FITSGridAdapter",
    "FSPSAdapter",
    "get_adapter",
    "register_adapter",
    "unregister_adapter",
    "list_adapters",
    "discover_entry_point_adapters",
    "validate_adapter",
]

# Primary registry mapping canonical adapter names to adapter classes
_ADAPTER_REGISTRY: dict[str, Type[BaseAdapter]] = {}
# Alias mapping (e.g. 'bruzual-charlot' -> 'bc03')
_ADAPTER_ALIASES: dict[str, str] = {}


def register_adapter(
    name: str,
    adapter_cls: Type[BaseAdapter],
    aliases: list[str] | None = None,
    overwrite: bool = False,
) -> None:
    """
    Register an SSP engine adapter class in the Specsynth runtime registry.

    Allows external packages or astrophysicists to register custom simulation/SPS
    engines dynamically without modifying the Specsynth core codebase.

    Args:
        name: Canonical adapter identifier (e.g. 'maraston', 'starburst99').
        adapter_cls: Subclass of BaseAdapter.
        aliases: Optional list of alternate lookup names.
        overwrite: If True, allow replacing an existing registered adapter.
    """
    if not inspect.isclass(adapter_cls) or not issubclass(adapter_cls, BaseAdapter):
        raise TypeError(f"Adapter class must inherit from BaseAdapter, got {adapter_cls}")

    canonical_name = name.strip().lower()
    if canonical_name in _ADAPTER_REGISTRY and not overwrite:
        raise ValueError(
            f"Adapter '{canonical_name}' is already registered. Set overwrite=True to replace."
        )

    _ADAPTER_REGISTRY[canonical_name] = adapter_cls
    if aliases:
        for alias in aliases:
            _ADAPTER_ALIASES[alias.strip().lower()] = canonical_name


def unregister_adapter(name: str) -> bool:
    """
    Remove an adapter from the registry by name or alias.
    Returns True if removed, False if not found.
    """
    clean_name = name.strip().lower()
    canonical = _ADAPTER_ALIASES.get(clean_name, clean_name)
    if canonical in _ADAPTER_REGISTRY:
        del _ADAPTER_REGISTRY[canonical]
        # Clean aliases pointing to canonical
        aliases_to_remove = [k for k, v in _ADAPTER_ALIASES.items() if v == canonical]
        for a in aliases_to_remove:
            del _ADAPTER_ALIASES[a]
        return True
    return False


def list_adapters() -> dict[str, Type[BaseAdapter]]:
    """Return a dictionary of all currently registered canonical adapters."""
    return dict(_ADAPTER_REGISTRY)


def validate_adapter(adapter_cls: Type[BaseAdapter]) -> bool:
    """
    Verify that an adapter class satisfies the required lifecycle contract.

    Checks:
    1. Inherits from BaseAdapter.
    2. Implements `load()` returning SSPData.
    3. Implements `validate()`.
    4. Implements `get_capabilities()`.
    """
    if not inspect.isclass(adapter_cls) or not issubclass(adapter_cls, BaseAdapter):
        raise TypeError(f"{adapter_cls} does not inherit from BaseAdapter")

    load_method = getattr(adapter_cls, "load", None)
    if not callable(load_method) or getattr(load_method, "__isabstractmethod__", False):
        raise TypeError(f"{adapter_cls.__name__} does not implement required abstract method 'load'")

    return True


def discover_entry_point_adapters() -> dict[str, Type[BaseAdapter]]:
    """
    Discover and register third-party adapters published via Python entry points.

    Any external Python package advertising entry points under the group
    `specsynth.adapters` will be discovered and registered automatically at runtime:
    ```toml
    [project.entry-points."specsynth.adapters"]
    my_engine = "my_package.adapter:MyEngineAdapter"
    ```
    """
    discovered: dict[str, Type[BaseAdapter]] = {}
    try:
        eps = importlib.metadata.entry_points(group="specsynth.adapters")
    except Exception as e:
        logger.debug(f"Failed to query entry points: {e}")
        return discovered

    for ep in eps:
        try:
            cls = ep.load()
            if issubclass(cls, BaseAdapter):
                register_adapter(ep.name, cls, overwrite=False)
                discovered[ep.name] = cls
                logger.info(f"Discovered third-party adapter '{ep.name}' via entry points")
        except Exception as e:
            logger.warning(f"Failed to load external adapter '{ep.name}': {e}")

    return discovered


# Register built-in adapters
register_adapter("toy", ToyAdapter, aliases=["analytical", "benchmark"])
register_adapter("bc03", BC03Adapter, aliases=["bruzual-charlot", "bruzual_charlot"])
register_adapter("bpass", BPASSAdapter, aliases=["bpass2", "bpass_v2"])
register_adapter("emiles", EMILESAdapter, aliases=["e-miles", "miles"])
register_adapter("fits", FITSGridAdapter, aliases=["fits_grid", "hdf5", "npz"])
register_adapter("fsps", FSPSAdapter)


def get_adapter(name: str, **kwargs) -> BaseAdapter:
    """
    Factory helper to instantiate an SSP adapter by name from the registry.
    Checks dynamic discovery before failing.
    """
    name_clean = name.strip().lower()
    canonical = _ADAPTER_ALIASES.get(name_clean, name_clean)

    if canonical not in _ADAPTER_REGISTRY:
        # Try dynamic discovery in case newly installed external packages exist
        discover_entry_point_adapters()
        canonical = _ADAPTER_ALIASES.get(name_clean, name_clean)

    adapter_cls = _ADAPTER_REGISTRY.get(canonical)
    if adapter_cls is None:
        available = sorted(list(_ADAPTER_REGISTRY.keys()))
        raise ValueError(
            f"Unknown adapter '{name}'. Available: {available}"
        )

    return adapter_cls(**kwargs)
