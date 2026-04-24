#!/usr/bin/env bash
# Video Archive Pipeline — Ubuntu Bootstrap
# Run this once on a fresh Ubuntu machine to install Docker and build the image.
# Tested on Ubuntu 22.04 LTS and 24.04 LTS (amd64).

set -euo pipefail

PIPELINE_DIR="$(cd "$(dirname "$0")/video_pipeline" && pwd)"

print_step() { echo ""; echo "▶ $1"; }
ok()         { echo "  ✓ $1"; }

# ── 1. Docker ─────────────────────────────────────────────────────────────────
print_step "Checking Docker..."
if command -v docker &>/dev/null && docker info &>/dev/null; then
    ok "Docker is already installed and running."
else
    echo "  Installing Docker CE via get.docker.com..."
    curl -fsSL https://get.docker.com | sudo sh
    sudo usermod -aG docker "$USER"
    ok "Docker installed."
    echo ""
    echo "  ⚠  You were added to the 'docker' group."
    echo "     Run the following so the change takes effect without logging out:"
    echo ""
    echo "       newgrp docker"
    echo ""
    echo "     Then re-run this script."
    exit 0
fi

# ── 2. Directories ────────────────────────────────────────────────────────────
print_step "Creating input/output directories..."
mkdir -p "$PIPELINE_DIR/input" "$PIPELINE_DIR/output"
ok "Directories ready."

# ── 3. .env ───────────────────────────────────────────────────────────────────
print_step "Checking .env file..."
if [ ! -f "$PIPELINE_DIR/.env" ]; then
    cp "$PIPELINE_DIR/.env.example" "$PIPELINE_DIR/.env"
    ok ".env created from .env.example"
else
    ok ".env already exists — skipping."
fi

# ── 4. Build image ────────────────────────────────────────────────────────────
print_step "Building Docker image..."
echo "  This downloads the faster-whisper large-v3 model (~3 GB) on first build."
echo "  Subsequent builds use Docker's layer cache and are fast."
echo ""
cd "$PIPELINE_DIR"
docker compose build

# ── 5. Done ───────────────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Setup complete."
echo ""
echo "  Drop MP4 files into:  video_pipeline/input/"
echo "  Transcripts appear in: video_pipeline/output/"
echo ""
echo "  Start the service:"
echo "    cd video_pipeline && docker compose up -d"
echo ""
echo "  Batch-process all MP4s in input/:"
echo "    cd video_pipeline && bash process_batch.sh"
echo ""
echo "  Or point at a different directory:"
echo "    cd video_pipeline && bash process_batch.sh /mnt/ssd/marks_videos"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
