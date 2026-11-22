#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
context="${1:-default}"
project="iptv-test-$(openssl rand -hex 8)"
POSTGRES_PASSWORD="$(openssl rand -hex 24)"
export POSTGRES_PASSWORD
compose=(docker --context "$context" compose --env-file /dev/null
    --project-name "$project" -f compose.yaml -f compose.test.yaml)

cleanup() {
    result=$?
    trap - EXIT
    if ! "${compose[@]}" down --volumes; then
        echo "Cleanup failed for temporary project: $project" >&2
        if [[ "$result" -eq 0 ]]; then
            result=1
        fi
    fi
    exit "$result"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

echo "Starting disposable database in $project"
"${compose[@]}" up -d --wait --wait-timeout 120 db

migration_args=("$context" --env-file /dev/null --project-name "$project"
    -f compose.yaml -f compose.test.yaml)
bash scripts/migrate-db.sh "${migration_args[@]}"
applied="$(bash scripts/migrate-db.sh "${migration_args[@]}")"
printf '%s\n' "$applied"
for migration in database/migrations/*.sql; do
    if ! grep -Fxq "Already applied ${migration##*/}" <<< "$applied"; then
        echo "Migration was not recorded: $migration" >&2
        exit 1
    fi
done

psql=("${compose[@]}" exec -T db psql -X -v ON_ERROR_STOP=1
    --single-transaction -U iptv_app -d iptv_dev -f -)
"${psql[@]}" < database/test-fixtures.sql

"${compose[@]}" run --build --rm --no-deps \
    -v "$PWD/backend/tests:/app/tests:ro" \
    api python -m pytest -q -p no:cacheprovider tests
