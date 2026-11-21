# Physical Assumptions & Equations

**Milestone:** `TNG–JWST Scientific Validation v1.0`  

---

## 1. Stellar Population Synthesis Framework

Each galaxy's composite stellar spectrum $L_\lambda(\lambda, t)$ is modeled as a linear superposition of Simple Stellar Population (SSP) spectra:
$$L_\lambda^{\mathrm{intrinsic}}(\lambda) = \sum_{k=1}^K M_k \cdot \mathrm{SSP}_k(\lambda)$$
where $M_k$ is the stellar mass formed in age bin $t_i$ and metallicity bin $Z_j$ ($k = i \times N_Z + j$), and $\mathrm{SSP}_k(\lambda)$ is the corresponding SSP luminosity density in $L_\odot / \text{\AA}$ per $M_\odot$ formed.

### 1.1 Initial Mass Function (IMF)
We adopt the Chabrier (2003) Galactic field IMF:
$$\xi(\log m) \propto \begin{cases} \exp\left[ -\frac{(\log m - \log m_c)^2}{2 \sigma^2} \right] & (m \le 1.0\,M_\odot) \\ m^{-1.3} & (m > 1.0\,M_\odot) \end{cases}$$
with $m_c = 0.08\,M_\odot$ and $\sigma = 0.69$, normalized over the mass limits $[0.08, 100]\,M_\odot$.

---

## 2. Dust Attenuation: Two-Component Model

We apply the Charlot & Fall (2000) two-component attenuation prescription:
$$F_\lambda^{\mathrm{atten}}(\lambda) = \exp\left[ -\tau_d \left(\frac{\lambda}{5500\,\text{\AA}}\right)^{\alpha_d} \right] \left[ L_{\lambda,\mathrm{old}}(\lambda) + \exp\left[ -\tau_b \left(\frac{\lambda}{5500\,\text{\AA}}\right)^{\alpha_b} \right] L_{\lambda,\mathrm{young}}(\lambda) \right]$$

- **Young Stellar Population**: Stars with age $t < 10\,\mathrm{Myr}$ ($10^7\,\mathrm{yr}$) still reside within their dense birth clouds. They experience attenuation by both the birth cloud (optical depth $\tau_b$, power-law index $\alpha_b = -1.3$) and the diffuse interstellar medium (optical depth $\tau_d$, power-law index $\alpha_d = -0.7$).
- **Old Stellar Population**: Stars with age $t \ge 10\,\mathrm{Myr}$ have migrated out of their birth clouds and experience only diffuse ISM attenuation ($\tau_d$, $\alpha_d = -0.7$).
- **Optical Depth Normalization**: $\tau_d = A_V / 1.086$, $\tau_b = 1.5\,\tau_d$.

---

## 3. Intergalactic Medium (IGM) Transmission

For galaxies at $z > 0$, photons travel through the neutral intergalactic medium. Resonant Lyman series absorption and photoelectric continuum absorption are modeled following Madau (1995):
$$F_\lambda^{\mathrm{obs}}(\lambda_{\mathrm{obs}}) = T_{\mathrm{IGM}}(\lambda_{\mathrm{obs}}, z) \cdot F_\lambda^{\mathrm{unabsorbed}}(\lambda_{\mathrm{obs}})$$
where $T_{\mathrm{IGM}}(\lambda_{\mathrm{obs}}, z) = \exp\left[-\tau_{\mathrm{eff}}(\lambda_{\mathrm{obs}}, z)\right]$.

1. **Lyman-Series Resonant Line Blanketing**:
   $$\tau_{\mathrm{line}}(\lambda_{\mathrm{obs}}) = \sum_{j=1}^{16} A_j \left(\frac{\lambda_{\mathrm{obs}}}{\lambda_j}\right)^{3.46}$$
   evaluated for all Lyman lines redward of $\lambda_{\mathrm{obs}} / (1+z)$ up to Ly$\alpha$ ($1215.67\,\text{\AA}$).
2. **Photoelectric Lyman Continuum Edge**:
   Shortward of $\lambda_{\mathrm{obs}} \le 911.75\,\text{\AA} \cdot (1+z)$, neutral hydrogen photoelectric absorption sets in:
   $$\tau_{\mathrm{cont}}(\lambda_{\mathrm{obs}}) = 0.25\,x_c^3 \left[(1+z)^{0.46} - x_c^{0.46}\right] + 9.4\,x_c^{1.5} \left[(1+z)^{0.18} - x_c^{0.18}\right] - 0.7\,x_c^3 \left[(1+z)^{-1.32} - x_c^{-1.32}\right]$$
   where $x_c \equiv \lambda_{\mathrm{obs}} / 911.75\,\text{\AA}$.

---

## 4. Cosmological Distance Dimming

The observed monochromatic flux density $F_\lambda(\lambda_{\mathrm{obs}})$ is related to rest-frame luminosity density $L_\lambda(\lambda_{\mathrm{rest}})$ by:
$$F_\lambda(\lambda_{\mathrm{obs}}) = \frac{1}{1+z} \frac{L_\lambda\left(\frac{\lambda_{\mathrm{obs}}}{1+z}\right)}{4\pi D_L^2(z)}$$
where $D_L(z)$ is the luminosity distance in centimeters. The factor $(1+z)^{-1}$ accounts for the cosmological dilation of the wavelength interval ($d\lambda_{\mathrm{obs}} = (1+z)d\lambda_{\mathrm{rest}}$).
