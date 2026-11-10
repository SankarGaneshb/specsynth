from __future__ import annotations

import json
import os
import platform
import subprocess
import time
from typing import Any

import numpy as np
import psutil

from specsynth.adapters.toy import build_toy_ssp
from specsynth.core import attenuation_curve, synth_block
from specsynth.gpu import get_device_info, is_gpu_available


def get_system_hardware_info() -> dict[str, Any]:
    """Inspect and return complete host system hardware and BLAS specifications."""
    info: dict[str, Any] = {
        "os": platform.platform(),
        "python_version": platform.python_version(),
        "cpu_arch": platform.machine(),
        "cpu_processor": platform.processor(),
        "cpu_count_physical": psutil.cpu_count(logical=False) or 1,
        "cpu_count_logical": psutil.cpu_count(logical=True) or 1,
        "total_ram_gb": round(psutil.virtual_memory().total / (1024**3), 2),
        "available_ram_gb": round(psutil.virtual_memory().available / (1024**3), 2),
    }

    # Git commit provenance
    try:
        git_hash = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, text=True
        ).strip()
        info["git_commit"] = git_hash
    except Exception:
        info["git_commit"] = "unknown"

    # BLAS / NumPy backend info
    try:
        blas_info = np.show_config(mode="dicts")
        info["blas_backend"] = blas_info.get("Build Dependencies", {}).get("blas", {}).get("name", "standard")
    except Exception:
        info["blas_backend"] = "numpy_default"

    # GPU device info
    gpu_info = get_device_info()
    info["gpu_available"] = gpu_info["gpu_available"]
    if gpu_info["gpu_available"]:
        info["gpu_device_name"] = gpu_info.get("device_name", "Unknown GPU")
        info["gpu_cupy_version"] = gpu_info.get("cupy_version", "unknown")
        info["gpu_cuda_version"] = gpu_info.get("cuda_version", "unknown")
        info["gpu_total_memory_gb"] = gpu_info.get("total_memory_gb", 0.0)

    return info


def run_benchmark_suite(
    n_gal: int = 50_000,
    n_runs: int = 5,
    n_warmup: int = 2,
    enable_gpu: bool = False,
) -> dict[str, Any]:
    """
    Run an end-to-end reproducible synthetic workload to measure
    galaxies/second, computational FLOPs, and memory processing bandwidth.
    """
    n_age, n_met, n_wave = 15, 4, 1200
    ages, mets, wave, ssp = build_toy_ssp(n_age, n_met, n_wave)
    K, W = ssp.shape
    n_young = int(K * 0.25)

    kd = attenuation_curve(wave, -0.7)
    kb = attenuation_curve(wave, -1.3)

    rng = np.random.default_rng(42)
    sfh = rng.uniform(0.01, 1.0, (n_gal, K)).astype(np.float32)
    tau_d = rng.gamma(2.0, 0.25, n_gal).astype(np.float32)
    tau_b = rng.gamma(2.0, 0.35, n_gal).astype(np.float32)

    # Arithmetic operations:
    # 2 GEMMs: 2 * (n_gal * K * W) operations
    # Dust: exp + multiply ~ 6 ops/element * (n_gal * W)
    total_flops = 4.0 * n_gal * K * W + 6.0 * n_gal * W
    # Memory volume: input SFH (n*K*4) + output spectra (n*W*4) + dust vectors
    memory_bytes = (n_gal * K * 4) + (n_gal * W * 4) + (n_gal * 8) + (W * 8)

    # CPU Benchmark
    for _ in range(n_warmup):
        _ = synth_block(sfh[:1000], tau_d[:1000], tau_b[:1000], ssp, kd, kb, n_young, use_gpu=False)

    cpu_times = []
    for _ in range(n_runs):
        t0 = time.perf_counter()
        _ = synth_block(sfh, tau_d, tau_b, ssp, kd, kb, n_young, use_gpu=False)
        cpu_times.append(time.perf_counter() - t0)

    cpu_times = np.array(cpu_times)
    mean_cpu_time = float(np.mean(cpu_times))
    std_cpu_time = float(np.std(cpu_times))
    cpu_throughput = n_gal / mean_cpu_time
    cpu_gflops = (total_flops / mean_cpu_time) / 1e9
    cpu_gb_s = (memory_bytes / mean_cpu_time) / (1024**3)

    results: dict[str, Any] = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "provenance_type": "Measured Benchmark (Local Hardware)",
        "workload": {
            "n_galaxies": n_gal,
            "ssp_grid_k": K,
            "n_wavelengths": W,
            "n_runs": n_runs,
            "n_warmup": n_warmup,
            "total_giga_ops": round(total_flops / 1e9, 3),
        },
        "system": get_system_hardware_info(),
        "cpu_performance": {
            "mean_elapsed_seconds": round(mean_cpu_time, 4),
            "std_elapsed_seconds": round(std_cpu_time, 4),
            "throughput_galaxies_per_sec": round(cpu_throughput, 1),
            "compute_gflops": round(cpu_gflops, 2),
            "memory_bandwidth_gb_s": round(cpu_gb_s, 2),
        },
    }

    # GPU Benchmark if requested and available
    gpu_available = is_gpu_available()
    if enable_gpu and gpu_available:
        try:
            for _ in range(n_warmup):
                _ = synth_block(sfh[:1000], tau_d[:1000], tau_b[:1000], ssp, kd, kb, n_young, use_gpu=True)

            gpu_times = []
            for _ in range(n_runs):
                t0 = time.perf_counter()
                _ = synth_block(sfh, tau_d, tau_b, ssp, kd, kb, n_young, use_gpu=True)
                gpu_times.append(time.perf_counter() - t0)

            gpu_times = np.array(gpu_times)
            mean_gpu_time = float(np.mean(gpu_times))
            std_gpu_time = float(np.std(gpu_times))
            gpu_throughput = n_gal / mean_gpu_time
            gpu_gflops = (total_flops / mean_gpu_time) / 1e9
            gpu_gb_s = (memory_bytes / mean_gpu_time) / (1024**3)
            speedup = cpu_throughput > 0 and (gpu_throughput / cpu_throughput) or 1.0

            results["gpu_performance"] = {
                "mean_elapsed_seconds": round(mean_gpu_time, 4),
                "std_elapsed_seconds": round(std_gpu_time, 4),
                "throughput_galaxies_per_sec": round(gpu_throughput, 1),
                "compute_gflops": round(gpu_gflops, 2),
                "memory_bandwidth_gb_s": round(gpu_gb_s, 2),
                "speedup_vs_cpu": round(speedup, 2),
            }
        except Exception as e:
            results["gpu_performance"] = {"error": str(e)}

    # Multi-node projections (explicitly labeled as Projected)
    results["projected_cluster_scaling"] = {
        "provenance_type": "Projected Benchmark (Linear Scaling Model with 85% Efficiency)",
        "assumptions": "Dask distributed cluster on GCP Spot VMs ($0.088/hr per 8 vCPU)",
        "estimates": {
            "8_cpu_workers": {
                "projected_throughput_gal_s": round(cpu_throughput * 8 * 0.90, 0),
                "time_for_1m_galaxies_s": round(1_000_000 / (cpu_throughput * 8 * 0.90), 1),
                "estimated_cost_per_million_usd": round((1_000_000 / (cpu_throughput * 8 * 0.90) / 3600) * 0.088, 4),
            },
            "32_cpu_workers": {
                "projected_throughput_gal_s": round(cpu_throughput * 32 * 0.85, 0),
                "time_for_100m_galaxies_min": round((100_000_000 / (cpu_throughput * 32 * 0.85)) / 60, 1),
                "estimated_cost_per_100m_usd": round(((100_000_000 / (cpu_throughput * 32 * 0.85)) / 3600) * (0.088 * 4), 2),
            },
        },
    }

    return results


