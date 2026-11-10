"""
specsynth: Distributed, out-of-core stellar population synthesis (SPS).
"""

__version__ = "0.2.0"

from specsynth.core import (
    YOUNG_AGE_YR,
    attenuation_curve,
    band_matrix,
    planck,
    sfh_from_params,
    synth_block,
    url,
)

__all__ = [
    "YOUNG_AGE_YR",
    "attenuation_curve",
    "band_matrix",
    "planck",
    "sfh_from_params",
    "synth_block",
    "url",
]
