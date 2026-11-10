# One image for client, scheduler and workers (Dask requires matching versions).
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
ARG STORAGE_DRIVERS="s3fs gcsfs adlfs"
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt ${STORAGE_DRIVERS}
COPY specsynth.py .
COPY specsynth/ specsynth/
ENTRYPOINT ["python", "/app/specsynth.py"]
