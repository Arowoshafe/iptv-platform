# IPTV Platform — macOS Development / AWS-Ready Architecture

**Status: private development demo, NOT a licensed or production IPTV service.** This project has FastAPI, a PostgreSQL schema, and a fictional US/NG channel catalog. Playback is deliberately blocked (HTTP 403). It does not yet have customer authentication, billing, licensed TV streams, or hardened security. **Do not make it public or collect real subscriber/payment data.**

## Goal and hosting sequence

1. **MacBook**: write code, test the UI and APIs, run Docker Compose privately.
2. **AWS**: inspect the services you already have, then deploy a *separate secured staging/production stack* after implementing identity, authorization, secrets, TLS and deployment automation. Never expose this unprotected demo.
3. **Later home server**: run the same Linux container image on your Ryzen/Windows host using WSL 2 Docker, or install Linux if the server becomes dedicated; migrate PostgreSQL data using a controlled export/restore.

## Run on your Mac (Terminal)

Requirements: Docker Desktop (running), Docker Compose v2, a Terminal with `openssl` and `bash`.

```bash
cd ~/Developer/iptv-platform
bash scripts/check-mac.sh
bash scripts/setup-mac.sh
docker compose -f compose.yaml -f compose.local.yaml config --quiet
docker compose -f compose.yaml -f compose.local.yaml up -d --build
docker compose -f compose.yaml -f compose.local.yaml ps
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8000/ready
open http://127.0.0.1:8000/
```

The API is bound to **127.0.0.1 only**. No LAN, router or public exposure. The `db` container has no published database port.

For tests:

```bash
docker compose -f compose.yaml -f compose.local.yaml run --rm --no-deps \
  -v "$PWD/backend/tests:/app/tests:ro" api python -m pytest -q tests
```

Expected: **6 passed**.

Stop (keeps your DB data):

```bash
docker compose -f compose.yaml -f compose.local.yaml down
```

**Never use `down -v` unless you deliberately want to delete the database volume.**

## AWS inventory (read-only; only after you log in to the right account)

Install AWS CLI v2 if needed (official documentation: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html ). Then verify the current identity and configured region:

```bash
aws sts get-caller-identity
aws configure list
bash scripts/check-aws.sh
```

`check-aws.sh` only lists resources. It creates, updates and deletes **nothing**. Some list commands can be denied by IAM. Do not share credentials, secret access keys, account numbers or private ARNs in chat. If there are existing ECS/ECR/RDS/EC2 resources, reuse them only after checking compatibility and ownership. Existing AWS resources for unrelated applications should be kept separate.

Read `docs/MAC-AWS-NEXT-STEPS.md` and `docs/FUTURE-HOME-MIGRATION.md` before deploying.

## What this prototype cannot do yet

- No real channels, streaming rights, M3U distribution or DRM.
- No authentication, real subscribers, subscription payments or billing webhooks.
- No production TLS, application authorization, rate-limiting or security audit.
- AWS production deployment not provided as a one-click script intentionally; deploying this demo to an internet-facing address would be unsafe.
