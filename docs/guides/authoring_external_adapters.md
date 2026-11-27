# Authoring External Engine Adapters

This guide explains how independent astrophysicists, simulation groups, and spectral synthesis developers can integrate their own engines into **Specsynth** with **Zero Core Modifications** (North Star Pillar 1).

---

## 🎯 The Zero-Core-Modification Principle

Under the Specsynth Architecture and Scope Charter:
> **An independent astrophysicist should be able to plug their own simulation, galaxy-modelling, or spectral-synthesis engine into the Specsynth ecosystem [...] without modifying the core framework.**

You do **not** need to submit a pull request or modify files in `specsynth/` to use a custom model. You can write your adapter as a standalone script, an internal research module, or distribute it as an independent pip-installable package.

---

## 📐 The Adapter Interface Contract

Every Specsynth adapter subclasses `specsynth.adapters.BaseAdapter` and implements three core methods:

```python
from specsynth.adapters import BaseAdapter, SSPData
import numpy as np

class MyCustomAdapter(BaseAdapter):
    """Adapter wrapping an external spectral synthesis or simulation engine."""

    def __init__(self, **kwargs):
        super().__init__()
        # Store user parameters (e.g. IMF, resolution, isochrones)

    def load(self, wave_resample: np.ndarray | None = None) -> SSPData:
        """
        Execute computation or read on-disk grids, returning a verified SSPData container.
        """
        ...

    def validate(self) -> bool:
        """Return True if external dependencies, grids, or data files are valid."""
        return True

    def get_capabilities(self) -> dict:
        """Return engine metadata, supported ranges, and physical assumptions."""
        return {
            "name": "my_custom_engine",
            "imf": "chabrier",
            "resolution": "R~2000",
            "wavelength_range_aa": [912.0, 30000.0],
            "age_range_yr": [1e7, 1e10],
            "metallicity_range": [0.001, 0.04],
        }
```

---

## 🗄️ Coordinate & Grid Specifications (`SSPData`)

The `load()` method must return an instance of `specsynth.adapters.SSPData`. This container enforces strict dimensional and physical invariants:

| Axis | Shape / Type | Invariant Rules | Units |
| :--- | :--- | :--- | :--- |
| `ages` | 1D `float64` array ($N_\text{age}$) | Strictly monotonically increasing ($t_{i+1} > t_i$) | Years ($\text{yr}$) |
| `mets` | 1D `float64` array ($N_\text{met}$) | Strictly monotonically increasing ($Z_{j+1} > Z_j$) | Metal mass fraction $Z$ |
| `wave` | 1D `float64` array ($N_\text{wave}$) | Strictly monotonically increasing ($\lambda_{k+1} > \lambda_k$) | Rest-frame Angstroms ($\text{\AA}$) |
| `ssp` | 2D `float32` matrix ($N_\text{age} \times N_\text{met},\, N_\text{wave}$) | Age-major flattening: $\text{idx} = i \cdot N_\text{met} + j$. Non-negative ($L_\lambda \ge 0$), finite. | $L_\odot \cdot \text{\AA}^{-1} \cdot M_\odot^{-1}$ |

### Converting a 3D Grid into 2D Age-Major Format
If your engine naturally computes a 3D tensor of shape `(n_age, n_met, n_wave)`:
```python
# Flatten into 2D age-major layout
ssp_2d = np.ascontiguousarray(
    flux_3d.reshape((n_age * n_met, n_wave)),
    dtype=np.float32,
)

data = SSPData(
    ages=linear_ages_yr,
    mets=metallicities_z,
    wave=wave_angstroms,
    ssp=ssp_2d,
)
```

---

## 🔬 Programmatic Conformance Certification

Before running forward modeling, certify your adapter using the built-in **16-point Conformance Suite**:

```python
from specsynth.adapters import assert_adapter_conforms

# Run full programmatic verification
result = assert_adapter_conforms(MyCustomAdapter, verbose=True)

if result.passed:
    print("✓ Adapter strictly conforms to all Specsynth physical and architectural invariants.")
```

