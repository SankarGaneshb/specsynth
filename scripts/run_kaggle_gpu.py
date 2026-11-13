#!/usr/bin/env python3
"""
Automated Kaggle Tesla T4 GPU Benchmark Orchestrator for specsynth.

Dispatches an on-demand GPU benchmark kernel to Kaggle, monitors execution,
and retrieves the verified benchmark manifest (gpu_manifest.json).
Works seamlessly in GitHub Actions and local developer environments.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def get_kaggle_credentials() -> tuple[str | None, str | None]:
    """Retrieve Kaggle credentials from environment, ~/.kaggle/access_token, or ~/.kaggle/kaggle.json."""
    user = os.environ.get("KAGGLE_USERNAME")
    key = os.environ.get("KAGGLE_KEY") or os.environ.get("KAGGLE_API_TOKEN")

    acc_file = Path.home() / ".kaggle" / "access_token"
    if not key and acc_file.exists():
        try:
            key = acc_file.read_text(encoding="utf-8").strip()
        except Exception:
            pass

    cfg_file = Path.home() / ".kaggle" / "kaggle.json"
    if cfg_file.exists():
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                u = data.get("username")
                k = data.get("key") or data.get("api_token")
                if not user and u:
                    user = u
                if not key and k:
                    key = k
        except Exception:
            pass

    return user, key


def generate_worker_script(n_gal: int, n_runs: int) -> str:
    """Generate the self-contained benchmark worker script to run on Kaggle."""
    return f'''#!/usr/bin/env python3
import os
import subprocess
import sys

print("=" * 60)
print("[*] SPECSYNTH KAGGLE TESLA T4 GPU BENCHMARK WORKER")
print("=" * 60)

# Step 1: Ensure cupy matching Kaggle CUDA 13.0 environment
print("\\n[*] Step 1: Aligning CuPy with CUDA 13.0 driver...")
subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", "cupy-cuda12x", "cupy-cuda13x"], check=False)
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "cupy-cuda13x"], check=True)

# Step 2: Install latest specsynth directly from GitHub
print("\\n[*] Step 2: Installing specsynth from GitHub (main)...")
subprocess.run([
    sys.executable, "-m", "pip", "install", "--upgrade", "--no-cache-dir", "-q",
    "git+https://github.com/SankarGaneshb/specsynth.git", "matplotlib"
], check=True)

# Step 3: Verify GPU diagnostics
print("\\n[*] Step 3: Checking GPU Diagnostics...")
try:
    from specsynth.gpu import get_device_info, is_gpu_available
    print(f"  GPU Available: {{is_gpu_available()}}")
    info = get_device_info()
    print(f"  Device Details: {{info}}")
except Exception as e:
    print(f"  Warning during diagnostics probe: {{e}}")

# Step 4: Run specsynth benchmark suite
print("\\n[*] Step 4: Running Standardized GPU Benchmark Suite ({n_gal} galaxies, {n_runs} runs)...")
cmd = [
    "specsynth", "benchmark",
    "--n-gal", "{n_gal}",
    "--n-runs", "{n_runs}",
    "--gpu",
    "--output", "gpu_manifest.json"
]
subprocess.run(cmd, check=True)

print("\\n[*] Step 5: Validating Output Manifest...")
if os.path.exists("gpu_manifest.json"):
    print(f"  [+] gpu_manifest.json generated successfully ({{os.path.getsize('gpu_manifest.json')}} bytes).")
    with open("gpu_manifest.json") as f:
        print("\\n--- MANIFEST PREVIEW ---")
        print(f.read())
        print("------------------------")
else:
    print("  [!] ERROR: gpu_manifest.json was not created!")
    sys.exit(1)

print("\\n[+] Benchmark worker completed successfully.")
'''


def run_command(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a subprocess command and return the completed process."""
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def main() -> int:
    parser = argparse.ArgumentParser(description="Orchestrate Kaggle GPU benchmark for specsynth")
    parser.add_argument("--username", help="Kaggle username")
    parser.add_argument("--kernel-slug", default="specsynth-gpu-benchmark", help="Kernel slug identifier")
    parser.add_argument("--n-gal", type=int, default=50000, help="Number of galaxies (default: 50,000)")
    parser.add_argument("--n-runs", type=int, default=5, help="Number of benchmark runs (default: 5)")
    parser.add_argument("--output", default="paper/benchmark_manifest_gpu_t4.json", help="Destination manifest path")
    parser.add_argument("--timeout", type=int, default=900, help="Timeout in seconds (default: 900s / 15m)")
    parser.add_argument("--public", action="store_true", help="Make the Kaggle notebook publicly visible on Kaggle")
    args = parser.parse_args()

    # Self-healing: ensure 'six' is installed (known Kaggle CLI packaging bug)
    try:
        import six
    except ImportError:
        try:
            print("[*] Installing missing 'six' dependency for Kaggle CLI...")
            subprocess.run([sys.executable, "-m", "pip", "install", "-q", "six"], check=False)
        except Exception:
            pass

    # Verify Kaggle CLI is installed
    if not shutil.which("kaggle"):
        print("[!] Error: 'kaggle' CLI is not installed or not in PATH.", file=sys.stderr)
        print("    Install it via: pip install kaggle", file=sys.stderr)
        return 1

    username = (args.username or "").strip()
    user_env, key_env = get_kaggle_credentials()
    if not username:
        username = (user_env or "").strip()

    if not username:
        print("[!] Error: Kaggle username could not be resolved.", file=sys.stderr)
        print("    Please ensure KAGGLE_USERNAME is configured in GitHub Secrets -> Repository Secrets (not Environment Secrets).", file=sys.stderr)
        print("    If running locally, pass --username <your_kaggle_username> or set KAGGLE_USERNAME in your environment.", file=sys.stderr)
        return 1

    # Synchronize authentication token for both modern and legacy Kaggle CLI
    if key_env:
        key_clean = key_env.strip()
        os.environ["KAGGLE_KEY"] = key_clean
        os.environ["KAGGLE_API_TOKEN"] = key_clean
        try:
            acc_file = Path.home() / ".kaggle" / "access_token"
            acc_file.parent.mkdir(parents=True, exist_ok=True)
            acc_file.write_text(key_clean, encoding="utf-8")
        except Exception:
            pass
        try:
            cfg_file = Path.home() / ".kaggle" / "kaggle.json"
            cfg_file.parent.mkdir(parents=True, exist_ok=True)
            cfg_file.write_text(json.dumps({"username": username, "key": key_clean}), encoding="utf-8")
        except Exception:
            pass

    kernel_id = f"{username}/{args.kernel_slug}"
    print(f"[*] Target Kaggle Kernel ID: {kernel_id}")
    print(f"[*] Benchmark parameters: {args.n_gal:,} galaxies, {args.n_runs} runs, GPU enabled")

    # Prepare staging directory
    staging_dir = Path(tempfile.mkdtemp(prefix="specsynth_kaggle_"))
    try:
        # Write worker script
        worker_file = staging_dir / "benchmark_worker.py"
        worker_file.write_text(generate_worker_script(args.n_gal, args.n_runs), encoding="utf-8")

        # Write kernel metadata
        metadata = {
            "id": kernel_id,
            "title": args.kernel_slug.replace("-", " ").title(),
            "code_file": "benchmark_worker.py",
            "language": "python",
            "kernel_type": "script",
            "is_private": "false" if args.public else "true",
            "enable_gpu": "true",
            "enable_internet": "true",
        }
        meta_file = staging_dir / "kernel-metadata.json"
        meta_file.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        print(f"[*] Staged kernel files in: {staging_dir}")

        # Push kernel to Kaggle
        print(f"[*] Pushing kernel to Kaggle ({kernel_id})...")
        push_res = run_command(["kaggle", "kernels", "push", "-p", str(staging_dir)], check=False)
        if push_res.returncode != 0:
            print(f"[!] Kaggle push failed:\n{push_res.stderr}\n{push_res.stdout}", file=sys.stderr)
            return 1
        print(f"    {push_res.stdout.strip()}")

        # Polling status
        print("[*] Monitoring execution status on Kaggle...")
        start_time = time.time()
        completed = False

        while time.time() - start_time < args.timeout:
            status_res = run_command(["kaggle", "kernels", "status", kernel_id], check=False)
            status_text = status_res.stdout.strip()
            print(f"    [{int(time.time() - start_time):03d}s] {status_text}")

            status_lower = status_text.lower()
            if "complete" in status_lower:
                completed = True
                break
            elif "error" in status_lower or "failed" in status_lower:
                print(f"\n[!] Kaggle kernel execution failed with status: {status_text}", file=sys.stderr)
                break

            time.sleep(15)

        if not completed:
            print(f"\n[!] Execution did not complete successfully within {args.timeout}s.", file=sys.stderr)
            # Retrieve output to show failure log
            out_fail_dir = staging_dir / "failed_output"
            out_fail_dir.mkdir(exist_ok=True)
            run_command(["kaggle", "kernels", "output", kernel_id, "-p", str(out_fail_dir)], check=False)
            for f in out_fail_dir.glob("*"):
                if f.is_file():
                    print(f"\n--- Artifact: {f.name} ---")
                    try:
                        print(f.read_text(encoding="utf-8", errors="replace")[:2000])
                    except Exception:
                        pass
            return 1

        # Fetch output artifacts
        print(f"\n[*] Fetching generated artifacts from Kaggle...")
        out_dir = staging_dir / "output"
        out_dir.mkdir(exist_ok=True)
        fetch_res = run_command(["kaggle", "kernels", "output", kernel_id, "-p", str(out_dir)], check=False)
        if fetch_res.returncode != 0:
            print(f"[!] Failed to fetch kernel output:\n{fetch_res.stderr}", file=sys.stderr)
            return 1

        manifest_source = out_dir / "gpu_manifest.json"
        if not manifest_source.exists():
            print(f"[!] gpu_manifest.json was not found in kernel output artifacts.", file=sys.stderr)
            for p in out_dir.glob("*"):
                print(f"    Found file: {p.name}")
            return 1

        # Save to output path
        dest_path = Path(args.output).resolve()
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(manifest_source, dest_path)
        print(f"[+] Successfully copied GPU manifest to: {dest_path}")

        # Parse and print summary
        with open(dest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        sys_info = manifest.get("system", {})
        s_node = manifest.get("category_2_single_node", {})
        cpu = s_node.get("cpu_blas", {})
        gpu = s_node.get("gpu_cupy", {})

        print("\n" + "=" * 60)
        print("          SPECSYNTH GPU BENCHMARK RESULTS")
        print("=" * 60)
        print(f"  GPU Hardware:       {sys_info.get('gpu_device_name', 'N/A')}")
        print(f"  CPU Backend:        {sys_info.get('blas_backend', 'N/A')} ({sys_info.get('cpu_processor', 'CPU')})")
        print(f"  Workload:           {manifest.get('workload', {}).get('n_galaxies', 0):,} galaxies")
        print(f"  CPU Throughput:     {cpu.get('throughput_galaxies_per_sec', 0):,.1f} gal/s ({cpu.get('compute_gflops', 0):.2f} GFLOPS)")
        print(f"  GPU Throughput:     {gpu.get('throughput_galaxies_per_sec', 0):,.1f} gal/s ({gpu.get('compute_gflops', 0):.2f} GFLOPS)")
        print(f"  Measured Speedup:   {gpu.get('speedup_vs_cpu', 0):.2f}x")
        print(f"  Kaggle Web URL:     https://www.kaggle.com/code/{kernel_id}")
        print("=" * 60)

        # Write to GITHUB_STEP_SUMMARY if running in GitHub Actions
        step_summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
        if step_summary_path:
            with open(step_summary_path, "a", encoding="utf-8") as gf:
                gf.write("## 🚀 Kaggle Tesla T4 GPU Benchmark Results\n\n")
                gf.write(f"- **Device**: `{sys_info.get('gpu_device_name', 'N/A')}`\n")
                gf.write(f"- **Workload**: `{manifest.get('workload', {}).get('n_galaxies', 0):,}` galaxies\n")
                gf.write(f"- **Correctness**: `{manifest.get('category_1_correctness', {}).get('status', 'N/A')}` (Max Rel Error: `{manifest.get('category_1_correctness', {}).get('max_relative_error', 'N/A')}`)\n\n")
                gf.write("| Backend | Throughput (gal/s) | Compute (GFLOPS) | Memory Bandwidth (GB/s) | Speedup |\n")
                gf.write("| :--- | :---: | :---: | :---: | :---: |\n")
                gf.write(f"| **CPU BLAS** | {cpu.get('throughput_galaxies_per_sec', 0):,.1f} | {cpu.get('compute_gflops', 0):.2f} | {cpu.get('memory_bandwidth_gb_s', 0):.2f} | 1.00x |\n")
                gf.write(f"| **GPU (CuPy / cuBLAS)** | **{gpu.get('throughput_galaxies_per_sec', 0):,.1f}** | **{gpu.get('compute_gflops', 0):.2f}** | **{gpu.get('memory_bandwidth_gb_s', 0):.2f}** | **{gpu.get('speedup_vs_cpu', 0):.2f}x** |\n\n")

        return 0

    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
