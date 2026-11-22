#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -e .env ]]; then
  echo 'Existing .env preserved. No credentials changed.'
  exit 0
fi
command -v openssl >/dev/null || { echo 'openssl not found'; exit 1; }
PASSWORD="$(openssl rand -hex 24)"
printf 'APP_NAME=YOUR IPTV BRAND\nPOSTGRES_PASSWORD=%s\n' "$PASSWORD" >.env
chmod 600 .env
echo 'Created a private .env with a random local PostgreSQL password.'
