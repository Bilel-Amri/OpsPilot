# OpsPilot demo image (S1 laboratory incident generator — NOT the project backend).
# See demo-app/app.py header for the scenario behaviors and the rationale for
# using a (tiny) FastAPI app per spec §17.2 (S1: "Cluster Kind, application FastAPI, SC-01").
#
# Base image choice: python:3.12-slim keeps the image small and matches the
# project's Python >= 3.11 requirement (spec §4.4). Freeze/verify the digest at
# the first successful build (G0 passes) if reproducibility requires it.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app.py /app/app.py

# The container runs as root only because kind + local lab; do not reuse this
# pattern outside the laboratory. (Lab-only, synthetic workloads — spec §15.4.)
EXPOSE 8080

# SCENARIO is provided by each scenario manifest (healthy / crashloop / oom).
CMD ["python", "app.py"]
