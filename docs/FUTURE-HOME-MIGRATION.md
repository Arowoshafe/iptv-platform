# Future AWS -> In-House Ryzen Migration (do NOT perform yet)

### What stays consistent

Source repository, Linux/amd64 Docker image, FastAPI APIs, PostgreSQL schema, licensed provider adapter, signed session logic and client applications. DNS and environment settings change; applications should not contain fixed AWS resource addresses.

### What requires replacement or retention

- ECS Fargate -> local Docker Compose / Linux container host on Windows (Docker Desktop WSL 2) or preferably a dedicated Linux installation for 24/7 uptime.
- RDS -> self-hosted PostgreSQL (encrypted backups, tested recovery, storage and patch management). Option: keep RDS in AWS and host only the API at home, but hybrid latency/cost/security need assessment.
- Secrets Manager/Cognito and other AWS-dependent identity services -> either stay on AWS or be intentionally replaced. Merely relocating Docker images does not eliminate all AWS dependencies.
- ALB/WAF/CloudFront -> secure reverse proxy + firewall + DNS, and provider-hosted licensed video delivery. A CDN may remain useful even if the API moves.

### Controlled migration checklist

1. Inspect contracts: licensed provider permits your new origin/network and any geo-specific delivery.
2. Provision a dedicated home host, UPS, reliable wired network, fixed LAN address and secured off-site backup.
3. Configure dual-stack IPv4/IPv6 reachability or an approved secure reverse proxy; verify ISP terms, CGNAT, and upload/latency reliability. Do not publish PostgreSQL (5432).
4. Install Docker Linux container support and the **same tested application image**; verify environment variables, secrets and database migrations.
5. Prepare a target PostgreSQL instance on a compatible major version; run `pg_dump -Fc` from source and `pg_restore` at target during an approved maintenance window. This is a logical migration and often requires a write freeze and downtime; snapshot/restore alone is not directly portable to an on-premise PostgreSQL server.
6. Validate accounts, entitlements, rights enforcement, audit logs and playback using only licensed test content.
7. Reduce DNS TTL before planned cutover; switch HTTPS routing and monitor; retain AWS rollback route for a defined window.
8. Keep tested off-site backups and consider continuing to use AWS for redundancy.

**Important:** Do not copy Docker named volumes between macOS, Linux EC2 and Windows. Export PostgreSQL data logically, test restore, and confirm secrets and app configuration separately. This guide is a plan, not an executed migration.
