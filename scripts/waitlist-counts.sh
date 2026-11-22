#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

docker --context desktop-linux compose -f compose.yaml -f compose.local.yaml \
    exec -T db psql -X -v ON_ERROR_STOP=1 -P pager=off -U iptv_app -d iptv_dev <<'SQL'
WITH markets(country, market) AS (
    VALUES ('US', 'United States'), ('NG', 'Nigeria')
)
SELECT markets.market, count(launch_interest.country) AS signups
FROM markets
LEFT JOIN launch_interest ON launch_interest.country = markets.country
GROUP BY markets.country, markets.market
ORDER BY markets.country DESC;
SQL
