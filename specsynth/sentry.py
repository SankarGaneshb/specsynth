from __future__ import annotations

import json
import os
import sys
import time
import traceback
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from specsynth.core import N_PARAM, YOUNG_AGE_YR, attenuation_curve, url
from specsynth.filters import build_filter_projection_matrix, flux_to_ab_mag
from specsynth.igm import madau_transmission


# ---------------------------------------------------------------------------
# Data Models for Anomalies and Audit Reports
# ---------------------------------------------------------------------------

@dataclass
class AnomalyRecord:
    anomaly_id: str
    tier: int
    category: str        # INPUT_SCHEMA_FAULT, NUMERICAL_FAULT, PHYSICAL_ANOMALY, UNKNOWN_EXCEPTION
    severity: str        # WARNING, ERROR, CRITICAL
    galaxy_index: int    # Explicit int (np.int64 safe)
    metric_name: str
    observed_value: float | None = None
    expected_range: list[float] | None = None
    input_parameters: dict[str, float] | None = None
    root_cause: str = ""
    remediation: str = ""


@dataclass
class SentryReport:
    timestamp: str
    provenance: str
    total_galaxies_evaluated: int
    passed_count: int
    flagged_count: int
    pass_rate_pct: float
    status: str          # PASSED, WARNING, CRITICAL_FAILURE
    tier_summary: dict[str, int] = field(default_factory=dict)
    category_summary: dict[str, int] = field(default_factory=dict)
    quarantined_files: list[str] = field(default_factory=list)
    anomalies: list[AnomalyRecord] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d

    def to_json(self, path: str | Path | None = None, indent: int = 2) -> str:
        s = json.dumps(self.to_dict(), indent=indent)
        if path:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(s)
        return s

    def to_markdown(self, path: str | Path | None = None) -> str:
        lines = [
            "# Scientific Sentry Quality Assurance Audit Report",
            f"**Audit Status**: `{self.status}` | **Timestamp**: {self.timestamp}",
            "",
            "## Summary Metrics",
            f"- **Total Galaxies Evaluated**: {self.total_galaxies_evaluated:,}",
            f"- **Valid Physical Objects**: {self.passed_count:,} ({self.pass_rate_pct:.3f}%)",
            f"- **Quarantined / Flagged**: {self.flagged_count:,} ({100.0 - self.pass_rate_pct:.3f}%)",
            "",
            "### Breakdown by Severity & Category",
            "| Category | Count | Status |",
            "| :--- | :---: | :---: |",
        ]
        for cat, cnt in sorted(self.category_summary.items()):
            stat = "CRITICAL" if cat in ("NUMERICAL_FAULT", "INPUT_SCHEMA_FAULT") else "WARN/ERROR"
            lines.append(f"| `{cat}` | {cnt} | {stat} |")

        if self.anomalies:
            lines.extend([
                "",
                "## Isolated Anomalies (Sample)",
                "| ID | Galaxy Index | Metric | Observed | Expected | Root Cause |",
                "| :--- | :---: | :--- | :---: | :---: | :--- |",
            ])
            for a in self.anomalies[:25]:
                obs_str = f"{a.observed_value:.3e}" if a.observed_value is not None else "N/A"
                exp_str = f"[{a.expected_range[0]}, {a.expected_range[1]}]" if a.expected_range else "N/A"
                lines.append(
                    f"| `{a.anomaly_id}` | #{a.galaxy_index} | {a.metric_name} | {obs_str} | {exp_str} | {a.root_cause} |"
                )
            if len(self.anomalies) > 25:
                lines.append(f"*(...and {len(self.anomalies) - 25} more anomalies logged in JSON report)*")

        if self.quarantined_files:
            lines.extend([
                "",
                "## Quarantined Input Dumps",
                "The following chunks or galaxies encountered fatal/unknown exceptions and were dumped to disk for inspection:",
            ] + [f"- `{f}`" for f in self.quarantined_files])

        md_text = "\n".join(lines) + "\n"
        if path:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(md_text)
        return md_text


# ---------------------------------------------------------------------------
# Vectorized Diagnostic Algorithms (Tier 1 & Tier 2)
# ---------------------------------------------------------------------------

