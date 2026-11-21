# Distributed, Cloud & GPU Execution

`specsynth` scales seamlessly from a laptop CPU to NVIDIA GPUs and multi-node Kubernetes clusters without changing the physics pipeline.

---

## 1. Execution Schedulers

Select the execution scheduler via the top-level `--scheduler` flag:

| Mode | Flag | Aliases | Best For |
| :--- | :--- | :--- | :--- |
| **Synchronous** | `--scheduler sync` | `synchronous`, `single-threaded` | Unit tests, small runs (< 50k galaxies), debugging (zero IPC/TCP overhead) |
| **Threaded** | `--scheduler threads` | `threaded` | Single-node multi-core BLAS workloads without multiprocessing |
| **Local Distributed** | `--scheduler local` (default) | `localcluster`, `distributed` | Multi-process local cluster with explicit `--workers` and `--memory-limit` |
| **External Cluster** | `--scheduler tcp://<ip>:8786` | — | Remote HPC / Slurm / Kubernetes Dask clusters |

---

## 2. Memory Boundedness & Adaptive Chunking

Working memory is strictly decoupled across three tiers:
1. **Worker Working-Set Footprint**: Scales strictly as $O(N_{\text{chunk}}(K + W))$ where $K$ is the number of SSP templates and $W$ is the wavelength grid resolution. Intermediate spectra stay in worker cache/VRAM and are discarded after in-flight filter projection.
2. **Client-Side Graph Construction Memory**: Dask task graph assembly remains bounded by submitting computations in discrete batches.
3. **Scheduler Memory**: Regulated by the sliding-window batch pipeline (`--batch-chunks`).

Key parameters:
- **`--chunk`**: Number of galaxies processed per Dask block (default tuned via `compute_adaptive_chunk_size` so transient buffers stay under 20% of `--memory-limit`).
- **`--batch-chunks`**: Sliding-window batch pipeline that submits only $B$ chunks at a time to the Dask scheduler, keeping scheduler memory strictly $O(B)$ even for $N \ge 10^8$ galaxies.
- **Task Graph Guard**: Automatically checks total task count to prevent scheduler OOM on billion-galaxy configurations.

```bash
specsynth --base gs://my-survey-bucket/run1 \
    --scheduler tcp://dask-scheduler:8786 \
    synth --filters jwst_nircam --redshift 2.0 --igm \
    --chunk 20000 --batch-chunks 32
```

---

## 3. Cloud Object Storage (`fsspec` + Zarr)

Because every array read/write uses Zarr over `fsspec`, no shared POSIX filesystem (NFS/Lustre) is required across cluster nodes:

- **AWS S3**: `--base s3://bucket-name/specsynth-run` (requires `pip install -e ".[storage]"`)
- **Google Cloud Storage**: `--base gs://bucket-name/specsynth-run`
- **Azure Blob Storage**: `--base abfs://container@account/specsynth-run`

---

## 4. GPU Acceleration (CuPy / CUDA)

When an NVIDIA GPU and `cupy` are available, pass `--gpu` to offload both dense GEMM contractions and dust attenuation to cuBLAS/VRAM with transparent fallback to CPU BLAS if unavailable:

```bash
specsynth --base ./run synth --filters jwst_nircam --redshift 2.0 --gpu
```

Check detected GPU hardware programmatically:

```python
from specsynth.gpu import is_gpu_available, get_device_info
print(is_gpu_available(), get_device_info())
```

---

## 5. Kubernetes Deployment (`k8s/`)

Manifests under `k8s/` deploy a Dask Operator cluster (`k8s/dask-cluster.yaml`) and submit synthesis jobs (`k8s/synth-job.yaml`):

```bash
# 1. Build container image
docker build -t specsynth:latest .

# 2. Deploy DaskCluster via Dask Kubernetes Operator
kubectl apply -f k8s/dask-cluster.yaml

# 3. Submit distributed synthesis job
kubectl apply -f k8s/synth-job.yaml
kubectl logs -f job/specsynth-job
```
