# syntax=docker/dockerfile:1.7
# zer0one-cinema worker — Blender 4.2 LTS + zer0one-cinema CLI
#
# Base image is plain ubuntu:22.04 because the v0.1 model-prep pipeline is
# CPU-only (mesh geometry + material analysis, no rendering). GPU support
# (nvidia/cuda base + OptiX) arrives with v0.3 when we ship actual Cycles
# rendering. Keep the image thin for fast RunPod cold-starts.
#
# Design: zer0one-cinema is installed directly into Blender's bundled Python
# (3.11 in Blender 4.2). No system Python venv needed — Blender loads its own
# interpreter, and the package + its deps sit alongside bpy.
#
# Build:   docker build -f Dockerfile -t ghcr.io/0xxcool/zer0one-cinema-worker:v0.1.1 .
# Run:     docker run --rm -v /host/path:/workspace ghcr.io/0xxcool/zer0one-cinema-worker:v0.1.1 \
#              zocinema model-prep car.glb --output car_prepped.blend --report report.json
FROM ubuntu:22.04

ARG BLENDER_VERSION=4.2.11
ARG BLENDER_MAJOR=4.2
ARG ZOCINEMA_VERSION=0.1.1

ENV DEBIAN_FRONTEND=noninteractive \
    BLENDER_VERSION=${BLENDER_VERSION} \
    BLENDER_MAJOR=${BLENDER_MAJOR} \
    ZOCINEMA_VERSION=${ZOCINEMA_VERSION} \
    ZOCINEMA_HOME=/opt/zocinema \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System packages: minimum X/GL/font libraries Blender needs even in headless
# mode (the linker resolves them at import time regardless of --background).
RUN apt-get update && apt-get install -y --no-install-recommends \
        wget xz-utils ca-certificates \
        libxi6 libxxf86vm1 libxfixes3 libxrender1 libxkbcommon0 \
        libgl1 libglu1-mesa libsm6 libxext6 \
        libxml2 libfreetype6 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/* /var/cache/apt/*

# Blender 4.2 LTS — official tarball, extracted to /opt/blender
RUN wget -qO /tmp/blender.tar.xz \
        "https://download.blender.org/release/Blender${BLENDER_MAJOR}/blender-${BLENDER_VERSION}-linux-x64.tar.xz" \
    && mkdir -p /opt/blender \
    && tar -xJf /tmp/blender.tar.xz -C /opt/blender --strip-components=1 \
    && rm /tmp/blender.tar.xz \
    && ln -s /opt/blender/blender /usr/local/bin/blender

# Install zer0one-cinema into Blender's bundled Python (3.11).
# ensurepip is needed because Blender ships without pip by default.
RUN BLENDER_PY=$(ls /opt/blender/${BLENDER_MAJOR}/python/bin/python3.*) \
    && $BLENDER_PY -m ensurepip \
    && $BLENDER_PY -m pip install --no-cache-dir --upgrade pip \
    && $BLENDER_PY -m pip install --no-cache-dir "zer0one-cinema==${ZOCINEMA_VERSION}"

COPY docker/blender_bootstrap.py ${ZOCINEMA_HOME}/bootstrap.py

# Wrapper: `zocinema <args>` → `blender -b -P bootstrap.py -- <args>`
RUN printf '#!/bin/bash\nset -e\nexec blender -b -P %s/bootstrap.py -- "$@"\n' \
        "${ZOCINEMA_HOME}" > /usr/local/bin/zocinema \
    && chmod +x /usr/local/bin/zocinema

WORKDIR /workspace
CMD ["zocinema", "--help"]
