from __future__ import annotations

import os
from typing import Any

import numpy as np

_GPU_AVAILABLE: bool | None = None


def is_gpu_available() -> bool:
    """
    Check if a CUDA-capable GPU and CuPy are available.
    Caches the result so subsequent checks are instant.
    """
    global _GPU_AVAILABLE
    if _GPU_AVAILABLE is not None:
        return _GPU_AVAILABLE

    try:
        import cupy as cp
        # Verify a device exists and is accessible
        count = cp.cuda.runtime.getDeviceCount()
        if count > 0:
            # Perform a tiny probe operation
            _ = cp.zeros(1, dtype=cp.float32) + 1.0
            _GPU_AVAILABLE = True
            return True
    except Exception:
        pass

    _GPU_AVAILABLE = False
    return False


def get_array_module(x: Any = None):
    """Return cupy if GPU is available, else numpy."""
    if is_gpu_available():
        import cupy as cp
        return cp if x is None else cp.get_array_module(x)
    return np


def get_device_info() -> dict[str, Any]:
    """Retrieve GPU hardware diagnostics and memory stats."""
    if not is_gpu_available():
        return {"gpu_available": False, "device_name": "CPU (NumPy)"}

    import cupy as cp
    dev = cp.cuda.Device()
    mem_info = dev.mem_info
    free_gb = mem_info[0] / (1024**3)
    total_gb = mem_info[1] / (1024**3)
    name = cp.cuda.runtime.getDeviceProperties(dev.id)["name"].decode("utf-8")
    return {
        "gpu_available": True,
        "device_id": dev.id,
        "device_name": name,
        "free_memory_gb": round(free_gb, 2),
        "total_memory_gb": round(total_gb, 2),
    }


def synth_block_gpu(
    sfh: np.ndarray,
    tau_d: np.ndarray,
    tau_b: np.ndarray,
    ssp: np.ndarray,
    k_d: np.ndarray,
    k_b: np.ndarray,
    n_young_k: int,
    return_host: bool = True,
) -> np.ndarray:
    """
    GPU-accelerated stellar population synthesis kernel.
    Executes dense matrix contractions via cuBLAS and elementwise operations on device.
    Falls back seamlessly to CPU if GPU is unavailable.
    """
    if not is_gpu_available():
        # CPU Fallback
        young = sfh[:, :n_young_k] @ ssp[:n_young_k]
        old = sfh[:, n_young_k:] @ ssp[n_young_k:]
        att_b = np.exp(-tau_b[:, None] * k_b[None, :])
        att_d = np.exp(-tau_d[:, None] * k_d[None, :])
        return (att_d * (old + att_b * young)).astype(np.float32)

    import cupy as cp

    # Transfer inputs to GPU
    d_sfh = cp.asarray(sfh, dtype=cp.float32)
    d_ssp = cp.asarray(ssp, dtype=cp.float32)
    d_taud = cp.asarray(tau_d, dtype=cp.float32)
    d_taub = cp.asarray(tau_b, dtype=cp.float32)
    d_kd = cp.asarray(k_d, dtype=cp.float32)
    d_kb = cp.asarray(k_b, dtype=cp.float32)

    # cuBLAS accelerated GEMM contractions
    young = cp.matmul(d_sfh[:, :n_young_k], d_ssp[:n_young_k])
    old = cp.matmul(d_sfh[:, n_young_k:], d_ssp[n_young_k:])

    # Dust screen calculation
    att_b = cp.exp(-d_taub[:, None] * d_kb[None, :])
    att_d = cp.exp(-d_taud[:, None] * d_kd[None, :])

    spec = att_d * (old + att_b * young)

    if return_host:
        return cp.asnumpy(spec).astype(np.float32)
    return spec
