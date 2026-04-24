#!/usr/bin/env bash
# Video Archive Pipeline — Ubuntu Bootstrap
# Run this once on a fresh Ubuntu machine to install Docker, Claude Code,
# and the MCP server, then build the pipeline image.
# Tested on Ubuntu 22.04 LTS and 24.04 LTS (amd64).

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
PIPELINE_DIR="$REPO_DIR/video_pipeline"

print_step() { echo ""; echo "▶ $1"; }
ok()         { echo "  ✓ $1"; }
info()       { echo "  → $1"; }

# ── 1. Docker ─────────────────────────────────────────────────────────────────
print_step "Checking Docker..."
if command -v docker &>/dev/null && docker info &>/dev/null 2>&1; then
    ok "Docker is already installed and running."
else
    info "Installing Docker CE via get.docker.com..."
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

# ── 2. Python 3 + pip ─────────────────────────────────────────────────────────
print_step "Checking Python 3..."
if command -v python3 &>/dev/null; then
    PY_VER=$(python3 --version 2>&1)
    ok "$PY_VER"
else
    info "Installing python3-pip..."
    sudo apt-get update -qq && sudo apt-get install -y python3 python3-pip
    ok "Python 3 installed."
fi

# ── 3. Node.js (for Claude Code) ──────────────────────────────────────────────
print_step "Checking Node.js..."
if command -v node &>/dev/null; then
    ok "Node.js $(node --version)"
else
    info "Installing Node.js LTS via NodeSource..."
    curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
    sudo apt-get install -y nodejs
    ok "Node.js $(node --version) installed."
fi

# ── 4. Claude Code CLI ────────────────────────────────────────────────────────
print_step "Checking Claude Code CLI..."
if command -v claude &>/dev/null; then
    ok "Claude Code $(claude --version 2>/dev/null || echo '(installed)')"
else
    info "Installing Claude Code CLI..."
    npm install -g @anthropic-ai/claude-code
    ok "Claude Code installed."
fi

# ── 5. MCP server Python dependencies ────────────────────────────────────────
print_step "Installing MCP server dependencies..."
pip3 install -q -r "$REPO_DIR/requirements-mcp.txt" 2>/dev/null \
    || pip3 install -q "mcp[cli]>=1.9.0" pyairtable
ok "MCP dependencies ready."

# ── 6. Directories ────────────────────────────────────────────────────────────
print_step "Creating input/output directories..."
mkdir -p "$PIPELINE_DIR/input" "$PIPELINE_DIR/output"
ok "Directories ready."

# ── 7. .env ───────────────────────────────────────────────────────────────────
print_step "Checking .env file..."
if [ ! -f "$PIPELINE_DIR/.env" ]; then
    cp "$PIPELINE_DIR/.env.example" "$PIPELINE_DIR/.env"
    ok ".env created from .env.example"
    echo ""
    echo "  ⚠  Edit video_pipeline/.env and add your Airtable credentials:"
    echo "       AIRTABLE_API_KEY=pat..."
    echo "       AIRTABLE_BASE_ID=app..."
    echo ""
    echo "     Or open the setup wizard after starting the pipeline:"
    echo "       http://localhost:5000/setup"
else
    ok ".env already exists — skipping."
fi

# ── 8. Register MCP server with Claude Code ───────────────────────────────────
print_step "Registering MCP server..."
MCP_SERVER="$REPO_DIR/mcp_server.py"
MCP_JSON="$REPO_DIR/.mcp.json"
PYTHON_BIN="$(command -v python3)"

cat > "$MCP_JSON" <<JSON
{
  "mcpServers": {
    "video-archive": {
      "command": "$PYTHON_BIN",
      "args": ["$MCP_SERVER"],
      "env": {}
    }
  }
}
JSON

ok "MCP server registered at $MCP_JSON"
info "Claude Code will auto-load the video-archive tools when run in this directory."

# ── 9. Build Docker image ─────────────────────────────────────────────────────
print_step "Building Docker image..."
echo "  First build downloads faster-whisper large-v3 (~3 GB) — takes ~10 min."
echo "  Subsequent builds use Docker layer cache and are fast."
echo ""
cd "$PIPELINE_DIR"
docker compose build

# ── 10. Done ──────────────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Setup complete."
echo ""
echo "  ★  The fast path — just talk to Claude:"
echo "       cd $(basename "$REPO_DIR") && claude"
echo "       > Hey Claude, I'm ready to set up Video-Archive-1"
echo ""
echo "  Manual path:"
echo "    Start:   cd video_pipeline && docker compose up -d"
echo "    Process: cd video_pipeline && bash process_batch.sh"
echo "    Setup:   open http://localhost:5000/setup in a browser"
echo ""
echo "  Drop MP4s into: video_pipeline/input/"
echo "  Results appear: video_pipeline/output/"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
