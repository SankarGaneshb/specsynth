import json
import numpy as np
import pytest

from specsynth.benchmark import (
    get_system_hardware_info,
    print_benchmark_summary,
    run_benchmark_suite,
)


def test_get_system_hardware_info():
    info = get_system_hardware_info()
    assert "os" in info
    assert "python_version" in info
    assert "cpu_processor" in info
    assert "cpu_count_physical" in info
    assert "total_ram_gb" in info
    assert info["cpu_count_physical"] >= 1
    assert info["total_ram_gb"] > 0


def test_run_benchmark_suite_small():
    # Run a fast mini-benchmark to verify calculations
    report = run_benchmark_suite(n_gal=200, n_runs=2, n_warmup=1, enable_gpu=False)

    assert "timestamp" in report
    assert report["provenance_type"] == "Measured Benchmark (Local Hardware)"
    assert "cpu_performance" in report

    cpu = report["cpu_performance"]
    assert cpu["throughput_galaxies_per_sec"] > 0
    assert cpu["compute_gflops"] >= 0
    assert cpu["mean_elapsed_seconds"] > 0

    assert "projected_cluster_scaling" in report
    proj = report["projected_cluster_scaling"]["estimates"]
    assert "8_cpu_workers" in proj
    assert "32_cpu_workers" in proj
    assert proj["8_cpu_workers"]["projected_throughput_gal_s"] > 0

    # Ensure JSON serializability
    serialized = json.dumps(report)
    assert len(serialized) > 100


def test_print_benchmark_summary(capsys):
    report = run_benchmark_suite(n_gal=100, n_runs=1, n_warmup=1, enable_gpu=False)
    print_benchmark_summary(report)
    captured = capsys.readouterr()
    assert "SPECSYNTH SCIENTIFIC BENCHMARK & SCALING REPORT" in captured.out
    assert "NUMERICAL CORRECTNESS" in captured.out
    assert "SINGLE-NODE ACCELERATION" in captured.out
    assert "DISTRIBUTED SCALING" in captured.out
    assert "CLOUD ECONOMICS" in captured.out