def print_benchmark_summary(report: dict[str, Any]) -> None:
    """Print an ASCII provenance table of benchmark results to stdout."""
    sys_info = report["system"]
    cpu = report["cpu_performance"]
    workload = report["workload"]

    print("\n" + "=" * 70)
    print("           SPECSYNTH REPRODUCIBLE BENCHMARK REPORT")
    print("=" * 70)
    print(f" Provenance         : {report['provenance_type']}")
    print(f" Timestamp          : {report['timestamp']}")
    print(f" Git Commit         : {sys_info.get('git_commit', 'unknown')[:10]}")
    print(f" Host OS            : {sys_info['os']}")
    print(f" CPU Model          : {sys_info['cpu_processor']} ({sys_info['cpu_count_physical']} cores, {sys_info['cpu_count_logical']} threads)")
    print(f" Total System RAM   : {sys_info['total_ram_gb']} GB")
    print(f" BLAS Backend       : {sys_info.get('blas_backend', 'N/A')}")
    print(f" Workload Scale     : {workload['n_galaxies']:,} galaxies x {workload['n_wavelengths']} wavelengths")
    print("-" * 70)
    print(" [MEASURED LOCAL BENCHMARK: CPU BLAS]")
    print(f"  * Execution Time   : {cpu['mean_elapsed_seconds']:.4f}s (± {cpu['std_elapsed_seconds']:.4f}s)")
    print(f"  * Throughput       : {cpu['throughput_galaxies_per_sec']:,.0f} galaxies/sec")
    print(f"  * Compute Rate     : {cpu['compute_gflops']:.2f} GFLOPS")
    print(f"  * Memory Bandwidth : {cpu['memory_bandwidth_gb_s']:.2f} GB/s")

    if "gpu_performance" in report and "throughput_galaxies_per_sec" in report["gpu_performance"]:
        gpu = report["gpu_performance"]
        print("-" * 70)
        print(f" [MEASURED LOCAL BENCHMARK: GPU ({sys_info.get('gpu_device_name', 'CUDA')})]")
        print(f"  * Execution Time   : {gpu['mean_elapsed_seconds']:.4f}s (± {gpu['std_elapsed_seconds']:.4f}s)")
        print(f"  * Throughput       : {gpu['throughput_galaxies_per_sec']:,.0f} galaxies/sec")
        print(f"  * Compute Rate     : {gpu['compute_gflops']:.2f} GFLOPS")
        print(f"  * Speedup vs CPU   : {gpu.get('speedup_vs_cpu', 1.0):.1f}x")

    proj = report["projected_cluster_scaling"]["estimates"]
    print("-" * 70)
    print(" [PROJECTED CLUSTER BENCHMARK: Weak Scaling at 85-90% Efficiency]")
    print(f"  * 8 vCPU Worker    : {proj['8_cpu_workers']['projected_throughput_gal_s']:,.0f} gal/s | $1M gals in {proj['8_cpu_workers']['time_for_1m_galaxies_s']}s (~${proj['8_cpu_workers']['estimated_cost_per_million_usd']} USD)")
    print(f"  * 32 vCPU Cluster  : {proj['32_cpu_workers']['projected_throughput_gal_s']:,.0f} gal/s | 100M gals in {proj['32_cpu_workers']['time_for_100m_galaxies_min']} min (~${proj['32_cpu_workers']['estimated_cost_per_100m_usd']} USD)")
    print("=" * 70 + "\n")
