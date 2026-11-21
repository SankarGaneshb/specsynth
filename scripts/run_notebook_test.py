import json
import time
import matplotlib
matplotlib.use('Agg')

with open('notebooks/tng-jwst/01_tng_jwst_synthetic_photometry.ipynb', encoding='utf-8') as f:
    nb = json.load(f)

print(f"Total notebook cells: {len(nb['cells'])}")
code_cells = [c for c in nb['cells'] if c['cell_type'] == 'code']
print(f"Total code cells: {len(code_cells)}")

globs = {}
t0 = time.perf_counter()
for i, c in enumerate(code_cells):
    code_str = "".join(c['source'])
    t_cell = time.perf_counter()
    exec(code_str, globs)
    print(f"  * Code Cell {i+1} completed in {time.perf_counter() - t_cell:.3f}s")

t_total = time.perf_counter() - t0
print(f"\nNotebook headless execution completed in {t_total:.3f}s")