def check_finite_positive(flux: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Tier 1 check: Vectorized check for NaN, +Inf, -Inf, and non-positive fluxes.
    Returns:
        (valid_mask, invalid_indices) where valid_mask is boolean array of shape (N,)
        and invalid_indices are np.int64 array of indices failing the check.
    """
    flux = np.asarray(flux)
    if flux.ndim == 1:
        flux = flux.reshape(1, -1)

    # IEEE 754 Safe: check isfinite first, then strict positivity
    finite_mask = np.all(np.isfinite(flux), axis=-1)
    positive_mask = np.all(flux > 0.0, axis=-1)
    valid_mask = finite_mask & positive_mask

    invalid_indices = np.where(~valid_mask)[0].astype(np.int64)
    return valid_mask, invalid_indices


def check_energy_conservation(
    f_attenuated: np.ndarray,
    f_intrinsic: np.ndarray,
    atol: float = 1e-5,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Tier 1 check: Total integrated energy must not increase under dust attenuation.
    Integral(F_attenuated) <= Integral(F_intrinsic) * (1 + atol).
    Returns:
        (valid_mask, invalid_indices, energy_ratios)
    """
    f_att = np.asarray(f_attenuated, dtype=np.float64)
    f_int = np.asarray(f_intrinsic, dtype=np.float64)
    if f_att.ndim == 1:
        f_att = f_att.reshape(1, -1)
        f_int = f_int.reshape(1, -1)

    sum_att = np.sum(f_att, axis=-1)
    sum_int = np.sum(f_int, axis=-1)

    # Floor denominator to avoid divide-by-zero
    safe_denom = np.maximum(sum_int, 1e-35)
    ratios = sum_att / safe_denom

    valid_mask = np.isfinite(ratios) & (ratios <= (1.0 + atol))
    invalid_indices = np.where(~valid_mask)[0].astype(np.int64)
    return valid_mask, invalid_indices, ratios.astype(np.float32)


def measure_d4000_break(wave_rest: np.ndarray, flux_rest: np.ndarray) -> np.ndarray:
    """
    Tier 2 check: Balogh et al. (1999) narrow Dn(4000) break definition:
    Ratio of flux in red band [4000, 4100] A to blue band [3850, 3950] A.
    Returns:
        d4000 array of shape (N,). Physical range is [0.95, 2.50].
        Returns NaN for galaxies if wavelength does not cover [3850, 4100] A.
    """
    wave = np.asarray(wave_rest, dtype=np.float64)
    flux = np.asarray(flux_rest, dtype=np.float64)
    if flux.ndim == 1:
        flux = flux.reshape(1, -1)

    blue_mask = (wave >= 3850.0) & (wave <= 3950.0)
    red_mask = (wave >= 4000.0) & (wave <= 4100.0)

    if not np.any(blue_mask) or not np.any(red_mask):
        return np.full(flux.shape[0], np.nan, dtype=np.float32)

    # In F_nu: F_nu = F_lambda * lambda^2 / c
    f_nu_blue = flux[:, blue_mask] * (wave[blue_mask] ** 2)
    f_nu_red = flux[:, red_mask] * (wave[red_mask] ** 2)

    mean_blue = np.mean(f_nu_blue, axis=-1)
    mean_red = np.mean(f_nu_red, axis=-1)

    # Safe denominator floor prevents divide-by-zero
    safe_blue = np.maximum(mean_blue, 1e-35)
    d4000 = mean_red / safe_blue
    return d4000.astype(np.float32)


def measure_uv_slope(wave_rest: np.ndarray, flux_rest: np.ndarray) -> np.ndarray:
    """
    Tier 2 check: UV continuum slope beta (F_lambda ~ lambda^beta) over [1500, 2500] A.
    Evaluated via vectorized linear least-squares in log-log space.
    Returns:
        beta array of shape (N,). Physical range is [-2.80, +1.50].
    """
    wave = np.asarray(wave_rest, dtype=np.float64)
    flux = np.asarray(flux_rest, dtype=np.float64)
    if flux.ndim == 1:
        flux = flux.reshape(1, -1)

    uv_mask = (wave >= 1500.0) & (wave <= 2500.0)
    if np.sum(uv_mask) < 3:
        return np.full(flux.shape[0], np.nan, dtype=np.float32)

    w_uv = wave[uv_mask]
    f_uv = np.maximum(flux[:, uv_mask], 1e-35)

    log_w = np.log(w_uv)
    log_f = np.log(f_uv)

    # Linear regression slope: beta = cov(x, y) / var(x)
    x_mean = np.mean(log_w)
    x_var = np.sum((log_w - x_mean) ** 2)
    if x_var <= 1e-12:
        return np.full(flux.shape[0], np.nan, dtype=np.float32)

    beta = np.sum((log_w - x_mean) * (log_f - np.mean(log_f, axis=-1, keepdims=True)), axis=-1) / x_var
    return beta.astype(np.float32)


def check_magnitude_bounds(
    mags: np.ndarray,
    min_mag: float = 10.0,
    max_mag: float = 35.0,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Tier 2 check: Check that apparent AB magnitudes are within survey-detectable range.
    Returns:
        (valid_mask, invalid_indices)
    """
    mags = np.asarray(mags, dtype=np.float64)
    if mags.ndim == 1:
        mags = mags.reshape(1, -1)

    finite = np.all(np.isfinite(mags), axis=-1)
    in_range = np.all((mags >= min_mag) & (mags <= max_mag), axis=-1)
    valid_mask = finite & in_range
    invalid_indices = np.where(~valid_mask)[0].astype(np.int64)
    return valid_mask, invalid_indices


def check_population_bimodality(colors: np.ndarray) -> dict[str, Any]:
    """
    Tier 3 check: Statistical dispersion check across population colors.
    Flags population-level collapse (e.g. all galaxies collapsing to a single degenerate color).
    """
    c = np.asarray(colors, dtype=np.float64)
    c_clean = c[np.isfinite(c)]
    if len(c_clean) < 10:
        return {"status": "INSUFFICIENT_DATA", "variance": 0.0}

    var = float(np.var(c_clean))
    std = float(np.std(c_clean))
    median = float(np.median(c_clean))
    p16, p84 = float(np.percentile(c_clean, 16)), float(np.percentile(c_clean, 84))

    is_degenerate = var < 1e-5
    return {
        "status": "COLLAPSED" if is_degenerate else "OK",
        "sample_size": len(c_clean),
        "mean": float(np.mean(c_clean)),
        "std": std,
        "variance": var,
        "median": median,
        "p16": p16,
        "p84": p84,
        "bimodal_dispersion_ok": not is_degenerate,
    }


# ---------------------------------------------------------------------------
# Main Sentry Audit Runner
# ---------------------------------------------------------------------------

def run_sentry_audit(
    base: str,
    gal_name: str = "galaxies.zarr",
    ssp_name: str = "ssp.zarr",
    out_name: str = "spectra.zarr",
    sample_size: int = 50_000,
    min_mag: float = 10.0,
    max_mag: float = 35.0,
    max_anomaly_rate: float = 0.001,
    quarantine_dir: str | None = None,
    attach_is_valid: bool = False,
    seed: int = 42,
) -> SentryReport:
    """
    Executes an out-of-core Scientific Sentry audit across synthesized catalogs.
    Safely captures and isolates exceptions, writing anomalies and quarantined files.
    """
    import zarr
    import fsspec

    gal_store = url(base, gal_name)
    ssp_store = url(base, ssp_name)
    out_store = url(base, out_name)

    if quarantine_dir is None:
        quarantine_dir = os.path.join(base, "sentry_quarantine")

    anomalies: list[AnomalyRecord] = []
    quarantined_files: list[str] = []
    category_counts = {
        "INPUT_SCHEMA_FAULT": 0,
        "NUMERICAL_FAULT": 0,
        "PHYSICAL_ANOMALY": 0,
        "POPULATION_DRIFT": 0,
        "UNKNOWN_EXCEPTION": 0,
    }

    # 1. Open groups safely
    try:
        g_in = zarr.open_group(gal_store, mode="r")
    except Exception:
        g_in = zarr.open_group(fsspec.get_mapper(gal_store), mode="r")

    try:
        g_out = zarr.open_group(out_store, mode="r")
    except Exception:
        try:
            g_out = zarr.open_group(fsspec.get_mapper(out_store), mode="r")
        except Exception:
            if out_name == "spectra.zarr":
                alt_store = url(base, "photometry.zarr")
                try:
                    g_out = zarr.open_group(alt_store, mode="r")
                except Exception:
                    g_out = zarr.open_group(fsspec.get_mapper(alt_store), mode="r")
            else:
                raise

    try:
        g_ssp = zarr.open_group(ssp_store, mode="r")
    except Exception:
        g_ssp = zarr.open_group(fsspec.get_mapper(ssp_store), mode="r")

    wave = np.asarray(g_ssp["wave"][:])
    ages = np.asarray(g_ssp["ages"][:])
    mets = np.asarray(g_ssp["mets"][:])
    ssp = np.asarray(g_ssp["ssp"][:], dtype=np.float64)
    ny = int((ages < YOUNG_AGE_YR).sum()) * len(mets)

    # Total galaxies
    if "sfh" in g_in:
        total_galaxies = int(g_in["sfh"].shape[0])
    elif "params" in g_in:
        total_galaxies = int(g_in["params"].shape[0])
    else:
        total_galaxies = int(g_out["spectra"].shape[0] if "spectra" in g_out else g_out["photometry"].shape[0])

    n_sample = min(sample_size, total_galaxies)
    rng = np.random.default_rng(seed)
    sampled_indices = np.sort(rng.choice(total_galaxies, size=n_sample, replace=False)).astype(np.int64)

    # 2. Iterate in memory-bounded chunks with safe isolation
    chunk_size = 5_000
    is_spectra = "spectra" in g_out
    has_igm = getattr(g_out, "attrs", {}).get("igm", False)
    redshift = float(getattr(g_out, "attrs", {}).get("redshift", 0.0))

    kd = attenuation_curve(wave, -0.7).astype(np.float64)
    kb = attenuation_curve(wave, -1.3).astype(np.float64)

    for start_idx in range(0, n_sample, chunk_size):
        end_idx = min(start_idx + chunk_size, n_sample)
        batch_sample_idx = sampled_indices[start_idx:end_idx]

        try:
            # Load batch data
            if is_spectra:
                batch_out = np.asarray(g_out["spectra"][:][batch_sample_idx] if total_galaxies <= 50_000 else np.stack([g_out["spectra"][i] for i in batch_sample_idx]))
            else:
                batch_out = np.asarray(g_out["photometry"][:][batch_sample_idx] if total_galaxies <= 50_000 else np.stack([g_out["photometry"][i] for i in batch_sample_idx]))

            # Preload batch context once to avoid O(N) random I/O reads in anomaly loops
            batch_td = np.asarray(g_in["tau_diffuse"][:])[batch_sample_idx] if "tau_diffuse" in g_in else None
            batch_tb = np.asarray(g_in["tau_birth"][:])[batch_sample_idx] if "tau_birth" in g_in else None
            batch_p = np.asarray(g_in["params"][:])[batch_sample_idx] if "params" in g_in else None
            batch_sfh_ctx = np.asarray(g_in["sfh"][:])[batch_sample_idx] if "sfh" in g_in else None

            def _extract_galaxy_context(local_i: int) -> dict[str, float]:
                ctx: dict[str, float] = {}
                if batch_td is not None:
                    ctx["tau_diffuse"] = float(batch_td[local_i])
                if batch_tb is not None:
                    ctx["tau_birth"] = float(batch_tb[local_i])
                if batch_sfh_ctx is not None:
                    sfh_row = np.asarray(batch_sfh_ctx[local_i], dtype=np.float64)
                    tot_mass = float(np.sum(sfh_row))
                    young_mass = float(np.sum(sfh_row[:ny])) if ny > 0 else 0.0
                    ctx["total_stellar_mass_msun"] = tot_mass
                    ctx["young_stellar_fraction"] = young_mass / max(tot_mass, 1e-35)
                if batch_p is not None and len(batch_p[local_i]) >= 6:
                    ctx["log_stellar_mass"] = float(batch_p[local_i, 0])
                    ctx["t_onset_gyr"] = float(batch_p[local_i, 1])
                    ctx["sfh_tau_gyr"] = float(batch_p[local_i, 2])
                    ctx["log_metallicity"] = float(batch_p[local_i, 3])
                if redshift > 0.0:
                    ctx["redshift"] = float(redshift)
                return ctx

            # Tier 1: Numerical checks on outputs
            valid_num, bad_num = check_finite_positive(batch_out)
            for bad_i in bad_num:
                g_idx = int(batch_sample_idx[bad_i])
                category_counts["NUMERICAL_FAULT"] += 1
                if len(anomalies) < 1000:
                    anomalies.append(AnomalyRecord(
                        anomaly_id=f"NUM-{g_idx}",
                        tier=1,
                        category="NUMERICAL_FAULT",
                        severity="CRITICAL",
                        galaxy_index=g_idx,
                        metric_name="finite_positive_flux",
                        observed_value=float(np.nanmin(batch_out[bad_i])) if np.any(np.isnan(batch_out[bad_i])) else float(np.min(batch_out[bad_i])),
                        expected_range=[1e-35, 1e30],
                        input_parameters=_extract_galaxy_context(bad_i),
                        root_cause="Flux contains NaN, Inf, or non-positive value.",
                        remediation="Inspect input parameters for negative masses or unphysical zeros.",
                    ))

            # Tier 1 & 2: If spectra are available, run physical invariant checks
            if is_spectra and "sfh" in g_in:
                batch_sfh = np.asarray(g_in["sfh"][:][batch_sample_idx] if total_galaxies <= 50_000 else np.stack([g_in["sfh"][i] for i in batch_sample_idx])).astype(np.float64)
                batch_td = np.asarray(g_in["tau_diffuse"][:])[batch_sample_idx].astype(np.float64)
                batch_tb = np.asarray(g_in["tau_birth"][:])[batch_sample_idx].astype(np.float64)

                # Reference intrinsic spectra before dust
                batch_intr = batch_sfh[:, ny:] @ ssp[ny:] + batch_sfh[:, :ny] @ ssp[:ny]
                valid_energy, bad_energy, ratios = check_energy_conservation(batch_out, batch_intr)
                for bad_e in bad_energy:
                    g_idx = int(batch_sample_idx[bad_e])
                    category_counts["PHYSICAL_ANOMALY"] += 1
                    if len(anomalies) < 1000:
                        anomalies.append(AnomalyRecord(
                            anomaly_id=f"ENG-{g_idx}",
                            tier=1,
                            category="PHYSICAL_ANOMALY",
                            severity="ERROR",
                            galaxy_index=g_idx,
                            metric_name="energy_conservation_ratio",
                            observed_value=float(ratios[bad_e]),
                            expected_range=[0.0, 1.0],
                            input_parameters=_extract_galaxy_context(bad_e),
                            root_cause="Attenuated flux exceeds intrinsic flux (negative dust optical depth).",
                            remediation="Clamp tau_diffuse and tau_birth to non-negative values.",
                        ))

                # Dn(4000) Break
                d4000 = measure_d4000_break(wave, batch_out)
                bad_d4000 = np.where(np.isfinite(d4000) & ((d4000 < 0.95) | (d4000 > 2.80)))[0]
                for bad_d in bad_d4000:
                    g_idx = int(batch_sample_idx[bad_d])
                    category_counts["PHYSICAL_ANOMALY"] += 1
                    if len(anomalies) < 1000:
                        anomalies.append(AnomalyRecord(
                            anomaly_id=f"D4K-{g_idx}",
                            tier=2,
                            category="PHYSICAL_ANOMALY",
                            severity="WARNING",
                            galaxy_index=g_idx,
                            metric_name="d4000_break",
                            observed_value=float(d4000[bad_d]),
                            expected_range=[0.95, 2.80],
                            input_parameters=_extract_galaxy_context(bad_d),
                            root_cause="Inverted or extreme D_n(4000) break.",
                            remediation="Check old-to-young stellar age ratio in SFH grid.",
                        ))

                # UV Continuum Slope beta
                uv_slope = measure_uv_slope(wave, batch_out)
                bad_uv = np.where(np.isfinite(uv_slope) & ((uv_slope < -2.80) | (uv_slope > 1.80)))[0]
                for bad_u in bad_uv:
                    g_idx = int(batch_sample_idx[bad_u])
                    category_counts["PHYSICAL_ANOMALY"] += 1
                    if len(anomalies) < 1000:
                        anomalies.append(AnomalyRecord(
                            anomaly_id=f"UVB-{g_idx}",
                            tier=2,
                            category="PHYSICAL_ANOMALY",
                            severity="WARNING",
                            galaxy_index=g_idx,
                            metric_name="uv_slope_beta",
                            observed_value=float(uv_slope[bad_u]),
                            expected_range=[-2.80, 1.80],
                            input_parameters=_extract_galaxy_context(bad_u),
                            root_cause="Unphysical UV continuum slope (super-Rayleigh-Jeans or over-reddened).",
                            remediation="Review dust extinction curve index and burst fraction.",
                        ))

            # Tier 2: Check photometry bounds if photometry output and values are in apparent magnitude range (~5 to 45)
            if not is_spectra:
                med_val = float(np.nanmedian(batch_out))
                if 5.0 <= med_val <= 45.0:
                    valid_mags, bad_mags = check_magnitude_bounds(batch_out, min_mag=min_mag, max_mag=max_mag)
                    for bad_m in bad_mags:
                        g_idx = int(batch_sample_idx[bad_m])
                        category_counts["PHYSICAL_ANOMALY"] += 1
                        if len(anomalies) < 1000:
                            anomalies.append(AnomalyRecord(
                                anomaly_id=f"MAG-{g_idx}",
                                tier=2,
                                category="PHYSICAL_ANOMALY",
                                severity="WARNING",
                                galaxy_index=g_idx,
                                metric_name="ab_magnitude_range",
                                observed_value=float(np.min(batch_out[bad_m])),
                                expected_range=[min_mag, max_mag],
                                input_parameters=_extract_galaxy_context(bad_m),
                                root_cause="Magnitude falls outside standard survey limits.",
                                remediation="Verify cosmological distance modulus and normalization.",
                            ))

        except Exception as e:
            # UNKNOWN EXCEPTION: Safely isolate and dump to quarantine without crashing
            err_msg = str(e)
            tb_str = traceback.format_exc(limit=4)
            category_counts["UNKNOWN_EXCEPTION"] += 1

            Path(quarantine_dir).mkdir(parents=True, exist_ok=True)
            dump_filename = f"quarantine_chunk_{start_idx}_{end_idx}.json"
            dump_path = os.path.join(quarantine_dir, dump_filename)
            quarantined_files.append(dump_path)

            with open(dump_path, "w", encoding="utf-8") as qf:
                json.dump({
                    "start_index": int(start_idx),
                    "end_index": int(end_idx),
                    "error_message": err_msg,
                    "stack_trace": tb_str,
                }, qf, indent=2)

            anomalies.append(AnomalyRecord(
                anomaly_id=f"UNK-{start_idx}",
                tier=1,
                category="UNKNOWN_EXCEPTION",
                severity="CRITICAL",
                galaxy_index=int(batch_sample_idx[0]),
                metric_name="unexpected_runtime_exception",
                root_cause=f"Unhandled exception during batch execution: {err_msg}",
                remediation=f"Inspect quarantined crash report at {dump_path}",
            ))
            del e  # Release exception frame memory immediately

    # Final calculations
    total_anomalies = len(anomalies)
    passed_count = max(0, n_sample - total_anomalies)
    pass_rate = (passed_count / max(1, n_sample)) * 100.0
    anomaly_rate = total_anomalies / max(1, n_sample)

    if category_counts["NUMERICAL_FAULT"] > 0 or category_counts["UNKNOWN_EXCEPTION"] > 0 or anomaly_rate > max_anomaly_rate:
        status = "CRITICAL_FAILURE"
    elif total_anomalies > 0:
        status = "WARNING"
    else:
        status = "PASSED"

    tier_summary = {
        "tier1_numerical": category_counts["NUMERICAL_FAULT"] + category_counts["INPUT_SCHEMA_FAULT"] + category_counts["UNKNOWN_EXCEPTION"],
        "tier2_physical": category_counts["PHYSICAL_ANOMALY"],
        "tier3_population": category_counts["POPULATION_DRIFT"],
    }

    if attach_is_valid:
        try:
            bad_global_indices = set(a.galaxy_index for a in anomalies)
            is_valid_mask = np.ones(total_galaxies, dtype=bool)
            for b_idx in bad_global_indices:
                if 0 <= b_idx < total_galaxies:
                    is_valid_mask[b_idx] = False
            try:
                g_out_w = zarr.open_group(out_store, mode="a")
            except Exception:
                g_out_w = zarr.open_group(fsspec.get_mapper(out_store), mode="a")
            g_out_w.create_dataset("is_valid", data=is_valid_mask, overwrite=True)
        except Exception:
            pass

    return SentryReport(
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        provenance="specsynth Scientific Sentry QA Audit",
        total_galaxies_evaluated=n_sample,
        passed_count=passed_count,
        flagged_count=total_anomalies,
        pass_rate_pct=pass_rate,
        status=status,
        tier_summary=tier_summary,
        category_summary=category_counts,
        quarantined_files=quarantined_files,
        anomalies=anomalies,
    )
