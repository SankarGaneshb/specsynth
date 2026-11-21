# Photometry Integration Methodology & AB Zero Points

**Milestone:** `TNG–JWST Scientific Validation v1.0`  

---

## 1. Photon-Counting vs. Energy-Weighted Detector Integration

Astronomical CCDs and HgCdTe arrays (such as JWST NIRCam) operate as **photon-counting detectors**, measuring the rate of incident photons rather than total radiant energy.

### 1.1 Mathematical Formulation
The photon arrival rate per bandpass is proportional to $\int \frac{F_\nu(\nu)}{h\nu} T(\nu) d\nu$.
The mean synthetic flux density $\langle f_\nu \rangle$ is defined as:
$$\langle f_\nu \rangle = \frac{\int f_\nu(\nu) T(\nu) \frac{d\nu}{\nu}}{\int T(\nu) \frac{d\nu}{\nu}}$$

Transforming frequency $\nu$ to wavelength $\lambda$ via $\nu = c / \lambda$, $d\nu = -c / \lambda^2 d\lambda$:
$$\langle f_\nu \rangle = \frac{\int f_\nu(\lambda) T(\lambda) \frac{d\lambda}{\lambda}}{\int T(\lambda) \frac{d\lambda}{\lambda}}$$

Since $f_\nu(\lambda) = f_\lambda(\lambda) \frac{\lambda^2}{c}$:
$$\langle f_\nu \rangle = \frac{1}{c} \frac{\int f_\lambda(\lambda) T(\lambda) \lambda \, d\lambda}{\int T(\lambda) \frac{d\lambda}{\lambda}}$$

---

## 2. Pivot Wavelength Formulation

The **pivot wavelength** $\lambda_{\mathrm{piv}}$ is an exact mathematical property of the filter transmission curve alone:
$$\lambda_{\mathrm{piv}} \equiv \sqrt{\frac{\int T(\lambda) \lambda \, d\lambda}{\int T(\lambda) \frac{d\lambda}{\lambda}}}$$

Defining the photon-weighted mean spectral flux density $\langle f_\lambda \rangle_{\mathrm{photon}}$:
$$\langle f_\lambda \rangle_{\mathrm{photon}} \equiv \frac{\int f_\lambda(\lambda) T(\lambda) \lambda \, d\lambda}{\int T(\lambda) \lambda \, d\lambda}$$

The two formulations are related by:
$$\langle f_\nu \rangle = \langle f_\lambda \rangle_{\mathrm{photon}} \times \frac{\lambda_{\mathrm{piv}}^2}{c}$$

`specsynth` computes projection matrices using $\langle f_\lambda \rangle_{\mathrm{photon}}$ and maps directly to $F_\nu$ via the pivot wavelength, eliminating intermediate numerical approximations.

---

## 3. AB Magnitude Conversion & Units

The monochromatic AB magnitude system (Oke & Gunn 1983) is defined relative to a constant spectral flux density of $3631\,\mathrm{Jy}$:
$$m_{\mathrm{AB}} = -2.5 \log_{10}\left(\frac{\langle f_\nu \rangle}{3631\,\mathrm{Jy}}\right)$$

In CGS units ($1\,\mathrm{Jy} = 10^{-23}\,\mathrm{erg\,s^{-1}\,cm^{-2}\,Hz^{-1}}$):
$$3631\,\mathrm{Jy} = 3.631 \times 10^{-20}\,\mathrm{erg\,s^{-1}\,cm^{-2}\,Hz^{-1}}$$
$$m_{\mathrm{AB}} = -2.5 \log_{10}(\langle f_\nu \rangle_{\mathrm{cgs}}) - 48.600$$

### MicroJansky Conversion:
$$F_\nu\,[\mu\mathrm{Jy}] = \frac{\langle f_\nu \rangle_{\mathrm{cgs}}}{10^{-29}\,\mathrm{erg\,s^{-1}\,cm^{-2}\,Hz^{-1}}}$$
