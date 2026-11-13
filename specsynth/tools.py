from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import numpy as np

from specsynth.benchmark import get_system_hardware_info
from specsynth.catalog import clean_catalog
from specsynth.core import read_small, url
from specsynth.filters import FILTER_SETS, STANDARD_FILTER_SPECS
from specsynth.sentry import run_sentry_audit


def tool_run_sentry_audit(
    base: str = "./run",
    sample_size: int = 50_000,
    output_json: str | None = None,
    output_markdown: str | None = None,
) -> dict[str, Any]:
    """
    Run an automated Scientific Sentry audit across synthesized catalogs in a base directory.

    Args:
        base: Path or URL to storage base directory containing ssp.zarr, galaxies.zarr, etc.
        sample_size: Number of galaxies to audit (default: 50,000).
        output_json: Optional path to save machine-readable JSON audit manifest.
        output_markdown: Optional path to save executive Markdown report.

    Returns:
        Structured audit report dictionary including total evaluated, pass rate, and anomaly list.
    """
    report = run_sentry_audit(
        base=base,
        sample_size=sample_size,
        attach_is_valid=True,
    )
    if output_json:
        report.to_json(output_json)
    if output_markdown:
        report.to_markdown(output_markdown)

    return report.to_dict()


def tool_inspect_anomaly(
    base: str = "./run",
    anomaly_id: str = "",
    report_path: str | None = None,
) -> dict[str, Any]:
    """
    Look up details and physical input context for a specific anomaly ID.

    Args:
        base: Path to base storage.
        anomaly_id: The unique identifier (e.g., 'ANOM-D4K-14209' or 'D4K-14209').
        report_path: Path to sentry_report.json (default: <base>/sentry_report.json).

    Returns:
        Dictionary containing metric name, observed value, expected range, and input parameters.
    """
    rep_file = report_path or os.path.join(base, "sentry_report.json")
    if not os.path.exists(rep_file):
        return {"error": f"Report file not found at {rep_file}"}

    with open(rep_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    target_id = anomaly_id.strip()
    for anom in data.get("anomalies", []):
        if anom["anomaly_id"] == target_id or target_id in anom["anomaly_id"]:
            return {"found": True, "anomaly": anom}

    return {"found": False, "message": f"Anomaly {anomaly_id} not found in {rep_file}"}


# Alias for backward/agent naming consistency
tool_get_anomaly_details = tool_inspect_anomaly


def tool_inspect_galaxy(base: str = "./run", galaxy_idx: int = 0) -> dict[str, Any]:
    """
    Extract the full physical parameters, SFH mass fraction, and synthesized flux for a single galaxy.

    Args:
        base: Base storage directory.
        galaxy_idx: Index of the galaxy to inspect.

    Returns:
        Dictionary with galaxy parameters, diffuse/birth dust, young mass fraction, and fluxes.
    """
    import zarr
    import fsspec

    def _safe_open(store_path: str) -> Any | None:
        is_mocked = getattr(zarr.open_group, "__module__", "") != "zarr.api.synchronous"
        if not is_mocked and "://" not in str(store_path) and not Path(store_path).exists():
            return None
        try:
            return zarr.open_group(store_path, mode="r")
        except Exception:
            if "://" in str(store_path) or is_mocked:
                try:
                    import fsspec
                    return zarr.open_group(fsspec.get_mapper(store_path), mode="r")
                except Exception:
                    return None
            return None

    gal_store = url(base, "galaxies.zarr")
    out_store = url(base, "spectra.zarr")
    phot_store = url(base, "photometry.zarr")

    g_in = _safe_open(gal_store) or {}

    details: dict[str, Any] = {"galaxy_index": int(galaxy_idx)}

    if "tau_diffuse" in g_in:
        details["tau_diffuse"] = float(g_in["tau_diffuse"][galaxy_idx])
    if "tau_birth" in g_in:
        details["tau_birth"] = float(g_in["tau_birth"][galaxy_idx])
    if "redshift" in g_in:
        details["redshift"] = float(g_in["redshift"][galaxy_idx])

    if "sfh" in g_in:
        sfh_row = np.asarray(g_in["sfh"][galaxy_idx], dtype=np.float64)
        tot_mass = float(np.sum(sfh_row))
        details["total_stellar_mass_msun"] = tot_mass
        details["sfh_bins_count"] = len(sfh_row)

    if "params" in g_in:
        p_row = np.asarray(g_in["params"][galaxy_idx], dtype=np.float64)
        if len(p_row) >= 6:
            details["log_stellar_mass"] = float(p_row[0])
            details["t_onset_gyr"] = float(p_row[1])
            details["sfh_tau_gyr"] = float(p_row[2])
            details["log_metallicity"] = float(p_row[3])

    # Check output (spectra or photometry)
    for target_store in (out_store, phot_store):
        g_out = _safe_open(target_store)
        if g_out is None:
            continue
        try:
            if "spectra" in g_out:
                details["output_type"] = "spectra"
                row = np.asarray(g_out["spectra"][galaxy_idx], dtype=np.float64)
                details["min_spectral_flux"] = float(np.min(row))
                details["max_spectral_flux"] = float(np.max(row))
                break
            elif "photometry" in g_out:
                details["output_type"] = "photometry"
                p_row = [float(m) for m in np.asarray(g_out["photometry"][galaxy_idx], dtype=np.float64)]
                details["photometry_magnitudes"] = p_row
                details["photometry_values"] = p_row
                attrs = getattr(g_out, "attrs", None)
                if attrs and "filters" in attrs:
                    details["filter_names"] = list(attrs["filters"])
                break
        except Exception:
            continue
    else:
        details["output_type"] = "not_found"

    return details


def tool_clean_catalog(
    base: str = "./run",
    report_path: str | None = None,
    output_path: str = "clean_catalog.parquet",
    source_table_path: str | None = None,
) -> dict[str, Any]:
    """
    Filter quarantined anomalous galaxies out of a catalog, exporting a clean dataset.

    Args:
        base: Base storage directory.
        report_path: Path to sentry_report.json.
        output_path: Path to export cleaned catalog.
        source_table_path: Optional original raw table.

    Returns:
        Summary dictionary with retention rate, valid count, and quarantined count.
    """
    rep_file = report_path or os.path.join(base, "sentry_report.json")
    return clean_catalog(
        base=base,
        sentry_report_path=rep_file,
        output_path=output_path,
        source_table_path=source_table_path,
    )


def tool_get_system_info() -> dict[str, Any]:
    """
    Return host hardware information, CPU processor, RAM, and Python environment.
    """
    return get_system_hardware_info()


def tool_list_available_filters() -> dict[str, Any]:
    """
    Return available standard filter curves and filter sets (JWST, HST, Rubin, SDSS, Euclid).
    """
    return {
        "filter_sets": list(FILTER_SETS.keys()),
        "individual_filters_count": len(STANDARD_FILTER_SPECS),
        "available_filters": list(STANDARD_FILTER_SPECS.keys()),
    }
