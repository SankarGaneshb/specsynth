# Cosmological Framework & Redshift Conventions

**Milestone:** `TNG–JWST Scientific Validation v1.0`  

---

## 1. Simulation Cosmology (Planck 2015 Alignment)

To maintain absolute physical consistency with the underlying IllustrisTNG hydrodynamical simulation suite (Pillepich et al. 2018), `specsynth` defaults to the exact simulation cosmology:

$$\begin{aligned}
H_0 &= 67.74\text{ km s}^{-1}\text{Mpc}^{-1} \quad (h = 0.6774) \\
\Omega_m &= 0.3089 \\
\Omega_\Lambda &= 1.0 - \Omega_m = 0.6911 \\
\Omega_b &= 0.0486 \\
\sigma_8 &= 0.8159 \\
n_s &= 0.9667
\end{aligned}$$

This cosmology is accessible programmatically via:
```python
from specsynth.cosmology import TNG_COSMOLOGY, get_cosmology
cosmo = get_cosmology("tng")
```
or via the CLI using `--cosmology tng`.

---

## 2. Distance Calculations & Numerical Integration

In `specsynth.cosmology.FlatLambdaCDM`, distances are evaluated via Gauss-Legendre quadrature (100 nodes default; verified against 2,000 nodes to $< 10^{-5}$ relative accuracy):

1. **Hubble Parameter**:
   $$E(z) \equiv \sqrt{\Omega_m(1+z)^3 + \Omega_\Lambda}$$
2. **Line-of-Sight Comoving Distance**:
   $$D_C(z) = \frac{c}{H_0} \int_0^z \frac{dz'}{E(z')}$$
3. **Luminosity Distance**:
   $$D_L(z) = (1+z) D_C(z)$$

### Physical Conversion Factors (IAU 2015 Resolution B3):
- Speed of light: $c = 299{,}792.458\,\mathrm{km/s}$
- Parsec to centimeter: $1\,\mathrm{pc} = 3.08567758128 \times 10^{18}\,\mathrm{cm}$
- Megaparsec to centimeter: $1\,\mathrm{Mpc} = 3.08567758128 \times 10^{24}\,\mathrm{cm}$
- Solar luminosity: $L_\odot = 3.828 \times 10^{33}\,\mathrm{erg/s}$

---

## 3. Limiting Behavior at $z \to 0$

At $z = 0$, $D_L(0) = 0$, which introduces a formal singularity into the $1 / (4\pi D_L^2)$ scaling.
`specsynth` detects $z = 0.0$ and cleanly disables distance dimming, preserving the rest-frame spectral luminosity density without division by zero:
$$\lim_{z \to 0} F_\lambda(\lambda) = L_\lambda(\lambda)$$
