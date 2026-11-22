#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
export LC_ALL=C
context="${1:-desktop-linux}"
if [[ $# -gt 0 ]]; then
    shift
fi
if [[ $# -eq 0 ]]; then
    set -- -f compose.yaml -f compose.local.yaml
fi
compose=(docker --context "$context" compose "$@")

batch="$(mktemp)"
trap 'rm -f "$batch"' EXIT

{
    cat <<'SQL'
-- Serialize schema changes for this application within the database.
SELECT pg_advisory_xact_lock(712014, 1);
CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    checksum TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
SQL
    for migration in database/migrations/*.sql; do
        version="${migration##*/}"
        if [[ ! "$version" =~ ^[0-9]{3}_[a-z0-9_]+\.sql$ ]]; then
            echo "Invalid migration filename: $version" >&2
            exit 1
        fi
        digest="$(openssl dgst -sha256 < "$migration")"
        checksum="${digest##* }"
        if [[ ! "$checksum" =~ ^[a-f0-9]{64}$ ]]; then
            echo "Could not compute migration checksum: $version" >&2
            exit 1
        fi

        cat <<SQL
SELECT EXISTS (
    SELECT 1 FROM schema_migrations WHERE version = '$version'
) AS already_applied,
NOT EXISTS (
    SELECT 1 FROM schema_migrations WHERE version = '$version' AND checksum <> '$checksum'
) AS checksum_matches
\gset
\if :checksum_matches
\else
\echo Checksum mismatch for $version
DO \$\$ BEGIN RAISE EXCEPTION 'A previously applied migration changed'; END \$\$;
\endif
\if :already_applied
\echo Already applied $version
\else
\echo Applying $version
SQL
        cat "$migration"
        printf '\n'
        cat <<SQL
INSERT INTO schema_migrations (version, checksum) VALUES ('$version', '$checksum');
\endif
SQL
    done
} > "$batch"

"${compose[@]}" exec -T db psql -X -v ON_ERROR_STOP=1 \
    --single-transaction -U iptv_app -d iptv_dev -f - < "$batch"
