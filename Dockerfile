# =============================================================================
# Stage 1: Build & Dependency Wheel Stage
# =============================================================================
FROM python:3.12-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

ARG STORAGE_DRIVERS=""
WORKDIR /build

COPY requirements.txt pyproject.toml README.md ./
COPY specsynth.py ./
COPY specsynth/ specsynth/

RUN pip install --no-cache-dir --prefix=/install \
    -r requirements.txt \
    ${STORAGE_DRIVERS} \
    .

# =============================================================================
# Stage 2: Minimal Hardened Runtime Stage
# =============================================================================
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH="/app"

WORKDIR /app

# Copy all installed packages and CLI binaries directly into system Python
COPY --from=builder /install /usr/local

COPY specsynth.py .
COPY specsynth/ specsynth/

# Ensure specsynth is universally importable from any working directory
RUN ln -sf /app/specsynth /usr/local/lib/python3.12/site-packages/specsynth

ENTRYPOINT ["python", "/app/specsynth.py"]
