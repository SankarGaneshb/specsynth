"""
specsynth: Distributed, out-of-core stellar population synthesis (SPS).
"""

__version__ = "0.3.0"

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
from specsynth.benchmark import get_system_hardware_info, run_benchmark_suite
from specsynth.catalog import import_catalog, load_raw_table, resolve_catalog_columns
from specsynth.cosmology import DEFAULT_COSMOLOGY, FlatLambdaCDM, redshift_flux
from specsynth.filters import (
    FilterCurve,
    build_filter_projection_matrix,
    flux_to_ab_mag,
    get_filter,
)
from specsynth.gpu import get_device_info, is_gpu_available, synth_block_gpu
from specsynth.igm import madau_transmission
from specsynth.sentry import (
    AnomalyRecord,
    SentryReport,
    check_energy_conservation,
    check_finite_positive,
    check_magnitude_bounds,
    check_population_bimodality,
    measure_d4000_break,
    measure_uv_slope,
    run_sentry_audit,
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
    "FlatLambdaCDM",
    "DEFAULT_COSMOLOGY",
    "redshift_flux",
    "FilterCurve",
    "get_filter",
    "build_filter_projection_matrix",
    "flux_to_ab_mag",
    "get_device_info",
    "is_gpu_available",
    "synth_block_gpu",
    "madau_transmission",
    "import_catalog",
    "load_raw_table",
    "resolve_catalog_columns",
    "run_benchmark_suite",
    "get_system_hardware_info",
    "AnomalyRecord",
    "SentryReport",
    "check_finite_positive",
    "check_energy_conservation",
    "measure_d4000_break",
    "measure_uv_slope",
    "check_magnitude_bounds",
    "check_population_bimodality",
    "run_sentry_audit",
]
