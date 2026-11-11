#!/usr/bin/env python3
"""
Clean up test caches, temporary Zarr data stores, and build artifacts.
Usage:
    python scripts/clean.py
    python scripts/clean.py --all
"""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

# Directories to purge
CACHE_DIRS = [
    ".pytest_cache",
    ".benchmarks",
    "__pycache__",
    ".coverage",
    "htmlcov",
]

TEMP_DATA_DIRS = [
    "test_run",
    "run",
    "run_demo",
    "test_zarr.zarr",
    "test_batch.zarr",
    "test_client.zarr",
    "test_append.zarr",
    "test_store.zarr",
]

BUILD_DIRS = [
    "build",
    "dist",
    ".eggs",
]

TEMP_FILES = [
    "benchmark_report.json",
    ".coverage",
]


def clean_project(include_build: bool = False, verbose: bool = True) -> int:
    root = Path(__file__).resolve().parent.parent
    removed_count = 0

    if verbose:
        print(f"[*] Cleaning specsynth workspace at: {root}")

    # 1. Remove cache directories and any nested __pycache__
    for cache_name in CACHE_DIRS:
        target = root / cache_name
        if target.exists():
            if target.is_dir():
                shutil.rmtree(target, ignore_errors=True)
            else:
                target.unlink(missing_ok=True)
            removed_count += 1
            if verbose:
                print(f"  [-] Removed {cache_name}")

    for p in root.rglob("__pycache__"):
        if ".venv" not in p.parts:
            shutil.rmtree(p, ignore_errors=True)
            removed_count += 1

    for p in root.rglob("*.py[cod]"):
        if ".venv" not in p.parts:
            p.unlink(missing_ok=True)
            removed_count += 1

    # 2. Remove temporary Zarr test stores & mock runs
    for temp_dir in TEMP_DATA_DIRS:
        target = root / temp_dir
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
            removed_count += 1
            if verbose:
                print(f"  [-] Removed temporary store: {temp_dir}")

    # Remove any *.zarr directories in root
    for p in root.glob("*.zarr"):
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
            removed_count += 1
            if verbose:
                print(f"  [-] Removed temporary store: {p.name}")

    # 3. Remove temporary files
    for temp_file in TEMP_FILES:
        target = root / temp_file
        if target.exists():
            target.unlink(missing_ok=True)
            removed_count += 1
            if verbose:
                print(f"  [-] Removed {temp_file}")

    # 4. Optional: Remove build and egg-info
    if include_build:
        for b_dir in BUILD_DIRS:
            target = root / b_dir
            if target.exists():
                shutil.rmtree(target, ignore_errors=True)
                removed_count += 1
                if verbose:
                    print(f"  [-] Removed {b_dir}")

        for egg in root.glob("*.egg-info"):
            shutil.rmtree(egg, ignore_errors=True)
            removed_count += 1
            if verbose:
                print(f"  [-] Removed {egg.name}")

    if verbose:
        print(f"[+] Workspace cleaned successfully ({removed_count} items purged).\n")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean temporary test caches and data stores")
    parser.add_argument("--all", action="store_true", help="Also clean build and distribution artifacts")
    args = parser.parse_args()
    clean_project(include_build=args.all)
