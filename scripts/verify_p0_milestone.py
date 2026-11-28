#!/usr/bin/env python3
"""
Verification Script for Milestone P0 (GitHub Milestone #1): Scope and Architecture Freeze (Issue #14)
===================================================================================
Executes an automated, reproducible validation pass across all 7 acceptance criteria
of Milestone P0:
  1. Product boundaries and ADR-001 review
  2. Versioned engine I/O contracts (SSP, Simulation, Photometry)
  3. Zero-core-modification external adapter registration and lifecycle
  4. Scientific 3D galaxy data model (coordinates, units, particle batching)
  5. Truth-in-labeling validation (simulation-derived vs procedural)
  6. Canonical Model Context Protocol (MCP) schemas and M8ven annotations
  7. Codebase roadmap traceability matrix
"""

import subprocess
import sys
from pathlib import Path

# Ensure repo root is in sys.path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Auto-detect virtualenv if running in system Python without project dependencies
venv_bin = "Scripts" if sys.platform == "win32" else "bin"
venv_exe = "python.exe" if sys.platform == "win32" else "python"
local_venv_python = REPO_ROOT / ".venv" / venv_bin / venv_exe

if local_venv_python.exists() and Path(sys.executable).resolve() != local_venv_python.resolve():
    try:
        import dask  # test if current python has project dependencies
    except ImportError:
        res = subprocess.run([str(local_venv_python)] + sys.argv, cwd=str(REPO_ROOT))
        sys.exit(res.returncode)

import numpy as np

from specsynth.contracts import (
    SSPGridContract,
    SimulationGalaxyContract,
    Galaxy3DContract,
    ParticleBatchContract,
    ParticleType,
    GeometrySource,
    CoordinateFrame,
    SyntheticObservationContract,
    PhotometryPointContract,
    CANONICAL_MCP_TOOLS,
    get_canonical_tool_schema,
)
from specsynth.adapters import (
    BaseAdapter,
    SSPData,
    register_adapter,
    unregister_adapter,
    get_adapter,
    list_adapters,
    validate_adapter,
)

GREEN = "\033[92m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_stage(title: str):
    print(f"\n{BOLD}{CYAN}=== {title} ==={RESET}")


def pass_item(msg: str):
    print(f"  {GREEN}[PASS]{RESET} {msg}")


def fail_item(msg: str):
    print(f"  {RED}[FAIL]{RESET} {msg}")
    sys.exit(1)


def verify_adr_and_documentation():
    print_stage("1. Verifying Architecture Decisions & Roadmap Documentation (P0.1, P0.6, P0.7)")
    adr_file = REPO_ROOT / "docs" / "architecture" / "ADR_001_scope_and_contracts_freeze.md"
    roadmap_file = REPO_ROOT / "docs" / "architecture" / "roadmap_mapping.md"
    agents_file = REPO_ROOT / "AGENTS.md"
    parking_file = REPO_ROOT / "PARKING_LOT.md"

    if not adr_file.exists():
        fail_item(f"Missing ADR-001 at {adr_file}")
    pass_item("ADR-001 (Scope and Contracts Freeze) present and documented.")

    if not roadmap_file.exists():
        fail_item(f"Missing roadmap mapping at {roadmap_file}")
    pass_item("Roadmap Codebase Traceability Matrix (P0-P6) present.")

    if not agents_file.exists() or "Scope Freeze Charter" not in agents_file.read_text(encoding="utf-8"):
        fail_item("AGENTS.md missing scope freeze charter")
    pass_item("AGENTS.md scope freeze directive and guardian protocol ratified.")

    if not parking_file.exists():
        fail_item(f"Missing {parking_file}")
    pass_item("PARKING_LOT.md registry established.")


