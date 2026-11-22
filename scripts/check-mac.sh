#!/usr/bin/env bash
set -euo pipefail
printf 'Computer architecture: '; uname -m
printf '\nDocker client:\n'
if ! command -v docker >/dev/null 2>&1; then
  echo 'Docker is not installed. Install Docker Desktop for Mac first.'
  exit 1
fi
docker --version
docker compose version
printf '\nDocker engine:\n'
if docker info --format '{{.ServerVersion}}' >/dev/null 2>&1; then
  echo 'Docker engine is running.'
else
  echo 'Start Docker Desktop and retry.'
  exit 1
fi
