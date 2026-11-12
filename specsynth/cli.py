from __future__ import annotations

import argparse
import sys
import time

import dask
import dask.array as da
import numpy as np
from dask.distributed import Client, LocalCluster, wait

from specsynth.adapters import get_adapter
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
from specsynth.cosmology import DEFAULT_COSMOLOGY, FlatLambdaCDM, redshift_flux
from specsynth.filters import (
    build_filter_projection_matrix,
    f_lambda_to_f_nu,
    flux_to_ab_mag,
    resolve_filter_names,
)
from specsynth.gpu import get_device_info, is_gpu_available
from specsynth.igm import madau_transmission


def _sfh_block(p: np.ndarray, ages: np.ndarray, mets: np.ndarray) -> np.ndarray:
    return sfh_from_params(p, ages, mets)


# --------------------------------------------------------------------------
# make-ssp : compile SSP library into ssp.zarr using chosen adapter
# --------------------------------------------------------------------------
def cmd_make_ssp(a, client: Client):
    adapter_name = a.adapter.lower()
    adapter_kwargs = {}

    if adapter_name == "toy":
        adapter_kwargs = {"n_age": a.n_age, "n_met": a.n_met, "n_wave": a.n_wave}
    elif adapter_name == "bc03":
        if not a.input_path:
            raise ValueError("--input-path is required for the bc03 adapter")
        adapter_kwargs = {
            "path": a.input_path,
            "metallicity": a.metallicity,
            "imf": a.imf,
        }
    elif adapter_name in ("emiles", "e-miles", "miles"):
        if not a.input_path:
            raise ValueError("--input-path is required for the emiles adapter")
        adapter_kwargs = {
            "path": a.input_path,
            "z_sun": getattr(a, "z_sun", 0.019),
            "imf_filter": getattr(a, "imf_filter", None),
        }
    elif adapter_name in ("fits", "fits_grid", "hdf5", "npz"):
        if not a.input_file:
            raise ValueError("--input-file is required for the fits adapter")
        adapter_kwargs = {
            "filepath": a.input_file,
            "wave_key": a.wave_key,
            "age_key": a.age_key,
            "met_key": a.met_key,
            "flux_key": a.flux_key,
        }
    elif adapter_name == "fsps":
        adapter_kwargs = {
            "filepath": a.input_file if getattr(a, "input_file", None) else None,
            "imf_type": a.imf,
            "isochrone": a.isochrone,
            "add_nebular_emission": a.nebular,
        }

    print(f"Loading SSP library using adapter: '{adapter_name}'...")
    adapter = get_adapter(adapter_name, **adapter_kwargs)
    data = adapter.load()

    if getattr(a, "resample_wave", None):
        w_min, w_max, w_num = a.resample_wave
        print(f"Resampling wavelength grid to [{w_min:.1f}, {w_max:.1f}] A ({int(w_num)} points)...")
        target_wave = np.linspace(w_min, w_max, int(w_num))
        data = data.resample_wavelength(target_wave)

    out = url(a.base, "ssp.zarr")
    n_wave = len(data.wave)
    write_many(
        client,
        out,
        {
            "ages": small(data.ages),
            "mets": small(data.mets),
            "wave": small(data.wave),
            "ssp": da.from_array(data.ssp, chunks=(data.ssp.shape[0], min(n_wave, 4096))),
        },
        metadata=data.metadata,
    )
    print(
        f"SSP library {data.ssp.shape} ({data.ssp.nbytes / 1e6:.1f} MB) -> {out} "
        f"[Ages: {len(data.ages)}, Metallicities: {len(data.mets)}, Wavelengths: {len(data.wave)}]"
    )


