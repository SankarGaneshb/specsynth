from __future__ import annotations

from pathlib import Path
from typing import Sequence

import numpy as np

from specsynth.adapters.base import BaseAdapter, SSPData


def parse_fsps_spec_file(
    filepath: str | Path,
    return_mets: bool = False,
) -> tuple[np.ndarray, np.ndarray, np.ndarray] | tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray] | tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, dict]:
    """
    Parse a standard Fortran or SpecSynth FSPS ASCII spectrum output file.
    Extracts explicit age, metallicity, and layout metadata from file headers if present.
    """
    filepath = Path(filepath)
    parsed_ages = None
    parsed_mets = None
    parsed_meta = {}
    col_order = "met_major"  # Default Fortran FSPS spstot layout

    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if not line.startswith("#"):
                    break
                line_str = line.lstrip("#").strip()
                line_lower = line_str.lower()

                if ":" in line_str:
                    key, val = line_str.split(":", 1)
                    key_clean = key.strip().lower()
                    val_clean = val.strip()

                    if key_clean in ("ages (yr)", "ages_yr", "ages"):
                        parts = val_clean.replace(",", " ").split()
                        try:
                            parsed_ages = np.array([float(x) for x in parts], dtype=np.float64)
                        except Exception:
                            pass
                    elif key_clean in ("metallicities", "mets", "mets_z"):
                        parts = val_clean.replace(",", " ").split()
                        try:
                            parsed_mets = np.array([float(x) for x in parts], dtype=np.float64)
                        except Exception:
                            pass
                    elif key_clean in ("col_order", "layout"):
                        col_order = val_clean.lower()
                    elif key_clean in ("is_genuine_fsps", "genuine"):
                        parsed_meta["is_genuine_fsps"] = val_clean.lower() in ("true", "1", "yes")
                    elif key_clean in ("imf", "isochrone", "isochrones", "model"):
                        parsed_meta[key_clean] = val_clean
    except Exception:
        pass

    parsed_meta["col_order"] = col_order

    # If whitespace-separated grid
    data = np.loadtxt(filepath, comments="#")
    if data.ndim == 2:
        # Standard table: col 0 = wave, cols 1..N = flux per age/met
        wave = data[:, 0].astype(np.float64)
        fluxes = data[:, 1:].T.astype(np.float32)
        n_cols = fluxes.shape[0]

        if parsed_ages is not None and len(parsed_ages) > 0:
            ages = parsed_ages
        else:
            ages = np.logspace(6.0, np.log10(1.35e10), n_cols)

        if parsed_mets is not None and len(parsed_mets) > 0:
            mets = parsed_mets
        else:
            mets = np.array([0.019], dtype=np.float64)

        if return_mets:
            return ages, wave, fluxes, mets
        return ages, wave, fluxes
    else:
        raise ValueError(f"Unable to automatically parse FSPS table format in {filepath}")


def find_default_fsps_grid() -> Path | None:
    """Locate pre-compiled bundled wide-wavelength FSPS reference grid."""
    candidates = [
        Path(__file__).parents[2] / "sample_models" / "fsps" / "fsps_full_chabrier_mist.spec",
        Path("sample_models/fsps/fsps_full_chabrier_mist.spec"),
        Path(__file__).parents[2] / "sample_models" / "fsps" / "spstot_chab.spec",
        Path("sample_models/fsps/spstot_chab.spec"),
    ]
    for p in candidates:
        if p.is_file():
            return p.resolve()
    return None


