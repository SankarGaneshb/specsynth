# RNAAS Submission Checklist (`manuscripts/rnaas/`)

This directory is a **self-contained submission bundle** for **Research Notes of the AAS (RNAAS)** — kept isolated from `paper/` so the JOSS submission (`paper/paper.md`) remains untouched for May 2027.

## Compliance Verification

- [x] **Word count**: Abstract = ~135 words (limit ≤ 150); estimated grand total including title, abstract, body, figure caption, acknowledgments, and 8 references = ~1,030 words (limit ≤ 1,500).
- [x] **Display items**: Strictly **1 figure** (`fig1_validation.png`), **0 tables**.
- [x] **Line numbers**: Disabled (required by RNAAS since author PDF renders directly to HTML).
- [x] **Single-author voice**: First-person singular (`I`, `my`) verified throughout (`0` occurrences of `we`/`our`/`us`).
- [x] **No parent-directory paths**: All assets (`main.tex`, `references.bib`, `fig1_validation.png`) live directly inside `manuscripts/rnaas/`.
- [x] **JOSS compatibility**: Scoped specifically to numerical validation, verified benchmarks, and the `specsynth-benchmark-100k` Hugging Face dataset (`DOI: 10.57967/hf/11635`) — leaving the full software paper open for JOSS after May 2027 (remember to cite & disclose this RNAAS note in the JOSS submission).

## Action Items Before Upload

1. **Update contact email**: Replace `sankarganesh.astro@example.org` in `main.tex` (line 16) with your real email address.
2. **Compile on Overleaf (recommended)**:
   - Open Overleaf → Template Gallery → **"AASTeX Template for submissions to AAS Journals (ApJ-AJ-ApJS-ApJL-PSJ-RNAAS)"** (AASTeX v7).
   - Upload `main.tex`, `references.bib`, and `fig1_validation.png`.
   - Confirm clean PDF build (no `linenumbers`, no overflow, clean figure rendering).
   - *(If using an older AASTeX v6.31 template, change `\documentclass[RNAAS]{aastex7}` to `\documentclass[RNAAS]{aastex631}` and `\bibliographystyle{aasjournalv7}` to `\bibliographystyle{aasjournal}`.)*
3. **Submit to RNAAS**: Submit directly from Overleaf or via the AAS submission portal (`$0` APC, CC-BY 4.0, NASA ADS indexed).
4. **Regenerate figure if manifests change**:
   ```bash
   python manuscripts/rnaas/make_rnaas_figure.py
   ```
