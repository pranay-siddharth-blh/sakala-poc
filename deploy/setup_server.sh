#!/usr/bin/env bash
# One-time server setup for the Sakala WhatsApp POC + Mitra on Ubuntu (run as the ubuntu user with sudo).
# Expects /tmp/sakala_bundle.tar.gz (code + data) and /tmp/sakala.env (Gemini-only settings) uploaded first.
# Usage: bash setup_server.sh <host> <access-code>        host = 43-204-232-126.sslip.io
set -euo pipefail
HOST="$1"; CODE="$2"
TOKEN="$(head -c 24 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 32)"

echo "== packages"
sudo apt-get update -qq
sudo apt-get install -y -qq caddy curl ca-certificates sqlite3 >/dev/null

echo "== service user and folders"
id sakala >/dev/null 2>&1 || sudo useradd --system --create-home --home-dir /opt/sakala --shell /usr/sbin/nologin sakala
sudo mkdir -p /opt/sakala
sudo tar -xzf /tmp/sakala_bundle.tar.gz -C /opt/sakala
sudo install -m 600 /tmp/sakala.env /opt/sakala/app/.env
sudo chown -R sakala:sakala /opt/sakala

echo "== Python 3.11 (same as the laptop, so the trained model loads unchanged)"
if [ ! -x /opt/sakala/venv/bin/python ]; then
  curl -LsSf https://astral.sh/uv/install.sh | sudo env UV_INSTALL_DIR=/usr/local/bin sh >/dev/null
  sudo env UV_PYTHON_INSTALL_DIR=/opt/sakala/.python uv venv --python 3.11 /opt/sakala/venv
fi
sudo env UV_PYTHON_INSTALL_DIR=/opt/sakala/.python VIRTUAL_ENV=/opt/sakala/venv uv pip install --python /opt/sakala/venv/bin/python -q -r /opt/sakala/deploy/requirements.txt
sudo chown -R sakala:sakala /opt/sakala

echo "== services"
sudo cp /opt/sakala/deploy/sakala-poc.service /opt/sakala/deploy/mitra.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now sakala-poc.service mitra.service

echo "== HTTPS + access gate"
sudo mkdir -p /opt/sakala/gate && sudo cp /opt/sakala/deploy/gate/index.html /opt/sakala/gate/index.html
sed -e "s/__HOST__/$HOST/g" -e "s/__CODE__/$CODE/g" -e "s/__TOKEN__/$TOKEN/g" /opt/sakala/deploy/Caddyfile.template | sudo tee /etc/caddy/Caddyfile >/dev/null
sudo caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile >/dev/null
sudo systemctl enable caddy >/dev/null 2>&1 || true
sudo systemctl reload-or-restart caddy

echo "== done"
for p in 8020 8030; do printf "port %s: %s\n" "$p" "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:$p/api/health)"; done
