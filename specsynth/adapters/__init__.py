"""
specsynth adapters: built-in model loaders for Simple Stellar Population (SSP) libraries.
"""

from specsynth.adapters.base import BaseAdapter, SSPData
from specsynth.adapters.bc03 import BC03Adapter
from specsynth.adapters.bpass import BPASSAdapter
from specsynth.adapters.emiles import EMILESAdapter
from specsynth.adapters.fits_grid import FITSGridAdapter
from specsynth.adapters.fsps import FSPSAdapter
from specsynth.adapters.toy import ToyAdapter, build_toy_ssp, planck

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
]


def get_adapter(name: str, **kwargs) -> BaseAdapter:
    """Factory helper to instantiate an SSP adapter by name."""
    name_clean = name.strip().lower()
    if name_clean in ("toy", "analytical", "benchmark"):
        return ToyAdapter(**kwargs)
    elif name_clean in ("bc03", "bruzual-charlot", "bruzual_charlot"):
        return BC03Adapter(**kwargs)
    elif name_clean in ("bpass", "bpass2", "bpass_v2"):
        return BPASSAdapter(**kwargs)
    elif name_clean in ("emiles", "e-miles", "miles"):
        return EMILESAdapter(**kwargs)
    elif name_clean in ("fits", "fits_grid", "hdf5", "npz"):
        return FITSGridAdapter(**kwargs)
    elif name_clean == "fsps":
        return FSPSAdapter(**kwargs)
    else:
        raise ValueError(
            f"Unknown adapter '{name}'. Available: 'toy', 'bc03', 'bpass', 'emiles', 'fits', 'fsps'"
        )
