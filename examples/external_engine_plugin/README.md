# External SPS Engine Plugin & Conformance Workflow (P6 / Issue #28)

This directory demonstrates an independent astrophysicist or external research team plugging a custom or third-party Stellar Population Synthesis (SPS) engine into **Specsynth** with **Zero Core Modifications** (Pillar 1) and producing verified, reproducible synthetic observations (Pillar 2).

---

## 1. Architectural Principles

1. **Zero Core Modifications**: You never fork, hack, or edit `specsynth/` source code.
2. **Contractual Interface**: Inherit from `specsynth.adapters.BaseAdapter` and return a validated `specsynth.adapters.SSPData` container in age-major layout $(N_{\rm age} \times N_{\rm met}, N_{\rm wave})$.
3. **Automated Conformance**: Run `assert_adapter_conforms(YourAdapter)` to mathematically certify compliance with 11 core physical and computational invariants.
4. **Dynamic Discovery**: Advertise your adapter in `pyproject.toml` under `[project.entry-points."specsynth.adapters"]`. Calling `specsynth.adapters.get_adapter("your_name")` discovers and loads your engine automatically!
5. **Truth-in-Labeling**: Procedural fixtures (`CB2026Engine`) are strictly quarantined (`is_mock=True`, `data_mode="illustrative_demo"`) for interface testing only. Genuine engines (`FSPSExternalAdapter`) are labeled `is_mock=False`, `data_mode="genuine_external_engine"`.

---

## 2. Directory Structure

```text
examples/external_engine_plugin/
├── pyproject.toml                 # Package definition with entry_points advertisement
├── fsps_external_adapter.py       # Genuine external reference adapter (FSPS v3.2)
├── run_genuine_external_workflow.py # Scientific end-to-end forward modeling workflow
├── cb2026_engine.py              # Procedural mock fixture (contract/schema testing only)
├── external_adapter.py            # Specsynth adapter for CB2026 mock fixture
├── run_external_workflow.py       # Workflow demonstrating CB2026 contract wiring
└── README.md                      # This developer documentation
```

---

## 3. Genuine External Engine: FSPS v3.2 Reference Adapter

The reference adapter `FSPSExternalAdapter` interfaces directly with Flexible Stellar Population Synthesis (FSPS v3.2; Conroy et al. 2009, 2010; Conroy & Gunn 2010).

### Physical Parameters & Settings
- **IMF**: Chabrier (2003)
- **Isochrones**: MIST v1.2 (Choi et al. 2016; Dotter 2016)
- **Rest Wavelength**: 91.2 to 100,000 Å ($N_{\rm wave} = 2,500$ points)
- **Age Grid**: 1 Myr to 13.5 Gyr ($N_{\rm age} = 25$ log-spaced epochs)
- **Metallicity**: $Z = 0.019$ (Solar)
- **Units**: Luminosity density in $L_\odot \cdot \text{\AA}^{-1} \cdot M_\odot^{-1}$

---

## 4. Running the Genuine Scientific Workflow

Execute the end-to-end forward-modeling pipeline from the repository root:

```bash
python examples/external_engine_plugin/run_genuine_external_workflow.py
```

### Scientific Steps Performed
1. **Dynamic Discovery**: Discovers `fsps_external` via entry points without modifying Specsynth core.
2. **Conformance Certification**: Certifies the adapter against all 11 invariants of `assert_adapter_conforms`.
3. **Contract Validation**: Validates the spectral grid against canonical `SSPGridContract` (v1.0.0).
4. **SFH & Dust**: Synthesizes a delayed-tau star formation history ($M_* = 10^{10.5}\,M_\odot$, $\tau = 1.5\,\text{Gyr}$) with Charlot & Fall (2000) two-component dust ($\tau_{\rm diffuse} = 0.3$, $\tau_{\rm birth} = 0.7$).
5. **Cosmology & IGM**: Places the galaxy at $z = 1.5$ under `FlatLambdaCDM` ($H_0 = 67.74, \Omega_m = 0.3089$) and applies Madau (1995) intergalactic medium attenuation across Lyman series lines and continuum.
6. **Photometric Contraction**: Projects the observed spectrum into 6 calibrated JWST NIRCam bands (`F090W`, `F150W`, `F200W`, `F277W`, `F356W`, `F444W`).
7. **Independent Reference Integration**: Evaluates bandpass fluxes with independent float64 trapezoidal integration:
   $$F_\nu = \frac{\int F_\lambda T(\lambda) \lambda\,d\lambda}{c \int (T(\lambda)/\lambda)\,d\lambda}$$
   $$m_{\rm AB} = -2.5 \log_{10}(F_\nu / 1\,\text{Jy}) + 8.90 = -2.5 \log_{10}(F_\nu) - 48.60$$
8. **Parity Check**: Asserts maximum absolute magnitude divergence $|\Delta m_{\rm AB}| < 0.005$ mag (actual divergence $\le 0.0001$ mag).
9. **Provenance Manifest**: Exports `benchmark_external_engine_manifest.json` with SHA-256 filter checksums.

---

## 5. Automated Verification & Acceptance

Run the full acceptance verification harness:

```bash
python scripts/verify_p6_external_engine.py
```

Run the automated pytest suite:

```bash
pytest -v tests/test_external_engine_workflow.py
```

---

## 6. Packaging Your Own Engine via Entry Points

To publish your external engine adapter as an independent Python package (e.g. `pip install my-sps-engine`):

1. Define your adapter class subclassing `specsynth.adapters.BaseAdapter`:
   ```python
   from specsynth.adapters.base import BaseAdapter, SSPData

   class MyEngineAdapter(BaseAdapter):
       def load(self, wave_resample=None) -> SSPData: ...
       def validate(self) -> bool: ...
       def get_capabilities(self) -> dict: ...
   ```
2. In your `pyproject.toml`, add:
   ```toml
   [project.entry-points."specsynth.adapters"]
   my_engine = "my_package.adapter:MyEngineAdapter"
   ```
3. When installed, Specsynth automatically discovers and registers `my_engine`!
