# External Engine Plugin Example (CB2026)

This directory contains a complete, working example of an independent astrophysicist or research team plugging a custom simulation or Spectral Population Synthesis (SPS) engine into **Specsynth** with **Zero Core Modifications**.

## Architectural Principles (Pillar 1)

1. **No Core Changes**: You never need to fork or edit `specsynth/` internal files to integrate a new engine.
2. **Contractual Interface**: You inherit from `specsynth.adapters.BaseAdapter` and return a validated `specsynth.adapters.SSPData` container.
3. **Automated Conformance**: Run `assert_adapter_conforms(YourAdapter)` to mathematically certify compliance with 11 core scientific invariants (monotonic grids, positive flux, finite numbers, age-major 2D flattening, wavelength resampling).
4. **Dynamic Discovery**: Register your engine at runtime via `register_adapter("name", YourAdapter)` or advertise it via Python `entry_points` in your package's `pyproject.toml`.

---

## File Structure

- `cb2026_engine.py`: Represents the third-party external codebase (could be Fortran, C++, or custom Python). Computes grids in its own native formats and coordinate systems.
- `external_adapter.py`: The Specsynth adapter bridging the external engine to Specsynth's contraction pipeline.
- `run_external_workflow.py`: End-to-end runnable script demonstrating registration, conformance testing, grid generation, and synthetic forward modeling.

---

## Running the Example

From the root of the repository:

```bash
python examples/external_engine_plugin/run_external_workflow.py
```

Expected output:
- Conformance Suite runs and reports all 11 checks passed.
- Adapter is registered and retrieved through `specsynth.adapters.get_adapter("cb2026")`.
- 2D matrix contractions and synthetic observations are generated with verified physical invariants.

---

## Troubleshooting & Known Pitfalls

If you encounter unphysical synthetic photometry or conformance failures when plugging in your engine, refer to the **Known Issues & Actionable Diagnostics Guide** in:
[`docs/guides/authoring_external_adapters.md#known-issues-common-pitfalls--actionable-diagnostics`](../../docs/guides/authoring_external_adapters.md#known-issues-common-pitfalls--actionable-diagnostics)

Common quick checks:
1. **Coordinate Monotonicity**: Ensure `ages`, `mets`, and `wave` are strictly ascending.
2. **2D Age-Major Flattening**: Verify shape is `(n_age * n_met, n_wave)`.
3. **Units**: Ensure flux is in $L_\odot \cdot \text{\AA}^{-1} \cdot M_\odot^{-1}$ (not raw CGS $\text{erg/s}$).
4. **Conformance Suite**: Run `assert_adapter_conforms(MyAdapter, verbose=True)` for automated diagnostics.

---

## Packaging Your Own Engine via Entry Points

To publish an adapter as an independent Python package (e.g., `pip install my-sps-engine`), advertise your adapter class in your `pyproject.toml`:

```toml
[project.entry-points."specsynth.adapters"]
my_custom_engine = "my_package.adapter:MyCustomAdapter"
```

When Specsynth starts, `discover_entry_point_adapters()` will automatically discover, load, and register your engine without requiring any code changes in Specsynth!
