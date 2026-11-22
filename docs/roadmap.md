# Roadmap with go/no-go gates

**Phase 0 (Weeks 1–3): Commercial feasibility and rights**
- Choose brand and confirm trademark / domain / app-handle availability.
- Contact SoFast, MwareTV, FAST Channels TV, Vubiquity with `supplier-rfq.md`.
- Have a qualified legal adviser evaluate US streaming rights and Nigeria NBC licence classification for the actual business model.
- GATE: don't commit to commercial channel resale until written rights and market-specific licensing structure are defensible.

**Phase 1 (Weeks 2–4): Local prototype and AWS foundation**
- Run local web + FastAPI starter, document channels and rights models.
- Create separate AWS dev/prod accounts or isolation, enable MFA, budgets, CloudTrail and roles.
- Create repo and CI, use infrastructure as code (Terraform or AWS CDK).
- Prototype AWS Cognito login, PostgreSQL schemas, backups and private secrets.

**Phase 2 (Weeks 5–7): Product backend and portal**
- Implement plans, customers, provider adapters, catalog/EPG sync and rights by country.
- Build responsive web app and admin portal with audited entitlement changes.
- Add Stripe/Paystack webhooks, retry/idempotency, refunds and subscription lifecycle.
- Run integration tests using supplier's specifically authorized sandbox feed.

**Phase 3 (Weeks 8–11): First client apps**
- Prioritize Android TV/Google TV and Android mobile with Kotlin + Media3; on Fire OS test compatibility separately.
- Develop iOS/tvOS with Swift + AVPlayer/FairPlay where DRM is needed.
- Develop Fire TV Vega OS client if targeting newer Vega models (not interchangeable with Fire OS APKs).
- Implement secure TV pairing, EPG remote navigation, favorites, playback error recovery.

**Phase 4 (Weeks 12–16+): Hardening, publishing, soft launch**
- Complete channel-by-channel rights proof, app-store payments and content docs.
- Test Nigeria/US geo entitlement, offline/reconnect, account limits, device types and adaptive bitrate.
- Run beta with a limited cohort and legally allowed channels; track rebuffering, start time, churn, refunds and support.
- Release on authorized app stores. Add Roku/Samsung/LG only when demand supports extra engineering.

**STOP conditions:** No written rights for custom-branded apps, missing U.S./Nigeria territory coverage, no signed technical test feed approval, unclear NBC category, gross margin negative after licensing and CDN, or unsupported DRM.
