from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import scripts.run_kaggle_gpu as rkg

pytestmark = pytest.mark.integration


def test_get_kaggle_credentials_from_env(monkeypatch):
    monkeypatch.setenv("KAGGLE_USERNAME", "test_astronomer")
    monkeypatch.setenv("KAGGLE_KEY", "secret_key_12345")
    user, key = rkg.get_kaggle_credentials()
    assert user == "test_astronomer"
    assert key == "secret_key_12345"


def test_get_kaggle_credentials_from_kaggle_json(monkeypatch, tmp_path):
    monkeypatch.delenv("KAGGLE_USERNAME", raising=False)
    monkeypatch.delenv("KAGGLE_KEY", raising=False)
    monkeypatch.delenv("KAGGLE_API_TOKEN", raising=False)

    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    fake_kaggle = fake_home / ".kaggle"
    fake_kaggle.mkdir()
    cfg_file = fake_kaggle / "kaggle.json"
    cfg_file.write_text(json.dumps({"username": "file_user", "key": "file_key_999"}), encoding="utf-8")

    monkeypatch.setattr(Path, "home", lambda: fake_home)
    user, key = rkg.get_kaggle_credentials()
    assert user == "file_user"
    assert key == "file_key_999"


def test_generate_worker_script_syntax_and_injection():
    script = rkg.generate_worker_script(n_gal=25000, n_runs=3, commit_sha="abc123456")
    # Verify Python syntax validity
    code_obj = compile(script, "benchmark_worker.py", "exec")
    assert code_obj is not None

    assert "abc123456" in script
    assert "25000" in script
    assert "3" in script
    assert "cupy" in script
    assert "specsynth benchmark" in script
    assert "--gpu" in script
    assert "gpu_manifest.json" in script


def test_cli_dry_run(monkeypatch, capsys):
    test_argv = ["run_kaggle_gpu.py", "--dry-run", "--username", "testuser", "--n-gal", "1000", "--n-runs", "2"]
    monkeypatch.setattr(sys, "argv", test_argv)

    ret = rkg.main()
    assert ret == 0

    captured = capsys.readouterr()
    assert "DRY-RUN mode" in captured.out
    assert "Dry-run validation passed" in captured.out
    assert "testuser/specsynth-gpu-benchmark" in captured.out


def test_resolve_kaggle_cmd(monkeypatch):
    # 1. System PATH binary available
    monkeypatch.setattr(rkg.shutil, "which", lambda cmd: "/usr/bin/kaggle")
    assert rkg.resolve_kaggle_cmd() == ["kaggle"]

    # 2. Virtualenv adjacent binary available
    monkeypatch.setattr(rkg.shutil, "which", lambda cmd: None)
    monkeypatch.setattr(rkg.Path, "exists", lambda self: True)
    bin_name = "kaggle.exe" if sys.platform == "win32" else "kaggle"
    expected_local = str(Path(sys.executable).parent / bin_name)
    assert rkg.resolve_kaggle_cmd() == [expected_local]

    # 3. Python module available via -m kaggle
    monkeypatch.setattr(rkg.Path, "exists", lambda self: False)
    mock_spec = MagicMock()
    monkeypatch.setattr("importlib.util.find_spec", lambda name: mock_spec if name == "kaggle" else None)
    cmd = rkg.resolve_kaggle_cmd()
    assert cmd == [sys.executable, "-m", "kaggle"]

    # 4. Neither binary nor module available
    monkeypatch.setattr("importlib.util.find_spec", lambda name: None)
    assert rkg.resolve_kaggle_cmd() is None


def test_cli_missing_username_fails(monkeypatch, capsys):
    monkeypatch.delenv("KAGGLE_USERNAME", raising=False)
    monkeypatch.delenv("KAGGLE_KEY", raising=False)
    monkeypatch.delenv("KAGGLE_API_TOKEN", raising=False)
    monkeypatch.setattr(rkg, "get_kaggle_credentials", lambda: (None, None))
    monkeypatch.setattr(rkg.shutil, "which", lambda cmd: "/fake/bin/kaggle")

    test_argv = ["run_kaggle_gpu.py", "--n-gal", "1000"]
    monkeypatch.setattr(sys, "argv", test_argv)

    ret = rkg.main()
    assert ret == 1
    captured = capsys.readouterr()
    assert "Error: Kaggle username could not be resolved" in captured.err


def test_cli_mock_full_execution(monkeypatch, tmp_path, capsys):
    out_manifest = tmp_path / "paper" / "test_manifest.json"
    step_summary = tmp_path / "step_summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(step_summary))

    sample_manifest = {
        "workload": {"n_galaxies": 50000},
        "system": {
            "gpu_device_name": "Tesla T4",
            "blas_backend": "scipy-openblas",
            "cpu_processor": "x86_64",
        },
        "category_1_correctness": {
            "status": "PASS",
            "max_relative_error": 9.87e-07,
        },
        "category_2_single_node": {
            "cpu_blas": {
                "throughput_galaxies_per_sec": 57000.0,
                "compute_gflops": 17.0,
                "memory_bandwidth_gb_s": 0.27,
            },
            "gpu_cupy": {
                "throughput_galaxies_per_sec": 250000.0,
                "compute_gflops": 74.0,
                "memory_bandwidth_gb_s": 1.18,
                "speedup_vs_cpu": 4.38,
            },
        },
    }

    def mock_run_command(cmd, check=True):
        cmd_str = " ".join(cmd)
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stderr = ""

        if "git rev-parse HEAD" in cmd_str:
            mock_proc.stdout = "fedcba9876543210"
        elif "kaggle kernels push" in cmd_str:
            mock_proc.stdout = "Kernel version 1 successfully pushed."
        elif "kaggle kernels status" in cmd_str:
            mock_proc.stdout = '"specsynth-gpu-benchmark" has status "complete"'
        elif "kaggle kernels output" in cmd_str:
            # Simulate kaggle output download into directory -p
            dest_dir = Path(cmd[cmd.index("-p") + 1])
            dest_dir.mkdir(parents=True, exist_ok=True)
            (dest_dir / "gpu_manifest.json").write_text(json.dumps(sample_manifest), encoding="utf-8")
            mock_proc.stdout = f"Downloaded output to {dest_dir}"
        else:
            mock_proc.stdout = "ok"

        return mock_proc

    monkeypatch.setattr(rkg, "run_command", mock_run_command)
    monkeypatch.setattr(rkg.shutil, "which", lambda cmd: "/usr/local/bin/kaggle")
    monkeypatch.setattr(rkg, "get_kaggle_credentials", lambda: ("mock_user", "mock_key"))

    test_argv = [
        "run_kaggle_gpu.py",
        "--username",
        "mock_user",
        "--output",
        str(out_manifest),
        "--commit-sha",
        "testsha123",
    ]
    monkeypatch.setattr(sys, "argv", test_argv)

    ret = rkg.main()
    assert ret == 0

    assert out_manifest.exists()
    saved = json.loads(out_manifest.read_text(encoding="utf-8"))
    assert saved["system"]["gpu_device_name"] == "Tesla T4"
    assert saved["category_2_single_node"]["gpu_cupy"]["speedup_vs_cpu"] == 4.38

    assert step_summary.exists()
    summary_text = step_summary.read_text(encoding="utf-8")
    assert "Kaggle Tesla T4 GPU Benchmark Results" in summary_text
    assert "4.38x" in summary_text
    assert "Tesla T4" in summary_text
