from __future__ import annotations

import sys
from unittest.mock import MagicMock
import numpy as np
import pytest

pytestmark = pytest.mark.critical

from specsynth.core import synth_block
from specsynth.gpu import (
    _GPU_AVAILABLE,
    get_array_module,
    get_device_info,
    is_gpu_available,
    synth_block_gpu,
)
import specsynth.gpu as sgpu


def test_gpu_diagnostics():
    # In default CI / CPU environments
    sgpu._GPU_AVAILABLE = None
    avail = is_gpu_available()
    assert isinstance(avail, bool)

    # Calling again should use cached result
    assert is_gpu_available() == avail

    info = get_device_info()
    assert "gpu_available" in info
    assert "device_name" in info


def test_get_array_module_cpu(monkeypatch):
    monkeypatch.setattr(sgpu, "is_gpu_available", lambda: False)
    mod = get_array_module(np.array([1, 2, 3]))
    assert mod is np
    mod_none = get_array_module()
    assert mod_none is np


def test_synth_block_gpu_fallback_equivalence():
    # Verify that synth_block_gpu outputs the exact same results as CPU synth_block
    n_gal = 4
    K = 10
    W = 20
    ny = 4

    sfh = np.ones((n_gal, K), dtype=np.float32) * 2.0
    ssp = np.ones((K, W), dtype=np.float32) * 0.5
    tau_d = np.array([0.2, 0.4, 0.6, 0.8], dtype=np.float32)
    tau_b = np.array([0.5, 0.7, 0.9, 1.1], dtype=np.float32)
    kd = np.ones(W, dtype=np.float32)
    kb = np.ones(W, dtype=np.float32) * 1.5

    cpu_res = synth_block(
        sfh=sfh,
        tau_d=tau_d,
        tau_b=tau_b,
        ssp=ssp,
        k_d=kd,
        k_b=kb,
        n_young_k=ny,
        use_gpu=False,
    )

    gpu_or_fallback_res = synth_block_gpu(
        sfh=sfh,
        tau_d=tau_d,
        tau_b=tau_b,
        ssp=ssp,
        k_d=kd,
        k_b=kb,
        n_young_k=ny,
        return_host=True,
    )

    assert cpu_res.shape == (n_gal, W)
    assert np.allclose(cpu_res, gpu_or_fallback_res, atol=1e-5)


def test_gpu_mocked_cuda_device(monkeypatch):
    import sys

    # Create mock CuPy module
    mock_cp = MagicMock()
    mock_cp.cuda.runtime.getDeviceCount.return_value = 1
    mock_cp.zeros.return_value = np.zeros(1, dtype=np.float32)

    mock_dev = MagicMock()
    mock_dev.id = 0
    mock_dev.mem_info = (8 * 1024**3, 16 * 1024**3)
    mock_cp.cuda.Device.return_value = mock_dev
    mock_cp.cuda.runtime.getDeviceProperties.return_value = {"name": b"NVIDIA RTX 4090"}

    mock_cp.asarray.side_effect = lambda x, **kwargs: np.asarray(x, dtype=np.float32)
    mock_cp.matmul.side_effect = lambda a, b: a @ b
    mock_cp.exp.side_effect = lambda x: np.exp(x)
    mock_cp.asnumpy.side_effect = lambda x: np.asarray(x, dtype=np.float32)
    mock_cp.get_array_module.return_value = mock_cp

    monkeypatch.setitem(sys.modules, "cupy", mock_cp)
    sgpu._GPU_AVAILABLE = None

    # Test GPU is available
    assert is_gpu_available() is True
    assert get_array_module() is mock_cp
    assert get_array_module(np.array([1])) is mock_cp

    # Test GPU Device info
    info = get_device_info()
    assert info["gpu_available"] is True
    assert info["device_name"] == "NVIDIA RTX 4090"
    assert info["free_memory_gb"] == 8.0
    assert info["total_memory_gb"] == 16.0

    # Test synth_block_gpu with return_host=True and return_host=False
    n_gal, K, W, ny = 2, 4, 10, 2
    sfh = np.ones((n_gal, K), dtype=np.float32)
    ssp = np.ones((K, W), dtype=np.float32)
    tau_d = np.array([0.1, 0.2], dtype=np.float32)
    tau_b = np.array([0.3, 0.4], dtype=np.float32)
    kd = np.ones(W, dtype=np.float32)
    kb = np.ones(W, dtype=np.float32)

    res_host = synth_block_gpu(sfh, tau_d, tau_b, ssp, kd, kb, ny, return_host=True)
    assert res_host.shape == (n_gal, W)

    res_dev = synth_block_gpu(sfh, tau_d, tau_b, ssp, kd, kb, ny, return_host=False)
    assert res_dev is not None

    # Reset cache for teardown
    sgpu._GPU_AVAILABLE = None