class FSPSAdapter(BaseAdapter):
    """
    Adapter for Flexible Stellar Population Synthesis (FSPS).
    Supports either:
      - Programmatic generation using python-fsps
      - Ingestion of raw FSPS ASCII output files (spstot_*.spec)
      - Offline CPU reproduction via bundled reference grids
    """

    def __init__(
        self,
        filepath: str | Path | None = None,
        imf_type: int | str = "chabrier",
        isochrone: str = "mist",
        ages: Sequence[float] | None = None,
        metallicities: Sequence[float] | None = None,
        metallicity: float = 0.019,
        add_nebular_emission: bool = False,
        fallback_to_bundled: bool = False,
    ):
        self.filepath = Path(filepath) if filepath else None
        self.imf_type = imf_type
        self.isochrone = isochrone
        self.ages = (
            np.asarray(ages, dtype=np.float64)
            if ages is not None
            else np.logspace(6.0, np.log10(1.35e10), 100)
        )
        self.metallicities = (
            np.asarray(metallicities, dtype=np.float64)
            if metallicities is not None
            else None
        )
        self.metallicity = metallicity
        self.add_nebular_emission = add_nebular_emission
        self.fallback_to_bundled = fallback_to_bundled

    def load(self) -> SSPData:
        # File mode
        if self.filepath:
            ages, wave, fluxes, mets = parse_fsps_spec_file(self.filepath, return_mets=True)
            is_analytical = False
            col_order = "met_major"
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    head = f.read(2048).lower()
                    if "analytical_reference" in head or "is_genuine_fsps: false" in head:
                        is_analytical = True
                    if "col_order: age_major" in head or "layout: age_major" in head:
                        col_order = "age_major"
            except Exception:
                pass
            model_name = "analytical_reference" if is_analytical else "FSPS"
            meta = {
                "model": model_name,
                "is_genuine_fsps": not is_analytical,
                "file": str(self.filepath),
                "col_order": col_order,
            }
            if is_analytical:
                meta["note"] = "SpecSynth analytical reference grid (continuum & break proxy; python-fsps not used)"

            n_age = len(ages)
            n_met = len(mets)
            if fluxes.shape[0] == n_age * n_met and n_met > 1:
                if col_order == "age_major":
                    grid_3d = fluxes.reshape(n_age, n_met, len(wave))
                else:
                    grid_3d = fluxes.reshape(n_met, n_age, len(wave)).transpose(1, 0, 2)
            else:
                grid_3d = fluxes[:, None, :]
                if n_met == 1 and self.metallicity:
                    mets = np.array([self.metallicity])

            return SSPData.from_3d_grid(
                ages=ages,
                mets=mets,
                wave=wave,
                grid_3d=grid_3d,
                metadata=meta,
            )

        # Dynamic python-fsps mode
        try:
            import fsps
        except ImportError as e:
            if self.fallback_to_bundled:
                default_file = find_default_fsps_grid()
                if default_file:
                    ages, wave, fluxes, mets = parse_fsps_spec_file(default_file, return_mets=True)
                    is_analytical = False
                    try:
                        with open(default_file, "r", encoding="utf-8") as f:
                            head = f.read(1024).lower()
                            if "analytical_reference" in head or "is_genuine_fsps: false" in head:
                                is_analytical = True
                    except Exception:
                        pass
                    model_name = "analytical_reference" if is_analytical else "FSPS"
                    meta = {
                        "model": model_name,
                        "is_genuine_fsps": not is_analytical,
                        "file": str(default_file),
                        "note": "Bundled reference grid (analytical proxy; python-fsps not installed)" if is_analytical else "Bundled reference grid",
                    }
                    return SSPData.from_3d_grid(
                        ages=ages,
                        mets=mets,
                        wave=wave,
                        grid_3d=fluxes[:, None, :],
                        metadata=meta,
                    )
            raise ImportError(
                "python-fsps is required to run the dynamic FSPS adapter. Install it with: "
                "conda install -c conda-forge fsps python-fsps or pip install fsps "
                "or pass an exported FSPS file using --input-file."
            ) from e

        imf_map = {"salpeter": 0, "chabrier": 1, "kroupa": 2}
        imf_code = (
            imf_map.get(str(self.imf_type).lower(), self.imf_type)
            if isinstance(self.imf_type, str)
            else self.imf_type
        )

        sp = fsps.StellarPopulation(
            compute_vega_mags=False,
            zcontinuous=1,
            imf_type=imf_code,
            add_nebular_emission=self.add_nebular_emission,
        )

        if self.metallicities is None:
            z_sun = 0.019
            log_z = sp.zlegend
            mets = (10.0**log_z) * z_sun
        else:
            mets = np.asarray(self.metallicities, dtype=np.float64)

        wave = sp.wavelengths.astype(np.float64)
        n_age = len(self.ages)
        n_met = len(mets)
        n_wave = len(wave)

        grid_3d = np.empty((n_age, n_met, n_wave), dtype=np.float32)

        z_sun = 0.019
        for j, z in enumerate(mets):
            log_z_ratio = np.log10(max(z, 1e-6) / z_sun)
            sp.params["logzsol"] = log_z_ratio
            for i, age_yr in enumerate(self.ages):
                _, flux = sp.get_spectrum(tage=age_yr / 1e9, peraa=True)
                grid_3d[i, j, :] = flux

        return SSPData.from_3d_grid(
            ages=self.ages,
            mets=mets,
            wave=wave,
            grid_3d=grid_3d,
            metadata={
                "model": "FSPS",
                "imf": str(self.imf_type),
                "isochrone": self.isochrone,
                "nebular": self.add_nebular_emission,
            },
        )

    def to_contract(self) -> Any:
        """Load and convert to a validated SSPGridContract (v1.0.0)."""
        from specsynth.contracts.ssp import SSPGridContract
        ssp_data = self.load()
        meta = ssp_data.metadata
        return SSPGridContract(
            source_engine=meta.get("model", "FSPS"),
            engine_version="3.2",
            imf=str(self.imf_type),
            isochrones=str(self.isochrone),
            ages_yr=ssp_data.ages,
            mets_z=ssp_data.mets,
            wave_angstrom=ssp_data.wave,
            ssp_flux_2d=ssp_data.ssp,
            metadata=meta,
        )

    def get_capabilities(self) -> dict[str, Any]:
        """Declare FSPS adapter capabilities and runtime mode."""
        try:
            import fsps
            dynamic_available = True
        except ImportError:
            dynamic_available = False

        return {
            "name": "FSPSAdapter",
            "version": "3.2.0",
            "dynamic_metallicity": True,
            "resampling_supported": True,
            "supported_imfs": ["salpeter", "chabrier", "kroupa"],
            "supported_isochrones": ["mist", "padova", "parsec"],
            "dynamic_python_fsps_available": dynamic_available,
            "bundled_reference_available": find_default_fsps_grid() is not None,
        }

    @staticmethod
    def export_spec_file(
        filepath: str | Path,
        ages_yr: np.ndarray,
        mets_z: np.ndarray,
        wave_angstrom: np.ndarray,
        fluxes_2d: np.ndarray,
        is_genuine_fsps: bool = False,
        imf: str = "chabrier",
        isochrone: str = "mist",
        col_order: str = "age_major",
    ) -> None:
        """
        Export a multi-metallicity or single-metallicity grid to a standardized FSPS .spec table
        with self-documenting headers and layout conventions.
        """
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("# SpecSynth FSPS Spectral Grid Table\n")
            f.write(f"# is_genuine_fsps: {is_genuine_fsps}\n")
            f.write(f"# model: {'FSPS' if is_genuine_fsps else 'analytical_reference'}\n")
            f.write(f"# imf: {imf}\n")
            f.write(f"# isochrone: {isochrone}\n")
            f.write(f"# col_order: {col_order}\n")
            f.write(f"# N_WAVE={len(wave_angstrom)}, N_AGE={len(ages_yr)}, N_MET={len(mets_z)}\n")
            f.write(f"# Ages_yr: {', '.join(f'{a:.4e}' for a in ages_yr)}\n")
            f.write(f"# Metallicities: {', '.join(f'{m:.4e}' for m in mets_z)}\n")
            f.write("# Col 0: Wavelength (Angstroms), Cols 1..K: Flux (L_sun/A per M_sun formed)\n")

            # Table data: shape (N_wave, 1 + N_cols)
            # fluxes_2d is shape (N_cols, N_wave), so fluxes_2d.T is shape (N_wave, N_cols)
            combined = np.column_stack([wave_angstrom, fluxes_2d.T])
            np.savetxt(f, combined, fmt="%.8e")

