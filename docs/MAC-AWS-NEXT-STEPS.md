# MacBook + AWS Build Plan

## Current ground truth

Starter runs locally: demo FastAPI, an example PostgreSQL schema, fabricated channels, web catalog, `POST /api/v1/playback/session` always returns 403. **No verified IPTV cloud deployment exists in the project evidence.** Reuse AWS infrastructure only after reading its inventory. Do not conflate existing resources with other projects.

## Development workflow

- Keep source files, Dockerfile, schema migrations and infrastructure-as-code in a Git repo.
- Keep secrets out of Git, app images and source control. `.env` is gitignored. AWS IAM role-based access is preferred over long-lived keys.
- Docker Compose is your **local** and eventual home-server runtime. In AWS, use the same built application container image via ECR and ECS Fargate, or an already-provisioned EC2 server if suitable.
- Containerize Python API; never bake hostname/IP/password into code. `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` and auth config should come from environment or Secrets Manager.
- Database layer: PostgreSQL local -> RDS PostgreSQL cloud -> Dockerized PostgreSQL on home server if you later choose; use Alembic for schema changes and backup/restore tests.
- IP rights: the catalog must resolve an actual commercial channel-rights record by jurisdiction, subscription plan and device, not just accept the user's requested `country` query parameter. Playback remains denied until those gates exist.

## AWS deployment prerequisites (NOT satisfied by this demo)

1. Verify the AWS account, IAM permissions, region, existing VPC/networking, compute, RDS, ECR, domain and budget alarms.
2. Implement production authentication and admin roles. Add API-side ownership checks, signed/expiring sessions, rate limiting, audit trail and protected admin tools.
3. Add verified Stripe/Paystack webhooks for subscription entitlements. Keep real payment information at the processor, not in your database.
4. Obtain written authorized wholesale rights and provider API documentation for both US and Nigeria; implement server-side territory checks based on reliable signals and licensing contracts. No real TV content in this starter.
5. Create an ECR image repository, private ECS service/task for `linux/amd64` or multi-arch images, ALB or ingress with HTTPS, Secrets Manager and CloudWatch logs. Use RDS PostgreSQL on a private network; do not expose the database or API demo ports to the internet.
6. Configure domains, TLS, backups, deployment rollback and staged monitoring. Harden and review the application before any real account or payment is allowed.
7. Promote an image from the private test environment into production after tests and approval. Avoid using the local Compose `.env` password in AWS.

## Commands now (read-only)

```bash
aws sts get-caller-identity
aws configure list
bash scripts/check-aws.sh
```

## Building an architecture-portable app image

Run on the Mac from the project root (this does **not** publish to AWS):

```bash
docker buildx build --platform linux/amd64 -t iptv-api:dev-amd64 --load ./backend
```

If you deploy to another architecture, build a compatible image (or multi-architecture manifest) first. Apple Silicon local builds can default to arm64, while a Ryzen server normally uses amd64.

## Suggested next actual engineering sprint

1. Set up a source repository for this project and automated lint/tests.
2. Add Alembic migrations (not hand-edited production `init.sql`).
3. Add external identity provider integration (Cognito) and secure session validation.
4. Build your subscriber, plan, device and administrative APIs using database records.
5. Add mock payment events and signed webhook verification tests; only then real payments.
6. Implement licensed supplier adapter interface and entitlement tests by country (US/NG), content rights, plan, device, concurrency and expiry.
7. Build TV app and mobile app clients for the secured API.

## Useful official references

- AWS ECS Fargate: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/getting-started-fargate.html
- Docker Compose production overrides: https://docs.docker.com/compose/how-tos/production/
- PostgreSQL migration: https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/PostgreSQL.Procedural.Importing.html
