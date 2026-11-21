# External Reviewer Feedback Packet & Survey

**Milestone:** `TNG–JWST Scientific Validation v1.0`  
**Contact:** specsynth Development Team  

---

## 1. Invitation to Review

Dear Colleague,

We invite your expert feedback on **`specsynth`**, an open-source distributed forward-modeling engine designed to synthesize survey-scale JWST photometry from simulated galaxies.

Rather than asking you to review an entire software codebase, we have designed a **self-contained 10-minute scientific experiment** that runs locally on your laptop without installing Fortran or specialized GPU runtimes.

### Reviewer Resources:
- **Research Brief**: [`docs/science/tng-jwst-research-brief.md`](tng-jwst-research-brief.md)
- **Executable Notebook**: [`notebooks/tng-jwst/01_tng_jwst_synthetic_photometry.ipynb`](https://github.com/SankarGaneshb/specsynth/blob/main/notebooks/tng-jwst/01_tng_jwst_synthetic_photometry.ipynb)
- **Validation Report**: [`docs/science/validation-report.md`](validation-report.md)

---

## 2. Targeted Feedback Questionnaire

We kindly request your perspective on three core scientific questions:

### Question 1: Physical Assumptions & Model Configuration
*Are our physical assumptions (Chabrier 2003 IMF, MIST isochrones, Charlot & Fall 2000 dust, Madau 1995 IGM, and Planck 2015 cosmology) reasonable for baseline continuum forward-modeling of simulated galaxies?*
- [ ] Yes, appropriate for baseline synthetic observations.
- [ ] Needs minor refinement (please specify).
- [ ] Other: __________________________________________________

### Question 2: JWST NIRCam Filter Treatment & Photometry
*Are the photon-weighted bandpass integration convention and AB magnitude conversions physically defensible for your science cases?*
- [ ] Yes, aligns with standard observational definitions.
- [ ] Needs adjustment (please specify).
- [ ] Other: __________________________________________________

### Question 3: Future Scientific Capabilities
*What additional scientific capability would make this workflow most impactful for your research?*
- [ ] Inclusion of nebular emission lines / photoionization modeling.
- [ ] Spatially resolved IFU / 2D mock imaging forward-modeling.
- [ ] Differentiable SPS (e.g. JAX / gradient-based SED fitting).
- [ ] Additional telescope filter sets (Euclid, Roman, Rubin LSST, HST).
- [ ] Other: __________________________________________________

---

## 3. Submitting Feedback

Feedback can be submitted:
- As a GitHub Issue under milestone `TNG–JWST Scientific Validation v1.0`
- Or via email to the project maintainers.
