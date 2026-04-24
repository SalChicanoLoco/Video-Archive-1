#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Please run as root: sudo bash scripts/bootstrap_ubuntu.sh" >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y --no-install-recommends \
  ca-certificates \
  curl \
  docker.io \
  docker-compose-plugin \
  git

systemctl enable --now docker

echo "Bootstrap complete."
echo "Next: add your user to docker group and re-login:"
echo "  sudo usermod -aG docker $SUDO_USER"
echo "Then run: bash scripts/run_stack.sh"
