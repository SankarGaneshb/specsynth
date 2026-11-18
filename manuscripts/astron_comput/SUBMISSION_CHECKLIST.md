# *Astronomy and Computing* (Elsevier) Submission Checklist (`manuscripts/astron_comput/`)

This directory is a **self-contained Elsevier `elsarticle` submission bundle** for ***Astronomy and Computing*** (Software / Infrastructure Article), kept separate from `paper/` so existing CI workflows and the JOSS manuscript remain untouched.

## Compliance Verification

- [x] **Template**: Official Elsevier `elsarticle` (`preprint,12pt,authoryear` with `elsarticle-harv` bibliography and `\linenumbers` enabled for peer review).
- [x] **Abstract**: ~220 words (within Elsevier's 150–250 word recommendation).
- [x] **Highlights**: 4 bullet points, each strictly ≤ 85 characters including spaces.
- [x] **Mandatory Elsevier Sections Included**:
  - Keywords (`\sep`-delimited)
  - CRediT Authorship Contribution Statement
  - Declaration of Generative AI and AI-Assisted Technologies in the Writing Process
  - Declaration of Competing Interest
  - Data and Code Availability
  - Appendix A: Benchmark Provenance & Reproduction Commands
- [x] **All 22 Citations & 6 Figures Verified**: Zero missing BibTeX entries, zero unused entries, zero missing figure files, zero `../` parent-directory paths.
- [x] **Manifest Consistency Audited**: Exact alignment across all 5 JSON manifests (`CUDA 12.2`, `CuPy 13.3.0`, `3.96 s` JWST runtime matching Figure 6, honest reporting of both 3-node OCI OKE scaling and single-host 3-worker OpenBLAS contention).

## Action Items Before Submission

1. **Update contact email**: Replace `sankarganesh.astro@example.org` in `main.tex` (line 28) with your real email address, and verify `country={India}` in `\affiliation`.
2. **Mint a Zenodo archival DOI for the `v1.0.0` code release**:
   - Connect `SankarGaneshb/specsynth` on Zenodo and create a GitHub Release (`v1.0.0`), then insert the resulting software DOI into the **Data and Code Availability** section.
3. **Compile on Overleaf**:
   - Open Overleaf → New Project → Upload Project (zip `manuscripts/astron_comput/` containing `main.tex`, `references.bib`, and `figures/`).
   - Confirm clean PDF build (standard TeX Live includes `elsarticle.cls` and `elsarticle-harv.bst`).
4. **Choose Publication Route**:
   - **Subscription route (`$0` APC)**: Free to publish; allows posting a preprint on arXiv (Green Open Access).
   - **Gold Open Access**: Requires an APC (~$2,100–$2,900 unless covered by an institutional Read & Publish agreement).
5. **Important Publishing Policy Note (JOSS vs. *Astronomy and Computing*)**:
   - Publishing this full software paper in *Astronomy and Computing* serves as your **primary peer-reviewed archival software paper** for `specsynth v1.0`. Do **not** submit the same `v1.0` software paper to JOSS simultaneously or subsequently (that would constitute duplicate publication). You *can* publish the short validation/dataset note in `manuscripts/rnaas/` as a companion benchmark note (disclosing & citing it in both directions).