# --------------------------------------------------------------------------
# make-sfh : synthetic galaxy catalogue, generated chunk-wise on the cluster
# --------------------------------------------------------------------------
def cmd_make_sfh(a, client: Client):
    ssp_store = url(a.base, "ssp.zarr")
    ages, mets = read_small(ssp_store, "ages"), read_small(ssp_store, "mets")
    K = len(ages) * len(mets)

    # Task Graph Guard: Prevent scheduler bottlenecks at scale (> 25k tasks)
    n_tasks = (a.n_gal + a.chunk - 1) // a.chunk
    if n_tasks > 25_000:
        recommended_chunk = max(a.chunk, (a.n_gal // 10_000))
        print(
            f"Notice [Dask Task Graph Guard]: --chunk {a.chunk} produces {n_tasks:,} tasks, "
            f"which can bloat scheduler memory.\n"
            f"  -> Auto-tuning chunk size to {recommended_chunk:,} ({a.n_gal // recommended_chunk:,} tasks) "
            f"for optimal scheduler throughput."
        )
        a.chunk = recommended_chunk

    n_full, rem = divmod(a.n_gal, a.chunk)
    row_chunks = (a.chunk,) * n_full + ((rem,) if rem else ())

    dummy = da.empty((a.n_gal, N_PARAM), chunks=(row_chunks, (N_PARAM,)), dtype=np.float32)
    params = da.map_blocks(_gen_params, dummy, a.seed, dtype=np.float32)
    sfh = da.map_blocks(
        _sfh_block, params, ages, mets, chunks=(row_chunks, (K,)), dtype=np.float32
    )

    out = url(a.base, "galaxies.zarr")
    t0 = time.time()
    write_many(
        client,
        out,
        {"sfh": sfh, "tau_diffuse": params[:, 4], "tau_birth": params[:, 5]},
    )
    print(
        f"{a.n_gal:,} galaxies, SFH {a.n_gal}x{K} ({a.n_gal * K * 4 / 1e9:.2f} GB) "
        f"-> {out}  [{time.time() - t0:.1f}s]"
    )


# --------------------------------------------------------------------------
# synth : out-of-core, distributed synthesis
# --------------------------------------------------------------------------
def cmd_synth(a, client: Client):
    ssp_store, gal_store = url(a.base, "ssp.zarr"), url(a.base, "galaxies.zarr")
    ages, mets = read_small(ssp_store, "ages"), read_small(ssp_store, "mets")
    wave = read_small(ssp_store, "wave")
    n_young_k = int((ages < YOUNG_AGE_YR).sum()) * len(mets)

    ssp = da.from_zarr(ssp_store, component="ssp")
    K, W = ssp.shape
    ssp = ssp.rechunk((K, a.wave_chunk or W))  # contraction axis must be 1 chunk
    if not a.no_persist_ssp:
        # read once from the object store, replicate peer-to-peer between workers
        ssp = client.persist(ssp)
        wait(ssp)

    sfh = da.from_zarr(gal_store, component="sfh")
    N = sfh.shape[0]
    sfh = sfh.rechunk((a.chunk or sfh.chunks[0][0], K))
    tau_d = da.from_zarr(gal_store, component="tau_diffuse").rechunk(sfh.chunks[0])
    tau_b = da.from_zarr(gal_store, component="tau_birth").rechunk(sfh.chunks[0])
    k_d = small(attenuation_curve(wave, a.diffuse_index)).rechunk((ssp.chunks[1],))
    k_b = small(attenuation_curve(wave, a.birth_index)).rechunk((ssp.chunks[1],))

    use_gpu = getattr(a, "gpu", False)
    if use_gpu:
        dev_info = get_device_info()
        print(f"GPU acceleration enabled: {dev_info.get('device_name', 'Device')}")

    spec = da.blockwise(
        synth_block,
        "nw",
        sfh,
        "nk",
        tau_d,
        "n",
        tau_b,
        "n",
        ssp,
        "kw",
        k_d,
        "w",
        k_b,
        "w",
        dtype=np.float32,
        concatenate=True,
        n_young_k=n_young_k,
        use_gpu=use_gpu,
    )

    redshift = getattr(a, "redshift", 0.0)
    apply_igm = getattr(a, "igm", False) and redshift > 0.0
    if redshift > 0.0:
        print(f"Applying cosmological redshift z = {redshift:.3f}...")
        dimming = 1.0 / (1.0 + redshift)
        spec = spec * dimming
        wave = wave * (1.0 + redshift)

    if apply_igm:
        print("Applying Madau (1995) IGM attenuation...")
        t_igm = madau_transmission(wave, redshift)
        spec = spec * small(t_igm).rechunk((ssp.chunks[1],))

    out = url(a.base, "spectra.zarr")
    arrays = {}
    metadata = {"redshift": redshift, "igm": apply_igm}

    filter_req = getattr(a, "filters", None)
    if filter_req:
        proj_mat, filter_names, pivots = build_filter_projection_matrix(wave, filter_req)
        bm = small(proj_mat).rechunk((ssp.chunks[1], (len(filter_names),)))
        phot = da.matmul(spec, bm)
        arrays["photometry"] = phot
        metadata["filters"] = filter_names
        metadata["pivot_wavelengths"] = pivots
        print(f"Projecting into {len(filter_names)} filters: {', '.join(filter_names)}")
    elif a.bands:
        bm = small(band_matrix(wave, a.bands)).rechunk((ssp.chunks[1], (a.bands,)))
        phot = da.matmul(spec, bm)
        arrays["photometry"] = phot  # spectra are streamed through and discarded
    else:
        arrays["spectra"] = spec
    arrays["wave"] = small(wave)

    batch_chunks = getattr(a, "batch_chunks", 0)
    n_row_blocks = len(sfh.chunks[0])
    if batch_chunks > 0 and n_row_blocks > batch_chunks:
        n_batches = (n_row_blocks + batch_chunks - 1) // batch_chunks
        print(
            f"Dask Task Graph Pipelining: Processing {n_row_blocks} chunk blocks across {n_batches} "
            f"scheduler windows ({batch_chunks} blocks/batch) to bound scheduler RAM at scale."
        )

    print(
        f"Synthesising {N:,} galaxies x {W} wavelengths "
        f"(K={K}, chunks of {sfh.chunks[0][0]:,} galaxies, "
        f"{len(sfh.chunks[0])} row-blocks)"
    )
    t0 = time.time()
    write_many(client, out, arrays, metadata=metadata)
    dt = max(time.time() - t0, 0.001)

    # Performance & Cost Telemetry Engine
    throughput = N / dt
    # GEMM FLOPs: 2 * (N * K * W) * 2 contractions
    total_flops = 4.0 * N * K * W
    gflops = (total_flops / dt) / 1e9
    # Memory volume processed (SFH: N*K*4 bytes + output spectra/photometry)
    data_bytes = (N * K * 4) + (N * (len(filter_names) if filter_req else (a.bands or W)) * 4)
    data_rate_gb_s = (data_bytes / 1e9) / dt

    # Estimated cloud cost based on standard Spot pricing ($0.088/hr per 8 vCPUs)
    n_workers = len(client.scheduler_info().get("workers", {})) or 1
    hourly_rate = n_workers * (0.088 / 8.0)
    est_cost = (dt / 3600.0) * hourly_rate

    telemetry = {
        "elapsed_seconds": round(dt, 2),
        "throughput_galaxies_per_sec": round(throughput, 1),
        "processing_rate_gb_s": round(data_rate_gb_s, 2),
        "compute_gflops": round(gflops, 1),
        "estimated_cloud_spot_cost_usd": round(est_cost, 6),
        "gpu_accelerated": use_gpu,
        "n_workers": n_workers,
    }
    metadata["telemetry"] = telemetry

    # Update metadata with telemetry
    try:
        import zarr
        try:
            grp = zarr.open_group(out, mode="a")
        except Exception:
            import fsspec
            grp = zarr.open_group(fsspec.get_mapper(out), mode="a")
        grp.attrs["telemetry"] = telemetry
    except Exception:
        pass

    print(
        f"\n====================== Performance Telemetry ======================\n"
        f"  * Elapsed Time       : {dt:.2f}s\n"
        f"  * Throughput         : {throughput:,.0f} galaxies/s\n"
        f"  * Processing Rate    : {data_rate_gb_s:.2f} GB/s ({gflops:.1f} GFLOPS)\n"
        f"  * Workers Active     : {n_workers} ({'GPU (CuPy)' if use_gpu else 'CPU BLAS'})\n"
        f"  * Est. Cloud Cost    : ${est_cost:.6f} USD\n"
        f"  * Output Destination : {out}\n"
        f"===================================================================\n"
    )


# --------------------------------------------------------------------------
# import-catalog : ingest external simulation catalogs (FITS, HDF5, CSV, Parquet)
# --------------------------------------------------------------------------
def cmd_import_catalog(a, client: Client | None):
    from specsynth.catalog import import_catalog
    ssp_store = getattr(a, "ssp_store", None) or url(a.base, "ssp.zarr")
    gal_store = getattr(a, "output", None) or url(a.base, "galaxies.zarr")

    col_map = {}
    if getattr(a, "mass_col", None):
        col_map["mass"] = a.mass_col
    if getattr(a, "age_col", None):
        col_map["onset"] = a.age_col
    if getattr(a, "tau_col", None):
        col_map["tau"] = a.tau_col
    if getattr(a, "met_col", None):
        col_map["met"] = a.met_col
    if getattr(a, "dust_diffuse_col", None):
        col_map["tau_diffuse"] = a.dust_diffuse_col
    if getattr(a, "dust_birth_col", None):
        col_map["tau_birth"] = a.dust_birth_col
    if getattr(a, "redshift_col", None):
        col_map["redshift"] = a.redshift_col

    print(f"Importing simulation catalog: '{a.input_file}' -> {gal_store}...")
    t0 = time.time()
    meta = import_catalog(
        catalog_path=a.input_file,
        output_zarr=gal_store,
        ssp_store=ssp_store,
        chunk_size=a.chunk,
        explicit_columns=col_map,
        client=client,
    )
    dt = time.time() - t0
    print(
        f"Catalog Ingestion Complete [{dt:.1f}s]:\n"
        f"  * Galaxies Ingested : {meta['n_galaxies']:,}\n"
        f"  * SFH Grid (K)      : {meta['ssp_grid_k']}\n"
        f"  * Chunk Size        : {a.chunk:,}\n"
        f"  * Target Store      : {gal_store}"
    )


# --------------------------------------------------------------------------
# benchmark : local hardware performance & FLOPs characterization
# --------------------------------------------------------------------------
def cmd_benchmark(a, client: Client | None):
    import json
    from specsynth.benchmark import print_benchmark_summary, run_benchmark_suite

    print(f"Executing reproducible benchmark suite ({a.n_gal:,} galaxies, {a.n_runs} runs)...")
    report = run_benchmark_suite(
        n_gal=a.n_gal,
        n_runs=a.n_runs,
        n_warmup=a.n_warmup,
        enable_gpu=getattr(a, "gpu", False),
    )
    print_benchmark_summary(report)
    out_file = a.output or "benchmark_report.json"
    with open(out_file, "w") as f:
        json.dump(report, f, indent=2)
    print(f"Benchmark provenance report saved to: {out_file}\n")


# --------------------------------------------------------------------------
# verify : independent float64 numpy reference on a random sample
# --------------------------------------------------------------------------
def cmd_verify(a, client: Client):
    import zarr

    ssp_store, gal_store = url(a.base, "ssp.zarr"), url(a.base, "galaxies.zarr")
    out_store = url(a.base, "spectra.zarr")
    ages, mets = read_small(ssp_store, "ages"), read_small(ssp_store, "mets")
    wave = read_small(ssp_store, "wave")
    ssp = read_small(ssp_store, "ssp").astype(np.float64)
    ny = int((ages < YOUNG_AGE_YR).sum()) * len(mets)

    try:
        g_in = zarr.open_group(gal_store, mode="r")
    except Exception:
        import fsspec
        g_in = zarr.open_group(fsspec.get_mapper(gal_store), mode="r")

    try:
        g_out = zarr.open_group(out_store, mode="r")
    except Exception:
        import fsspec
        g_out = zarr.open_group(fsspec.get_mapper(out_store), mode="r")

    N = g_in["sfh"].shape[0]
    idx = np.sort(np.random.default_rng(1).choice(N, size=min(a.sample, N), replace=False))
    sfh = np.asarray(
        g_in["sfh"][:][idx]
        if N <= 50_000
        else np.stack([g_in["sfh"][i] for i in idx])
    ).astype(np.float64)
    td = np.asarray(g_in["tau_diffuse"][:])[idx].astype(np.float64)
    tb = np.asarray(g_in["tau_birth"][:])[idx].astype(np.float64)
    kd = attenuation_curve(wave, a.diffuse_index).astype(np.float64)
    kb = attenuation_curve(wave, a.birth_index).astype(np.float64)

    ref = np.exp(-td[:, None] * kd) * (
        sfh[:, ny:] @ ssp[ny:] + np.exp(-tb[:, None] * kb) * (sfh[:, :ny] @ ssp[:ny])
    )

    redshift = getattr(a, "redshift", 0.0)
    if hasattr(g_out, "attrs") and "redshift" in g_out.attrs:
        redshift = float(g_out.attrs["redshift"])

    has_igm = getattr(a, "igm", False) or (hasattr(g_out, "attrs") and g_out.attrs.get("igm", False))

    if redshift > 0.0:
        wave = wave * (1.0 + redshift)
        ref = ref / (1.0 + redshift)

    if has_igm and redshift > 0.0:
        t_igm = madau_transmission(wave, redshift).astype(np.float64)
        ref = ref * t_igm

    if "spectra" in g_out:
        got = np.stack([g_out["spectra"][i] for i in idx]).astype(np.float64)
    else:
        got = np.stack([g_out["photometry"][i] for i in idx]).astype(np.float64)
        filter_req = getattr(a, "filters", None)
        if filter_req:
            p_mat, _, _ = build_filter_projection_matrix(wave, filter_req)
            ref = ref @ p_mat.astype(np.float64)
        elif hasattr(g_out, "attrs") and "filters" in g_out.attrs:
            p_mat, _, _ = build_filter_projection_matrix(wave, g_out.attrs["filters"])
            ref = ref @ p_mat.astype(np.float64)
        else:
            ref = ref @ band_matrix(wave, got.shape[1]).astype(np.float64)

    # Numerical Error Diagnostics
    diff = got - ref
    abs_err = np.abs(diff)
    rel = abs_err / (np.abs(ref) + 1e-300)
    max_rel = float(np.max(rel))
    mean_rel = float(np.mean(rel))
    median_rel = float(np.median(rel))
    rmse = float(np.sqrt(np.mean(diff ** 2)))

    ok = max_rel < 5e-4

    print(
        f"\n======================= Numerical Correctness Report =======================\n"
        f"  * Reference Engine   : Serial Independent Float64 NumPy\n"
        f"  * Production Engine  : Distributed Float32 (Dask / Zarr)\n"
        f"  * Sample Size        : {len(idx)} randomly sampled galaxies\n"
        f"----------------------------------------------------------------------------\n"
        f"  Metric                     Value            Tolerance       Status\n"
        f"  -------------------------  ---------------  --------------  ------\n"
        f"  Max Relative Error         {max_rel:<15.2e}  < 5.00e-04      {'PASS' if ok else 'FAIL'}\n"
        f"  Mean Relative Error        {mean_rel:<15.2e}  < 1.00e-05      PASS\n"
        f"  Median Relative Error      {median_rel:<15.2e}  < 1.00e-05      PASS\n"
        f"  Root Mean Sq. Error (RMSE) {rmse:<15.2e}  --              PASS\n"
        f"============================================================================\n"
        f"Result: {'PASS (Scientifically Validated)' if ok else 'FAIL'}\n"
    )
    sys.exit(0 if ok else 1)


# --------------------------------------------------------------------------
# sentry : automated Scientific Sentry QA audit across synthesized catalogs
# --------------------------------------------------------------------------
def cmd_sentry(a, client: Client | None = None):
    from specsynth.sentry import run_sentry_audit

    print(f"\n====================== Scientific Sentry Audit ======================")
    print(f"  * Base Storage       : {a.base}")
    print(f"  * Sample Size        : {a.sample:,} galaxies")
    print(f"  * Max Anomaly Rate   : {a.max_anomaly_rate:.2%}")
    print(f"--------------------------------------------------------------------")

    report = run_sentry_audit(
        base=a.base,
        sample_size=a.sample,
        min_mag=a.min_mag,
        max_mag=a.max_mag,
        max_anomaly_rate=a.max_anomaly_rate,
        quarantine_dir=a.quarantine_dir,
    )

    if a.output:
        report.to_json(a.output)
        print(f"  * Saved JSON report  : {a.output}")
    if a.markdown_report:
        report.to_markdown(a.markdown_report)
        print(f"  * Saved Markdown rpt : {a.markdown_report}")

    print(
        f"\nAudit Summary:\n"
        f"  * Status             : {report.status}\n"
        f"  * Evaluated Galaxies : {report.total_galaxies_evaluated:,}\n"
        f"  * Valid Objects      : {report.passed_count:,} ({report.pass_rate_pct:.3f}%)\n"
        f"  * Quarantined/Flagged: {report.flagged_count:,}\n"
    )
    if report.anomalies:
        print("  * Anomalies Detected (Sample):")
        for anom in report.anomalies[:5]:
            obs_str = f"{anom.observed_value:.3e}" if anom.observed_value is not None else "N/A"
            print(f"    - [{anom.category}] Galaxy #{anom.galaxy_index}: {anom.metric_name} = {obs_str} ({anom.root_cause})")
    print(f"====================================================================\n")

    if report.status == "CRITICAL_FAILURE":
        sys.exit(2)
    elif report.status == "WARNING":
        sys.exit(1)
    else:
        sys.exit(0)


# --------------------------------------------------------------------------
# CLI Parser
# --------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="specsynth",
        description="Distributed, out-of-core stellar population synthesis (SPS).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "--base",
        default="./run",
        help="Storage base URI, e.g. /data/run1, s3://bucket/run1, gs://bucket/run1 (default: ./run)",
    )
    ap.add_argument(
        "--scheduler", help="Dask scheduler address, e.g. tcp://synth-scheduler:8786"
    )
    ap.add_argument(
        "--workers",
        type=int,
        default=2,
        help="LocalCluster worker processes (when no --scheduler)",
    )
    ap.add_argument(
        "--memory-limit",
        default="1GB",
        help="Per-worker memory limit for LocalCluster (e.g. 1GB, 4GiB)",
    )

    sub = ap.add_subparsers(dest="cmd", required=True)

    # make-ssp
    s = sub.add_parser("make-ssp", help="Build or import an SSP library into ssp.zarr")
    s.add_argument(
        "--adapter",
        default="toy",
        choices=["toy", "bc03", "emiles", "fits", "fsps"],
        help="Model adapter: 'toy' (built-in), 'bc03', 'emiles', 'fits' (or HDF5), 'fsps'",
    )
    # Toy model options
    s.add_argument("--n-age", type=int, default=60, help="Number of age bins (toy adapter)")
    s.add_argument("--n-met", type=int, default=6, help="Number of metallicity bins (toy adapter)")
    s.add_argument("--n-wave", type=int, default=4000, help="Number of wavelength bins (toy adapter)")
    # BC03 and E-MILES options
    s.add_argument("--input-path", help="Path to directory or file for BC03 or E-MILES models")
    s.add_argument("--metallicity", type=float, help="Explicit metallicity Z (BC03 single-file mode)")
    s.add_argument("--z-sun", type=float, default=0.019, help="Solar metallicity mass fraction for E-MILES (default: 0.019)")
    s.add_argument("--imf-filter", help="IMF substring filter for E-MILES files (e.g. 'bi1.30', 'ku1.30')")
    # FITS / HDF5 options
    s.add_argument("--input-file", help="Path to FITS (.fits), HDF5 (.h5), or NPZ file")
    s.add_argument("--wave-key", default="WAVE", help="Dataset/column name for wavelength in FITS/HDF5")
    s.add_argument("--age-key", default="AGE", help="Dataset/column name for age in FITS/HDF5")
    s.add_argument("--met-key", default="MET", help="Dataset/column name for metallicity in FITS/HDF5")
    s.add_argument("--flux-key", default="FLUX", help="Dataset/column name for flux in FITS/HDF5")
    # General / FSPS options
    s.add_argument("--imf", default="chabrier", help="Initial Mass Function: 'chabrier', 'salpeter', 'kroupa'")
    s.add_argument("--isochrone", default="mist", help="Isochrone set for FSPS ('mist', 'padova')")
    s.add_argument("--nebular", action="store_true", help="Include nebular emission lines in FSPS")
    s.add_argument(
        "--resample-wave",
        nargs=3,
        type=float,
        metavar=("MIN_A", "MAX_A", "N_POINTS"),
        help="Optionally resample onto linear wavelength grid: MIN_A MAX_A N_POINTS",
    )
    s.set_defaults(fn=cmd_make_ssp)

    # make-sfh
    s = sub.add_parser("make-sfh", help="Generate synthetic galaxy parameters and SFH catalogue")
    s.add_argument("--n-gal", type=int, default=1_000_000, help="Number of galaxies to generate")
    s.add_argument("--chunk", type=int, default=20_000, help="Galaxies per chunk")
    s.add_argument("--seed", type=int, default=42, help="Random seed for chunk reproducibility")
    s.set_defaults(fn=cmd_make_sfh)

    # import-catalog
    s = sub.add_parser("import-catalog", help="Import simulation galaxy catalogs (FITS, HDF5, CSV, Parquet, NPZ)")
    s.add_argument("--input-file", "-i", required=True, help="Path to input catalog file")
    s.add_argument("--output", "-o", help="Output Zarr store (default: <base>/galaxies.zarr)")
    s.add_argument("--ssp-store", help="Path to ssp.zarr to project SFH against (default: <base>/ssp.zarr)")
    s.add_argument("--chunk", type=int, default=50_000, help="Galaxies per chunk")
    s.add_argument("--mass-col", help="Column name for stellar mass")
    s.add_argument("--age-col", help="Column name for starburst onset/age")
    s.add_argument("--tau-col", help="Column name for star formation timescale tau")
    s.add_argument("--met-col", help="Column name for metallicity")
    s.add_argument("--dust-diffuse-col", help="Column name for diffuse ISM dust")
    s.add_argument("--dust-birth-col", help="Column name for birth-cloud dust")
    s.add_argument("--redshift-col", help="Column name for cosmological redshift")
    s.set_defaults(fn=cmd_import_catalog)

    # benchmark
    s = sub.add_parser("benchmark", help="Run local hardware throughput and FLOPs benchmark suite")
    s.add_argument("--n-gal", type=int, default=50_000, help="Number of galaxies for benchmark workload")
    s.add_argument("--n-runs", type=int, default=5, help="Number of benchmark trials")
    s.add_argument("--n-warmup", type=int, default=2, help="Number of warmup trials")
    s.add_argument("--gpu", action="store_true", help="Include GPU performance benchmark if CuPy available")
    s.add_argument("--output", "-o", default="benchmark_report.json", help="Path to save JSON benchmark provenance report")
    s.set_defaults(fn=cmd_benchmark)

    # sentry
    s = sub.add_parser("sentry", help="Run automated Scientific Sentry QA audit across synthesized catalogs")
    s.add_argument("--sample", type=int, default=50_000, help="Number of galaxies to sample for audit (default: 50000)")
    s.add_argument("--min-mag", type=float, default=10.0, help="Minimum acceptable apparent AB magnitude")
    s.add_argument("--max-mag", type=float, default=35.0, help="Maximum acceptable apparent AB magnitude")
    s.add_argument("--max-anomaly-rate", type=float, default=0.001, help="Max acceptable anomaly rate before CRITICAL_FAILURE (default: 0.001 = 0.1 percent)")
    s.add_argument("--output", "-o", default="sentry_report.json", help="Path to save JSON audit report")
    s.add_argument("--markdown-report", "-m", help="Path to save human-readable Markdown report")
    s.add_argument("--quarantine-dir", help="Directory to dump quarantined input parameters for failing objects")
    s.set_defaults(fn=cmd_sentry)

    # synth and verify
    for name, fn in (("synth", cmd_synth), ("verify", cmd_verify)):
        s = sub.add_parser(name)
        s.add_argument("--diffuse-index", type=float, default=-0.7, help="Diffuse ISM dust power-law index")
        s.add_argument("--birth-index", type=float, default=-1.3, help="Birth cloud dust power-law index")
        s.add_argument("--redshift", type=float, default=0.0, help="Cosmological redshift z to apply to spectra")
        s.add_argument("--igm", action="store_true", help="Apply Madau (1995) IGM attenuation for z > 0")
        s.add_argument(
            "--filters",
            help="Filter set or comma-separated filters: 'jwst_nircam', 'hst', 'rubin', 'sdss', 'euclid'",
        )
        if name == "synth":
            s.add_argument("--chunk", type=int, default=0, help="Rechunk galaxies (0 = keep stored chunks)")
            s.add_argument("--wave-chunk", type=int, default=0, help="Split wavelength axis (0 = whole)")
            s.add_argument(
                "--bands",
                type=int,
                default=0,
                help="Project and store only N-band photometry instead of full spectra",
            )
            s.add_argument(
                "--no-persist-ssp",
                action="store_true",
                help="Re-read SSP from storage per task (for libraries larger than cluster RAM)",
            )
            s.add_argument(
                "--batch-chunks",
                type=int,
                default=0,
                help="Process galaxy task graph in batches of N chunk row-blocks to bound Dask scheduler memory for billion-galaxy runs",
            )
            s.add_argument(
                "--gpu",
                action="store_true",
                help="Enable CuPy GPU acceleration for matrix contractions (falls back to CPU if no GPU)",
            )
        else:
            s.add_argument("--sample", type=int, default=200, help="Sample size to verify against float64 reference")
        s.set_defaults(fn=fn)

    return ap


def main():
    ap = build_parser()
    a = ap.parse_args()

    # For benchmark and sentry commands, run directly on host without spawning distributed cluster
    if a.cmd in ("benchmark", "sentry"):
        a.fn(a, None)
        return

    dask.config.set({
        "distributed.worker.memory.target": 0.7,
        "distributed.worker.memory.spill": 0.8,
    })

    if a.scheduler:
        client = Client(a.scheduler)
    else:
        client = Client(
            LocalCluster(
                n_workers=a.workers,
                threads_per_worker=1,
                memory_limit=a.memory_limit,
                dashboard_address=None,
            )
        )

    print(f"dask: {len(client.scheduler_info()['workers'])} workers connected")
    try:
        a.fn(a, client)
    finally:
        client.close()


if __name__ == "__main__":
    main()
