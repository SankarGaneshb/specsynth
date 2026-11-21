# JWST NIRCam Filter Provenance & Verification

**Milestone:** `TNG–JWST Scientific Validation v1.0`  

---

## 1. Instrument Throughput Source & Provenance

All six primary NIRCam filter transmission curves bundled in `specsynth` (`specsynth/data/filters/jwst_*.csv`) are derived from the official **Space Telescope Science Institute (STScI)** calibration files via the **Spanish Virtual Observatory (SVO) Filter Profile Service**.

The tabulated response $T(\lambda)$ represents **total system throughput**, combining:
1. Optical elements (telescope primary + secondary mirrors, NIRCam pickoff mirror, anti-reflection coatings, dichroic beam splitters).
2. Filter substrate transmission curves.
3. HgCdTe detector quantum efficiency (QE).

---

## 2. NIRCam Filter Registry & Checksum Manifest

| Filter ID | Channel | Center [$\text{\AA}$] | FWHM [$\text{\AA}$] | Pivot $\lambda_{\mathrm{piv}}$ [$\text{\AA}$] | SHA-256 Checksum |
|:---|:---:|:---:|:---:|:---:|:---|
| `jwst_f090w` | SW | 9,000 | 2,000 | 8,990.54 | `58eb808d6ecc4ff698234173bab99d9e998c2ea6651fa98ff636de21d9e7ffb8` |
| `jwst_f115w` | SW | 11,500 | 2,300 | 11,520.01 | `1e31b7100dfcdf7cdd5b18e2b66061bf18aeab603fa806e13e266c2165139088` |
| `jwst_f150w` | SW | 15,000 | 3,000 | 14,979.26 | `3a47ccc4006658d4ed704283e97d914516e13c9f90e795c3ef16b06f4487c9b1` |
| `jwst_f200w` | SW | 20,000 | 4,600 | 19,831.19 | `6c1091caa32451e4f7f4426ac8598e72f16916cf35573f54e39beb0de76c3f5d` |
| `jwst_f277w` | LW | 27,700 | 6,800 | 27,545.27 | `f4fe1a9373c090af558f3772e29c3bf46be0377eb2877885c01c154585abb308` |
| `jwst_f356w` | LW | 35,600 | 7,800 | 35,601.98 | `e9682e1a21a18abb9e2f50ca34fc6a95d09ec393fedd7f98dacbf6819ef7847b` |
| `jwst_f444w` | LW | 44,400 | 10,200 | 43,971.35 | `a6582a07bafde3c6e89a1008a7e5f63dbde6d5cd2be822d51266720950083b57` |

---

## 3. Automated Integrity Verification

`specsynth` includes programmatic checksum verification via `specsynth.filters.verify_filter_registry()`.
At pipeline startup or within automated test suites:
```python
from specsynth.filters import verify_filter_registry
status = verify_filter_registry()
assert all(status.values()), "Filter curve integrity compromised!"
```
This guarantees that no truncated, modified, or corrupt ASCII table can silently introduce photometric calibration shifts.