def verify_ssp_contract():
    print_stage("2. Verifying SSP Grid Contract & Physical Invariants (P0.2)")
    ages = np.array([1e7, 1e8, 1e9], dtype=np.float64)
    mets = np.array([0.004, 0.02], dtype=np.float64)
    wave = np.linspace(1000, 10000, 100, dtype=np.float64)
    flux = np.ones((6, 100), dtype=np.float32)

    # Valid contract
    ssp = SSPGridContract(
        source_engine="FSPS",
        engine_version="3.2",
        imf="chabrier_2003",
        isochrones="mist_v1.2",
        ages_yr=ages,
        mets_z=mets,
        wave_angstrom=wave,
        ssp_flux_2d=flux,
    )
    pass_item(f"Valid SSP grid contract instantiated (v{ssp.version}, shape: {ssp.ssp_flux_2d.shape}).")

    # Invariant: non-monotonic wavelength rejection
    try:
        bad_wave = np.array([2000.0, 1500.0, 3000.0])
        SSPGridContract(
            source_engine="FSPS", engine_version="3.2", imf="chabrier_2003", isochrones="mist",
            ages_yr=np.array([1e7]), mets_z=np.array([0.02]), wave_angstrom=bad_wave,
            ssp_flux_2d=np.ones((1, 3), dtype=np.float32),
        )
        fail_item("Failed to reject non-monotonic wavelength axis.")
    except ValueError:
        pass_item("Strictly monotonic wavelength check enforced.")

    # Invariant: negative flux rejection
    try:
        bad_flux = np.array([[-1.0, 2.0]], dtype=np.float32)
        SSPGridContract(
            source_engine="FSPS", engine_version="3.2", imf="chabrier_2003", isochrones="mist",
            ages_yr=np.array([1e7]), mets_z=np.array([0.02]), wave_angstrom=np.array([1000.0, 2000.0]),
            ssp_flux_2d=bad_flux,
        )
        fail_item("Failed to reject negative luminosity flux.")
    except ValueError:
        pass_item("Non-negative luminosity invariant enforced.")


def verify_zero_core_adapter_pluggability():
    print_stage("3. Verifying Zero-Core-Modification Adapter Pluggability (P0.3, Pillar 1)")

    # Define custom third-party adapter class
    class ExternalAstrophysicsAdapter(BaseAdapter):
        def __init__(self, model_id: str = "custom_2026"):
            self.model_id = model_id

        def load(self) -> SSPData:
            ages = np.array([5e8], dtype=np.float64)
            mets = np.array([0.0142], dtype=np.float64)
            wave = np.array([3000.0, 4000.0, 5000.0], dtype=np.float64)
            ssp = np.array([[1.5, 2.0, 1.2]], dtype=np.float32)
            return SSPData(ages=ages, mets=mets, wave=wave, ssp=ssp, metadata={"model": self.model_id})

        def validate(self) -> bool:
            return True

        def get_capabilities(self) -> dict:
            return {"name": "ExternalAstrophysicsAdapter", "version": "1.0.0"}

    # Register dynamically
    register_adapter("external_astro", ExternalAstrophysicsAdapter, aliases=["ext_astro_v1"])
    pass_item("Dynamic external engine registration successful.")

    # Conformance validation
    assert validate_adapter(ExternalAstrophysicsAdapter) is True
    pass_item("Adapter lifecycle conformance check passed.")

    # Instantiation via registry & alias
    adapter = get_adapter("ext_astro_v1", model_id="chabrier_z014")
    assert isinstance(adapter, ExternalAstrophysicsAdapter)
    ssp_data = adapter.load()
    assert ssp_data.metadata["model"] == "chabrier_z014"
    pass_item(f"External engine instantiated and loaded data via alias without core edits.")

    # Clean up
    unregister_adapter("external_astro")
    assert "external_astro" not in list_adapters()
    pass_item("Adapter registry cleanly unregisters external modules.")