The conformance suite verifies:
1. Proper subclass inheritance and lifecycle implementation.
2. Coordinate monotonicity across all three physical dimensions.
3. Strict 2D age-major matrix layout matching Dask GEMM contraction rules.
4. Total absence of `NaN`, `Inf`, or unphysical negative luminosities.
5. Correct behavior of internal wavelength grid resampling (`resample_wavelength`).

---

## 🚀 Runtime Registration & Discovery

### Method 1: Runtime Registration in Python
You can register your adapter dynamically at runtime:

```python
from specsynth.adapters import register_adapter, get_adapter

# Register adapter class
register_adapter("my_engine", MyCustomAdapter, aliases=["custom_sps"])

# Retrieve instance via the factory
adapter = get_adapter("my_engine")
```

### Method 2: Dynamic Entry-Point Discovery (Standalone Package)
If you publish your engine as a separate Python package, declare an entry point under the `specsynth.adapters` group in your package's `pyproject.toml`:

```toml
[project.entry-points."specsynth.adapters"]
my_engine = "my_package.adapter:MyCustomAdapter"
```

When Specsynth starts or queries `list_adapters()`, your adapter is automatically discovered, registered, and available to the CLI, Python API, and MCP tools with zero configuration!

---

## 🚨 Known Issues, Common Pitfalls & Actionable Diagnostics

When integrating custom stellar models or external hydro-simulations, subtle formatting or astrophysical mismatches can arise. Use this quick reference to instantly diagnose symptoms and apply recommended fixes:

| Symptom / Sentry Alert | Probable Root Cause | Actionable Fix / What to Look Into |
| :--- | :--- | :--- |
| **`matrix_shape` mismatch or strange age steps** | **Axis Transposition**: Flattened grid is metallicity-major instead of age-major. | Ensure index $k = i_{\rm age} \cdot N_{\rm met} + i_{\rm met}$. Reshape from `(n_age, n_met, n_wave)` using contiguous C-ordering. |
| **High-$z$ galaxies are drastically too blue** ($F150W - F444W < -2$) | **Lyman Edge Leakage**: Missing photoelectric absorption below $912\,\text{\AA}$. | Enable `--igm` in Specsynth to apply Madau (1995) attenuation, and verify massive O-star atmosphere models cut off at $912\,\text{\AA}$. |
| **Negative flux dips around absorption lines** | **Resampling Oscillation**: High-order splines overshooting near sharp spectral features. | Use monotonic cubic Hermite or log-linear interpolation in `resample_wavelength()`, or densify wavelength sampling near the $4000\,\text{\AA}$ break. |
| **Synthetic magnitudes are 25-35 mag too bright/faint** | **Unit Scaling Mismatch**: Providing $\text{erg/s/\AA}$ instead of solar luminosities $L_\odot/\text{\AA}$. | Divide rest-frame spectrum by solar luminosity ($L_\odot = 3.828 \times 10^{33}\,\text{erg/s}$) and normalize per formed solar mass ($M_\odot$). |
| **`wavelength_monotonicity` failure** | **Inverted Grid**: Grid provided in ascending frequency ($\nu$) instead of ascending wavelength ($\lambda$). | Sort wavelength array with `np.sort(wave)` and reverse the spectral axis: `flux = flux[..., ::-1]`. |
| **Sentry Tier 2: Unphysical $M/L > 100$** | **Missing TP-AGB or Low-Mass Cutoff**: IMF bottom-heavy or evolved stars omitted. | Inspect IMF slope $\alpha$ (ensure $\alpha \approx 2.3$ for high masses) and verify low-mass cutoff ($M_{\rm min} \ge 0.08\,M_\odot$). |

---

## 📂 Working Example

A complete reference implementation containing a simulated third-party SPS engine (`CB2026Engine`), an external adapter (`CB2026Adapter`), and an end-to-end runnable script is available in the repository at:
`examples/external_engine_plugin/`
