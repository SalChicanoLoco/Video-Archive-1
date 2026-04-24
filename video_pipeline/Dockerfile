# Dockerfile
#
# This multi-stage Dockerfile builds a CPU‑only video processing service
# based on Python 3.11. The first stage installs system and Python
# dependencies, preloads the faster‑whisper model and builds the
# application. The final stage copies only the necessary files into a
# slim runtime image and runs the Flask API behind gunicorn. The build
# targets both amd64 and arm64 (Apple Silicon) via buildx.

#### Stage 1 – builder ####
# Use slim Debian base to minimise size. The python:3.11‑slim‑bookworm
# image includes Python but excludes many common utilities, so we install
# only what we need. See the UnderHost article for installing ffmpeg on
# Debian using apt【308060662158292†L187-L199】.
FROM --platform=$BUILDPLATFORM python:3.11-slim-bookworm AS builder

# Avoid prompts during apt installs
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies:
#  - ffmpeg: for video/audio processing【308060662158292†L187-L199】
#  - git: may be useful for future extensions
#  - curl: used by test script to download sample videos
#  - build-essential: required for compiling Python wheels
#  - libsndfile1: required by pydub and soundfile to read audio formats【321951324672017†L49-L64】
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ffmpeg \
       git \
       curl \
       build-essential \
       libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Install Python dependencies. We copy requirements separately to leverage
# Docker layer caching; subsequent changes to source files will not
# invalidate this step. All versions are pinned to ensure reproducible
# builds; versions were obtained from official PyPI pages (see
# citations in README).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY app/ /app/app/

# Preload the Whisper model during build so that the runtime does not
# download weights on first request. The faster‑whisper library uses
# CTranslate2 to load the model and will fetch the model from
# Hugging Face if it isn't present. Setting XDG_CACHE_HOME ensures
# model files are stored in our persistent volume (/app/models). We
# download the large‑v3 model because it offers high accuracy yet
# remains under 4 GB when quantised. We rely on the faster‑whisper
# API, which allows specifying beam size and VAD filtering during
# transcription【904580658027665†L227-L239】【904580658027665†L303-L320】.
ENV XDG_CACHE_HOME=/app/models
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('large-v3', device='cpu')"


#### Stage 2 – runtime ####
# Start from a clean slim image. We reuse the same base to avoid
# unnecessary layers.
FROM python:3.11-slim-bookworm AS runtime

ENV DEBIAN_FRONTEND=noninteractive

# Reinstall run‑time tools only (ffmpeg and libsndfile1) because they
# were installed in the builder but not copied here. We omit build
# tools to minimise the final image size.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ffmpeg \
       libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Create a non‑root user to run the service. Running as non‑root is a
# security best practice. The user will own the application files and
# directories so volumes mount correctly.
RUN useradd -m -d /home/pipeline pipeline

# Set working directory
WORKDIR /app

# Copy Python dependencies from builder
COPY --from=builder /usr/local/lib/python3.11 /usr/local/lib/python3.11
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy the predownloaded Whisper model from the builder. This ensures
# the model cache is present in the final image and persists to the
# /app/models volume mounted via docker‑compose.
COPY --from=builder /app/models /app/models

# Copy application source
COPY app/ /app/app/

# Copy entrypoint script and test script if present
COPY test_pipeline.sh /app/test_pipeline.sh

# Make test script executable
RUN chmod +x /app/test_pipeline.sh

# Copy requirements file for reference (not used at runtime)
COPY requirements.txt /app/requirements.txt

# Ensure correct ownership for the pipeline user
RUN chown -R pipeline:pipeline /app

# Expose Flask port
EXPOSE 5000

# Switch to non‑root user
USER pipeline

# Default command runs gunicorn with multiple threads. We set
# `--access-logfile -` and `--error-logfile -` to send logs to
# stdout/stderr for Docker log collection. The app object is
# available in app/app.py as "app". Gunicorn will manage worker
# processes and threads.
CMD gunicorn --workers 2 --threads 4 --bind 0.0.0.0:5000 --access-logfile - --error-logfile - app.app:app