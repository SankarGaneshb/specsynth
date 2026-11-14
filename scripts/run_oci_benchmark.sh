#!/usr/bin/env bash
# =============================================================================
# specsynth: On-Demand Ephemeral Multi-Node Benchmark on Oracle Cloud (OKE)
# Usage:
#   ./scripts/run_oci_benchmark.sh [NODES] [N_GALAXIES]
# Example:
#   ./scripts/run_oci_benchmark.sh 3 100000
# =============================================================================
set -eo pipefail

TARGET_NODES="${1:-3}"
N_GAL="${2:-100000}"

CLUSTER_OCID="${OCI_CLUSTER_OCID:-ocid1.cluster.oc1.ap-hyderabad-1.aaaaaaaaddhb24hni6golvl6hawziqrrsy5egcefllpv7souvcryswflmioq}"
REGION="${OCI_REGION:-ap-hyderabad-1}"

echo "================================================================="
echo "  specsynth: On-Demand OKE Cluster Scaling Benchmark"
echo "  * Target Worker Nodes : ${TARGET_NODES}"
echo "  * Target Workload     : ${N_GAL} galaxies"
echo "  * Region              : ${REGION}"
echo "================================================================="

# Retrieve Compartment & Node Pool ID
echo "[1/6] Discovering OCI Compartment & Node Pool..."
COMPARTMENT_ID=$(oci ce cluster get --cluster-id "$CLUSTER_OCID" --query 'data."compartment-id"' --raw-output)
NODE_POOL_ID=$(oci ce node-pool list --cluster-id "$CLUSTER_OCID" --compartment-id "$COMPARTMENT_ID" --query "data[0].id" --raw-output)

# Safety Trap: Always scale to 0 when script exits (even on failure or Ctrl+C)
cleanup() {
    echo ""
    echo "================================================================="
    echo "[!] Safety Cleanup Triggered: Scaling node pool back to 0..."
    echo "================================================================="
    oci ce node-pool update --node-pool-id "$NODE_POOL_ID" --size 0 --force >/dev/null 2>&1 || true
    echo "[+] Node pool scaled to 0. All compute costs halted."
}
trap cleanup EXIT INT TERM

# Step 2: Scale Node Pool to requested nodes
echo "[2/6] Scaling Node Pool to ${TARGET_NODES} nodes..."
oci ce node-pool update --node-pool-id "$NODE_POOL_ID" --size "$TARGET_NODES" --force >/dev/null

echo "[3/6] Waiting for ${TARGET_NODES} nodes to reach 'Ready' state..."
while true; do
    READY_NODES=$(kubectl get nodes --no-headers 2>/dev/null | grep -c " Ready" || true)
    echo "  -> Nodes Ready: ${READY_NODES} / ${TARGET_NODES}"
    if [ "$READY_NODES" -ge "$TARGET_NODES" ]; then
        break
    fi
    sleep 10
done
echo "[+] All ${TARGET_NODES} nodes are Ready!"

# Step 4: Ensure Storage & Dask Operator
echo "[4/6] Deploying in-cluster shared storage..."
kubectl apply -f https://raw.githubusercontent.com/SankarGaneshb/specsynth/main/k8s/oci-storage.yaml

# Step 5: Deploy Dask Cluster with requested replicas
echo "[5/6] Deploying Dask Cluster (${TARGET_NODES} worker replicas)..."
kubectl delete daskcluster synth --ignore-not-found

cat << EOF | kubectl apply -f -
apiVersion: kubernetes.dask.org/v1
kind: DaskCluster
metadata:
  name: synth
  namespace: default
spec:
  worker:
    replicas: ${TARGET_NODES}
    spec:
      volumes:
        - name: shared-data
          nfs:
            server: 10.96.140.121
            path: "/"
      containers:
        - name: worker
          image: docker.io/bsankarganesh/specsynth:latest
          imagePullPolicy: Always
          command: ["dask", "worker"]
          args: ["tcp://synth-scheduler:8786", "--name", "\$(DASK_WORKER_NAME)", "--nthreads", "1", "--memory-limit", "3GiB"]
          resources:
            requests: { cpu: "500m", memory: "1Gi" }
            limits:   { cpu: "1", memory: "3Gi" }
          volumeMounts:
            - name: shared-data
              mountPath: /data
  scheduler:
    spec:
      volumes:
        - name: shared-data
          nfs:
            server: 10.96.140.121
            path: "/"
      containers:
        - name: scheduler
          image: docker.io/bsankarganesh/specsynth:latest
          imagePullPolicy: Always
          command: ["dask", "scheduler"]
          ports:
            - { name: tcp-comm, containerPort: 8786 }
            - { name: http-dashboard, containerPort: 8787 }
          volumeMounts:
            - name: shared-data
              mountPath: /data
    service:
      type: ClusterIP
      selector:
        dask.org/cluster-name: synth
        dask.org/component: scheduler
      ports:
        - { name: tcp-comm, port: 8786, targetPort: tcp-comm }
        - { name: http-dashboard, port: 8787, targetPort: http-dashboard }
EOF

echo "  -> Waiting for Dask cluster to be ready..."
sleep 15
kubectl wait --for=condition=Ready pods -l dask.org/cluster-name=synth --timeout=180s

# Step 6: Submit Synthesis Job
echo "[6/6] Submitting distributed synthesis job (${N_GAL} galaxies)..."
kubectl delete job specsynth-run --ignore-not-found

cat << EOF | kubectl apply -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: specsynth-run
  namespace: default
spec:
  backoffLimit: 0
  template:
    spec:
      restartPolicy: Never
      volumes:
        - name: shared-data
          nfs:
            server: 10.96.140.121
            path: "/"
      containers:
        - name: client
          image: docker.io/bsankarganesh/specsynth:latest
          imagePullPolicy: Always
          volumeMounts:
            - name: shared-data
              mountPath: /data
          command: ["/bin/sh", "-c"]
          args:
            - |
              set -e
              BASE=/data/run1
              rm -rf \$BASE && mkdir -p \$BASE
              S="python /app/specsynth.py --base \$BASE --scheduler tcp://synth-scheduler:8786"
              echo "[*] Step 1: Generating SSP library (30 ages x 4 metallicities x 2000 wave)..."
              \$S make-ssp --adapter toy --n-age 30 --n-met 4 --n-wave 2000
              echo "[*] Step 2: Generating SFH for ${N_GAL} galaxies across ${TARGET_NODES} OCI nodes..."
              \$S make-sfh --n-gal ${N_GAL} --chunk 20000
              echo "[*] Step 3: Running Distributed In-Flight Synthesis across ${TARGET_NODES} Dask workers..."
              \$S synth --filters jwst_nircam --redshift 2.0 --igm
              echo "[*] Step 4: Verifying numerical accuracy against double-precision NumPy baseline..."
              \$S verify
              echo "[+] ${TARGET_NODES}-Node Oracle Cloud OKE Synthesis Run Completed Successfully!"
          resources:
            requests: { cpu: "500m", memory: "1Gi" }
            limits:   { cpu: "1", memory: "2Gi" }
EOF

echo "================================================================="
echo "  Streaming Live Cluster Execution Logs"
echo "================================================================="
kubectl wait --for=condition=Ready pod -l job-name=specsynth-run --timeout=120s 2>/dev/null || true
kubectl logs -f job/specsynth-run

echo ""
echo "================================================================="
echo "  Benchmark Complete! Initiating automatic zero-cost teardown..."
echo "================================================================="
