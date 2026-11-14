#!/usr/bin/env python3
"""
Upload the specsynth Canonical Reference Benchmark Dataset to Hugging Face Hub.

Usage:
    python scripts/upload_to_huggingface.py --repo-id sreeganesh/specsynth-benchmark-100k [--token YOUR_HF_TOKEN]
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Upload specsynth benchmark catalog to Hugging Face Hub")
    parser.add_argument(
        "--repo-id",
        type=str,
        default="sreeganesh/specsynth-benchmark-100k",
        help="Target Hugging Face dataset repository identifier (username/dataset-name)",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="benchmark_data/specsynth_reference_100k",
        help="Path to generated reference benchmark directory",
    )
    parser.add_argument(
        "--token",
        type=str,
        default=None,
        help="Hugging Face User Access Token with write permissions (or set HF_TOKEN env var)",
    )
    parser.add_argument(
        "--private",
        action="store_true",
        help="Make the dataset private on Hugging Face (default: public)",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    parquet_file = data_dir / "specsynth_benchmark_100k.parquet"
    readme_file = data_dir / "README.md"
    card_file = data_dir / "dataset_card.json"
    sums_file = data_dir / "SHA256SUMS.txt"

    if not parquet_file.is_file():
        print(f"[!] ERROR: Parquet reference file not found at {parquet_file}.")
        print("    Run 'python scripts/export_reference_dataset.py' first to generate the dataset.")
        sys.exit(1)

    token = args.token or os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")

    try:
        from huggingface_hub import HfApi, create_repo
    except ImportError:
        print("[*] Installing 'huggingface_hub'...")
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "huggingface_hub"], check=True)
        from huggingface_hub import HfApi, create_repo

    api = HfApi(token=token)

    print("=" * 70)
    print("SPECSYNTH HUGGING FACE DATASET UPLOADER")
    print(f"Target Repository: https://huggingface.co/datasets/{args.repo_id}")
    print(f"Data Directory:    {data_dir}")
    print("=" * 70)

    # Verify identity and token capabilities
    if token:
        try:
            user_info = api.whoami(token=token)
            username = user_info.get("name") or user_info.get("username", "unknown")
            print(f"[*] Authenticated as Hugging Face user: '{username}'")
            auth_info = user_info.get("auth", {})
            token_role = auth_info.get("accessToken", {}).get("role", "unknown")
            print(f"[*] Token Role/Scope: '{token_role}'")
            if str(token_role).lower() == "read":
                print("[!] CRITICAL: Token has 'read' permission only!")
                print("    Creating datasets and uploading files requires a token with 'write' permissions.")
                print("    Generate a new 'Write' token at: https://huggingface.co/settings/tokens")
        except Exception as e:
            print(f"[*] Token verification note: {e}")
    else:
        print("[!] WARNING: No HF_TOKEN supplied. Upload operations will require write credentials.")

    print("\n[*] Step 1: Creating or verifying Hugging Face dataset repository...")
    repo_ready = False
    try:
        create_repo(
            repo_id=args.repo_id,
            repo_type="dataset",
            private=args.private,
            token=token,
            exist_ok=True,
        )
        repo_ready = True
        print(f"  [+] Repository verified / ready: {args.repo_id}")
    except Exception as e:
        # Check if the repository already exists (in case user created it manually or token lacks repo-creation but has write)
        try:
            api.repo_info(repo_id=args.repo_id, repo_type="dataset", token=token)
            repo_ready = True
            print(f"  [+] Repository already exists on Hub: {args.repo_id}")
        except Exception:
            pass

        if not repo_ready:
            print("\n" + "!" * 70)
            print(f"[!] ERROR: Cannot create or access repository '{args.repo_id}':")
            print(f"    {e}\n")
            print("    Root Cause & Fix:")
            print("    1. Token Permission: The Hugging Face token must have 'Write' role.")
            print("       - Visit: https://huggingface.co/settings/tokens")
            print("       - Click 'Create new token' -> select Type: 'Write'")
            print("       - Copy the token ('hf_...')")
            print("    2. Update GitHub Secret:")
            print("       - Go to: https://github.com/SankarGaneshb/specsynth/settings/secrets/actions")
            print("       - Update 'HF_TOKEN' with the new Write token")
            print("!" * 70 + "\n")
            sys.exit(1)

    print("\n[*] Step 2: Uploading benchmark files to Hugging Face...")
    files_to_upload = [
        (parquet_file, "specsynth_benchmark_100k.parquet"),
        (readme_file, "README.md"),
        (card_file, "dataset_card.json"),
        (sums_file, "SHA256SUMS.txt"),
    ]

    for local_path, repo_path in files_to_upload:
        if local_path.is_file():
            size_mb = local_path.stat().st_size / (1024**2)
            print(f"  [*] Uploading {repo_path} ({size_mb:.2f} MB)...")
            try:
                api.upload_file(
                    path_or_fileobj=str(local_path),
                    path_in_repo=repo_path,
                    repo_id=args.repo_id,
                    repo_type="dataset",
                    token=token,
                )
                print(f"  [+] Uploaded {repo_path}")
            except Exception as e:
                print(f"[!] ERROR uploading {repo_path}: {e}")
                if "403" in str(e) or "Forbidden" in str(e):
                    print("    Hint: Your token appears to lack write access to this dataset.")
                    print("    Ensure your Hugging Face token was created with Role='Write' at https://huggingface.co/settings/tokens")
                raise

    print("\n" + "=" * 70)
    print(f"[+] SUCCESS! Dataset is now live on Hugging Face:")
    print(f"    👉 https://huggingface.co/datasets/{args.repo_id}")
    print("=" * 70)


if __name__ == "__main__":
    main()
