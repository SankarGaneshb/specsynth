"""
specsynth: Distributed, out-of-core stellar population synthesis (SPS).
"""

__version__ = "0.2.0"

from specsynth.adapters.toy import build_toy_ssp, planck
from specsynth.core import (
    N_PARAM,
    YOUNG_AGE_YR,
    _gen_params,
    attenuation_curve,
    band_matrix,
    read_small,
    sfh_from_params,
    small,
    synth_block,
    url,
    write_many,
)

__all__ = [
    "YOUNG_AGE_YR",
    "N_PARAM",
    "attenuation_curve",
    "band_matrix",
    "build_toy_ssp",
    "planck",
    "_gen_params",
    "sfh_from_params",
    "synth_block",
    "url",
    "read_small",
    "write_many",
    "small",
]
