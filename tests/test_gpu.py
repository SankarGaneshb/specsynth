import numpy as np
import pytest

from specsynth.core import synth_block
from specsynth.gpu import get_device_info, is_gpu_available, synth_block_gpu


def test_gpu_diagnostics():
    avail = is_gpu_available()
    assert isinstance(avail, bool)

    info = get_device_info()
    assert "gpu_available" in info
    assert "device_name" in info


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
