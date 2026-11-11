from __future__ import annotations

import sys
import time
from typing import Any

import dask.array as da
import numpy as np
from dask.distributed import Client, progress

YOUNG_AGE_YR = 1.0e7  # stars younger than this sit in their birth cloud
N_PARAM = 6  # log10 M*, t_onset[Gyr], tau[Gyr], log10 Z_centre, tau_diffuse, tau_birth


def url(base: str, name: str) -> str:
    """Format an fsspec URL or filesystem path."""
    cleaned = base.rstrip("/\\")
    return f"{cleaned}/{name}"


def read_small(store: str, comp: str) -> np.ndarray:
    """Read a small metadata/grid array from Zarr storage into memory."""
    return da.from_zarr(store, component=comp).compute()


def write_many(
    client: Client,
    store: str,
    arrays: dict[str, da.Array],
    metadata: dict[str, Any] | None = None,
):
    """Write several dask arrays into one Zarr store in a single graph, with optional metadata."""
    tasks = [
        da.to_zarr(a, store, component=name, overwrite=True, compute=False)
        for name, a in arrays.items()
    ]
    fut = client.compute(tasks)
    if sys.stdout.isatty():  # progress bars only make sense on a terminal
        progress(fut, notebook=False)
        print()
    client.gather(fut)

    if metadata:
        try:
            import zarr
            try:
                grp = zarr.open_group(store, mode="a")
            except Exception:
                import fsspec
                grp = zarr.open_group(fsspec.get_mapper(store), mode="a")
            grp.attrs.update(metadata)
        except Exception as e:
            # Non-critical warning if writing attrs fails
            print(f"Notice: could not attach metadata attributes to {store}: {e}")


def small(a: np.ndarray) -> da.Array:
    """Wrap a small NumPy array into a Dask array with a single chunk."""
    return da.from_array(np.asarray(a), chunks=a.shape)


def attenuation_curve(wave: np.ndarray, index: float) -> np.ndarray:
    """k(lam) = (lam / 5500 A) ** index   (tau_lam = tau_V * k)."""
    return ((wave / 5500.0) ** index).astype(np.float32)


def planck(wave_A: np.ndarray, T: float) -> np.ndarray:
    """Planck function blackbody flux in Angstroms."""
    lam = wave_A * 1e-10
    x = np.clip(1.4388e-2 / (lam * T), 1e-6, 700)
    return 1.0 / (lam**5 * np.expm1(x))


def _gen_params(block: np.ndarray, seed: int, block_info=None) -> np.ndarray:
    """Generate reproducible physical galaxy parameters per chunk."""
    if block_info is not None and None in block_info:
        info = block_info[None]
        loc, n = info["chunk-location"][0], info["chunk-shape"][0]
    else:
        loc, n = 0, block.shape[0]
    rng = np.random.default_rng([seed, loc])  # reproducible for any cluster layout
    p = np.empty((n, N_PARAM), dtype=np.float32)
    p[:, 0] = rng.normal(10.3, 0.7, n)      # log10 M* [Msun]
    p[:, 1] = rng.uniform(0.8, 13.0, n)     # t_onset [Gyr]
    p[:, 2] = rng.uniform(0.3, 8.0, n)      # tau [Gyr]
    p[:, 3] = rng.normal(-1.9, 0.25, n)     # log10 Z_centre
    p[:, 4] = rng.gamma(2.0, 0.25, n)       # tau_diffuse
    p[:, 5] = rng.gamma(2.0, 0.35, n)       # tau_birth
    return p


def sfh_from_params(p: np.ndarray, ages: np.ndarray, mets: np.ndarray) -> np.ndarray:
    """Delayed-tau SFH x Gaussian metallicity distribution -> (n, T*Z) masses."""
    edges = np.sqrt(ages[1:] * ages[:-1])
    edges = np.concatenate([[ages[0] ** 2 / edges[0]], edges, [ages[-1] ** 2 / edges[-1]]])
    dt = np.diff(edges)  # yr
    mass = 10.0 ** p[:, 0].astype(np.float64)
    t_on = p[:, 1, None] * 1e9
    tau = p[:, 2, None] * 1e9
    t_form = np.clip(t_on - ages[None, :], 0.0, None)  # time since onset
    sfr = t_form * np.exp(-t_form / tau)
    w_t = sfr * dt[None, :] + 1e-30
    w_t /= w_t.sum(1, keepdims=True)
    lz = np.log10(mets)[None, :]
    w_z = np.exp(-0.5 * ((lz - p[:, 3, None]) / 0.3) ** 2) + 1e-30
    w_z /= w_z.sum(1, keepdims=True)
    sfh = mass[:, None, None] * w_t[:, :, None] * w_z[:, None, :]
    return sfh.reshape(len(p), -1).astype(np.float32)


def synth_block(
    sfh: np.ndarray,
    tau_d: np.ndarray,
    tau_b: np.ndarray,
    ssp: np.ndarray,
    k_d: np.ndarray,
    k_b: np.ndarray,
    n_young_k: int,
    use_gpu: bool = False,
) -> np.ndarray:
    """One chunk: (n,K)@(K,w) twice, then dust attenuation. Pure numpy/CuPy, no I/O."""
    if use_gpu:
        from specsynth.gpu import synth_block_gpu
        return synth_block_gpu(sfh, tau_d, tau_b, ssp, k_d, k_b, n_young_k)

    young = sfh[:, :n_young_k] @ ssp[:n_young_k]
    old = sfh[:, n_young_k:] @ ssp[n_young_k:]
    att_b = np.exp(-tau_b[:, None] * k_b[None, :])
    att_d = np.exp(-tau_d[:, None] * k_d[None, :])
    return (att_d * (old + att_b * young)).astype(np.float32)


def band_matrix(wave: np.ndarray, n_bands: int) -> np.ndarray:
    """Normalised top-hat 'filters' log-spaced over the wavelength range."""
    edges = np.logspace(np.log10(wave[0]), np.log10(wave[-1]), n_bands + 1)
    dl = np.gradient(wave)
    filters = []
    for i, (lo, hi) in enumerate(zip(edges[:-1], edges[1:])):
        if i == n_bands - 1:
            mask = (wave >= lo) & (wave <= hi)
        else:
            mask = (wave >= lo) & (wave < hi)
        filters.append(mask * dl)
    m = np.stack(filters, 1)
    norm = np.maximum(m.sum(0, keepdims=True), 1e-30)
    return (m / norm).astype(np.float32)