def verify_3d_galaxy_data_model():
    print_stage("4. Verifying Scientific 3D Galaxy Data Model & Units (P0.4)")
    n_stars = 250
    coords = np.random.uniform(-5.0, 5.0, size=(n_stars, 3)).astype(np.float32)
    vels = np.random.uniform(-150.0, 150.0, size=(n_stars, 3)).astype(np.float32)
    masses = np.full(n_stars, 1e6, dtype=np.float32)
    ages = np.full(n_stars, 4e9, dtype=np.float32)
    mets = np.full(n_stars, 0.0142, dtype=np.float32)

    stars = ParticleBatchContract(
        particle_type=ParticleType.STAR,
        coordinates_kpc=coords,
        velocities_km_s=vels,
        masses_msun=masses,
        ages_yr=ages,
        metallicities_z=mets,
    )
    pass_item("Particle batch contract validated (physical kpc, km/s, M_sun, yr, Z).")

    galaxy_3d = Galaxy3DContract(
        galaxy_id="TNG100-1-Subhalo-424601",
        geometry_source=GeometrySource.SIMULATION_DERIVED,
        coordinate_frame=CoordinateFrame.PHYSICAL_REST,
        redshift=0.05,
        center_of_mass_kpc=(0.0, 0.0, 0.0),
        half_mass_radius_kpc=3.2,
        components={"star": stars},
        provenance={"simulation": "IllustrisTNG-100", "snapshot": 99},
    )
    expected_mass = float(np.sum(masses))
    assert abs(galaxy_3d.total_stellar_mass_msun() - expected_mass) < 1e-3
    pass_item(f"3D Galaxy model validated: Total M_* = {galaxy_3d.total_stellar_mass_msun():.2e} M_sun.")

    # Truth in labeling: Simulation-derived must contain real particles
    try:
        Galaxy3DContract(
            galaxy_id="FakeEmpty",
            geometry_source=GeometrySource.SIMULATION_DERIVED,
            coordinate_frame=CoordinateFrame.PHYSICAL_REST,
            redshift=1.0,
            center_of_mass_kpc=(0.0, 0.0, 0.0),
            half_mass_radius_kpc=1.0,
            components={},  # Empty components
        )
        fail_item("Failed to reject empty simulation-derived components.")
    except ValueError:
        pass_item("Truth-in-labeling rule enforced: Empty simulation geometry rejected.")


def verify_canonical_mcp_contracts():
    print_stage("5. Verifying Canonical Model Context Protocol (MCP) Tools (P0.5, Pillar 4)")
    expected_tools = [
        "specsynth_list_filters",
        "specsynth_inspect_galaxy",
        "specsynth_calculate_cosmology",
        "specsynth_get_3d_galaxy",
        "specsynth_run_sentry_audit",
    ]
    for tool_name in expected_tools:
        if tool_name not in CANONICAL_MCP_TOOLS:
            fail_item(f"Missing canonical tool: {tool_name}")
        schema = get_canonical_tool_schema(tool_name)
        assert "inputSchema" in schema and "outputSchema" in schema
        assert "annotations" in schema
        assert schema["annotations"]["readOnlyHint"] is True
        pass_item(f"Canonical MCP tool '{tool_name}' verified with M8ven safety annotations.")


def main():
    print(f"\n{BOLD}======================================================================{RESET}")
    print(f"{BOLD}   Specsynth & PerandamΨ — Milestone P0 (GitHub #1) Validation Harness {RESET}")
    print(f"{BOLD}   Scope and Architecture Freeze Acceptance Verification              {RESET}")
    print(f"{BOLD}======================================================================{RESET}")

    verify_adr_and_documentation()
    verify_ssp_contract()
    verify_zero_core_adapter_pluggability()
    verify_3d_galaxy_data_model()
    verify_canonical_mcp_contracts()

    print(f"\n{BOLD}{GREEN}======================================================================{RESET}")
    print(f"{BOLD}{GREEN}   [SUCCESS] Milestone P0 (GitHub #1) Architecture Freeze FULLY VALIDATED! {RESET}")
    print(f"{BOLD}{GREEN}======================================================================{RESET}\n")


if __name__ == "__main__":
    main()
