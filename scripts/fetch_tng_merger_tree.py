#!/usr/bin/env python3
"""
scripts.fetch_tng_merger_tree
==============================
Traceable IllustrisTNG SubLink merger tree fetcher, parser, and provenance verifier.
Addresses GitHub Issue #27: [MUST][P3] Real merger-tree lineage and physically validated galaxy evolution.

Capabilities:
  1. Download: Fetches genuine SubLink merger tree MPB from the IllustrisTNG API:
     https://www.tng-project.org/api/TNG100-1/snapshots/{snap}/subhalos/{subhalo_id}/sublink/mpb.json
  2. Verify: Validates node linkage, monotonic redshift ordering, physical mass balance,
     and SHA-256 checksums fail-closed.
  3. Export: Updates perandam-psi/src/data/evolution_tracks.json with segregated data_modes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional
import urllib.request
import urllib.error

# Auto-re-exec into local .venv if run with system python
if sys.prefix == getattr(sys, "base_prefix", sys.prefix):
    repo_root = Path(__file__).resolve().parent.parent
    venv_python_win = repo_root / ".venv" / "Scripts" / "python.exe"
    venv_python_posix = repo_root / ".venv" / "bin" / "python"
    venv_py = venv_python_win if venv_python_win.exists() else venv_python_posix

    if venv_py.exists() and str(venv_py) != sys.executable:
        os.execv(str(venv_py), [str(venv_py)] + sys.argv)

repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from specsynth.contracts.evolution import (
    EvolutionaryTrackContract,
    MergerEvent,
    ProgenitorNode,
)
from specsynth.cosmology import TNG_COSMOLOGY
from specsynth.evolution import (
    TNG_SNAPSHOT_TABLE,
    build_tng_sublink_track,
    diagnose_merger_mass_accounting,
    generate_highz_starburst_evolution_track,
    generate_reference_tng_evolution_track,
    load_sublink_merger_tree,
)

DEFAULT_SUBHALO_ID = 424601
DEFAULT_SNAPSHOT = 99
DEFAULT_SIMULATION = "IllustrisTNG-100-1"
DEFAULT_TREE_PATH = repo_root / "sample_models" / "evolution" / "tng100_subhalo_424601_sublink_tree.json"
DEFAULT_MANIFEST_PATH = repo_root / "sample_models" / "evolution" / "tng100_subhalo_424601_sublink_manifest.json"
DEFAULT_PERANDAM_PATH = repo_root / "perandam-psi" / "src" / "data" / "evolution_tracks.json"


def compute_sha256(filepath: Path) -> str:
    """Compute cross-platform canonical SHA-256 (normalizing CRLF to LF for JSON)."""
    with open(filepath, "rb") as f:
        content = f.read()
    if filepath.suffix.lower() in (".json", ".txt", ".csv", ".md"):
        content = content.replace(b"\r\n", b"\n")
    return hashlib.sha256(content).hexdigest()


def verify_merger_tree_provenance(
    tree_path: Path = DEFAULT_TREE_PATH,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
) -> bool:
    """
    Cryptographically verify the SubLink merger tree and manifest.
    Fails closed on any hash mismatch, broken tree linkage, or unphysical mass residual.
    """
    print("=" * 80)
    print("  IllustrisTNG SubLink Merger Tree Provenance Verifier (Issue #27)")
    print("=" * 80)

    if not tree_path.exists():
        print(f"[FAIL] SubLink tree file missing: {tree_path}")
        return False
    if not manifest_path.exists():
        print(f"[FAIL] Manifest file missing: {manifest_path}")
        return False

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # 1. SHA-256 checksum verification
    actual_sha256 = compute_sha256(tree_path)
    expected_sha256 = manifest.get("checksums", {}).get("tree_json_sha256", "")
    print(f"[*] SubLink Tree SHA-256: {actual_sha256}")
    if actual_sha256 != expected_sha256:
        print(f"[FAIL] SHA-256 mismatch!\n  Expected: {expected_sha256}\n  Actual:   {actual_sha256}")
        return False
    print("  [PASS] Cryptographic SHA-256 checksum matches manifest exactly.")

    # 2. Ingest track and validate contract invariants
    try:
        track = load_sublink_merger_tree(tree_path, subhalo_id=DEFAULT_SUBHALO_ID)
    except Exception as e:
        print(f"[FAIL] Failed to load SubLink merger tree: {e}")
        return False

    # 3. Check data_mode truth-in-labeling
    if track.data_mode != "simulation_derived":
        print(f"[FAIL] Expected data_mode 'simulation_derived', got '{track.data_mode}'")
        return False
    print(f"  [PASS] data_mode is '{track.data_mode}' (Truth-in-labeling verified).")

    # 4. Check snapshot count and redshift bounds
    n_nodes = len(track.main_branch)
    if n_nodes < 5:
        print(f"[FAIL] Insufficient snapshots in main branch: {n_nodes} < 5")
        return False
    z_min = track.main_branch[0].redshift
    z_max = track.main_branch[-1].redshift
    print(f"  [PASS] Main Progenitor Branch: {n_nodes} snapshots spanning z = {z_min:.2f} to {z_max:.2f}.")

    # 5. Tree connectivity verification
    try:
        track.validate_tree_connectivity()
        print("  [PASS] Tree connectivity verified: parent-child links connected without dangling references.")
    except Exception as e:
        print(f"[FAIL] Tree connectivity check failed: {e}")
        return False

    # 6. Merger mass accounting verification
    try:
        results = track.validate_mass_accounting(tolerance_fraction=0.35)
        print(f"  [PASS] Mass accounting verified across {len(results)} merger events (tolerance <= 35%).")
        for res in results:
            print(f"         - Snap {res['snapshot_id']}: mass_ratio={res['mass_ratio']}, residual={res['residual_fraction']:.2%}")
    except Exception as e:
        print(f"[FAIL] Mass accounting validation failed: {e}")
        return False

    # 7. Cosmology consistency check
    cosmo = TNG_COSMOLOGY
    for node in track.main_branch:
        expected_time = cosmo.cosmic_time_gyr(node.redshift)
        rel_diff = abs(node.cosmic_time_gyr - expected_time) / expected_time
        if rel_diff > 1e-2:
            print(f"[FAIL] Cosmic time mismatch at z={node.redshift}: node={node.cosmic_time_gyr}, cosmo={expected_time}")
            return False
    print("  [PASS] Cosmological time consistency verified against TNG FlatLambdaCDM.")

    print("-" * 80)
    print("  [SUCCESS] All Issue #27 SubLink Merger Tree Provenance Criteria Met.")
    print("=" * 80)
    return True


def export_perandam_evolution_tracks(
    output_path: Path = DEFAULT_PERANDAM_PATH,
    tree_path: Path = DEFAULT_TREE_PATH,
) -> None:
    """Export segregated evolutionary tracks to perandam-psi/src/data/evolution_tracks.json."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    sublink_track = load_sublink_merger_tree(tree_path, subhalo_id=DEFAULT_SUBHALO_ID)
    demo_disk = generate_reference_tng_evolution_track("TNG-DISC-01")
    demo_anom = generate_highz_starburst_evolution_track("TNG-ANOM-01")

    payload = {
        "version": "1.0.0",
        "description": "Multi-epoch evolutionary tracks for Perandam PSI Cosmic Time Stage",
        "tracks": {
            "TNG-SUBLINK-424601": sublink_track.to_dict(),
            "TNG-DISC-01": demo_disk.to_dict(),
            "TNG-ANOM-01": demo_anom.to_dict(),
        },
    }

    with open(output_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, indent=2)

    print(f"[OK] Exported {len(payload['tracks'])} tracks to {output_path}")


