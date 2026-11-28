# Scientific Sentry Quality Assurance

When forward-modeling millions of simulated subhalos, unphysical edge cases (negative masses, zero-metallicity singularities, extreme dust optical depths, or silent `NaN` propagation) can corrupt mock catalogs without raising runtime exceptions. `specsynth.sentry` provides a four-tier quality assurance pipeline that runs either inline during synthesis or post-hoc on synthesized Zarr stores.

---

## Four-Tier Diagnostic Architecture

1. **Tier 1 — Fast Numerical Invariants**:
   - Finite-value bitmask (`np.isfinite`) trapping IEEE 754 `NaN` and $\pm\infty$.
   - Strict non-negativity ($F > 0$).
   - Flux non-amplification invariant ($\int F_{\text{attenuated}}\,d\lambda \le (1 + 10^{-6}) \int F_{\text{intrinsic}}\,d\lambda$).
2. **Tier 2 — Spectral & Photometric Physical Diagnostics**:
   - Narrowband $D_n(4000)$ spectral break index ($0.95 \le D_n(4000) \le 2.50$).
   - UV continuum slope $\beta_{\text{UV}}$ ($-2.80 \le \beta_{\text{UV}} \le +1.50$).
   - Apparent AB magnitude bounds ($10.0 \le m_{\text{AB}} \le 35.0$).
3. **Tier 3 — Population Statistical Validation**:
   - Evaluates color-magnitude spread and bimodality, detecting degenerate constant-vector chunk collapse.
4. **Tier 4 — Quarantine & Clean Catalog Export**:
   - Writes companion `is_valid` boolean masks and structured JSON reports without halting distributed execution.
   - `specsynth clean-catalog` prunes flagged rows and exports a verified catalog.

---

## Usage

```bash
# Post-hoc QA audit across 50,000 sampled galaxies
specsynth --base ./run sentry --sample 50000 --output ./run/sentry_report.json

# Run root-cause clustering & automated quarantine memo
specsynth --base ./run sentry-agent --sample 50000 --clean-output ./run/clean_catalog.parquet

# Or export a pruned clean catalog directly
specsynth --base ./run clean-catalog --output ./run/clean_catalog.parquet
```