def download_sublink_tree(
    api_key: str,
    subhalo_id: int = DEFAULT_SUBHALO_ID,
    snapshot: int = DEFAULT_SNAPSHOT,
    output_path: Path = DEFAULT_TREE_PATH,
) -> bool:
    """Download live SubLink merger tree from IllustrisTNG API using user key."""
    if not api_key:
        print("[FAIL] Missing TNG API key. Live download requires '--api-key YOUR_KEY' or $env:TNG_API_KEY.")
        return False

    url = f"https://www.tng-project.org/api/TNG100-1/snapshots/{snapshot}/subhalos/{subhalo_id}/sublink/mpb.json"
    headers = {"api-key": api_key, "User-Agent": "specsynth-merger-tree-fetcher/1.0"}
    req = urllib.request.Request(url, headers=headers)

    print(f"[*] Requesting live SubLink tree from: {url}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        with open(output_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, indent=2)
        print(f"[OK] Successfully downloaded live SubLink tree to {output_path}")
        return True
    except urllib.error.HTTPError as e:
        print(f"[FAIL] TNG API HTTP Error {e.code}: {e.reason}")
        return False
    except Exception as e:
        print(f"[FAIL] Network or parse error: {e}")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="IllustrisTNG SubLink Merger Tree Fetcher & Verifier")
    parser.add_argument("--verify", action="store_true", help="Cryptographically verify SubLink tree and manifest")
    parser.add_argument("--export-tracks", action="store_true", help="Export segregated tracks to perandam-psi")
    parser.add_argument("--download", action="store_true", help="Download live SubLink tree from TNG API")
    parser.add_argument("--api-key", default=os.environ.get("TNG_API_KEY", ""), help="IllustrisTNG API Key")
    parser.add_argument("--subhalo-id", type=int, default=DEFAULT_SUBHALO_ID, help="Subhalo ID (default: 424601)")
    parser.add_argument("--snapshot", type=int, default=DEFAULT_SNAPSHOT, help="Snapshot number (default: 99)")

    args = parser.parse_args()

    if args.download:
        ok = download_sublink_tree(api_key=args.api_key, subhalo_id=args.subhalo_id, snapshot=args.snapshot)
        if not ok:
            sys.exit(1)

    if args.export_tracks:
        export_perandam_evolution_tracks()

    if args.verify or (not args.download and not args.export_tracks):
        ok = verify_merger_tree_provenance()
        if not ok:
            sys.exit(1)


if __name__ == "__main__":
    main()
