# Target architecture

## MVP: provider-delivered licensed video, your own business backend

- Customer on web, Android TV, Google TV, Fire TV, iOS or Android signs in.
- AWS Cognito authenticates customers. TV login uses a short-lived device pairing code verified by an authenticated browser/mobile session.
- API backend (FastAPI on ECS Fargate, or Lightsail for noncommercial testing) checks account and country-based rights.
- PostgreSQL stores channels, country rights, offers, subscriber entitlements, devices and audit events.
- The licensed provider gives your server a DRM-protected playback entitlement, URL/token or approved HLS/DASH delivery endpoint.
- Only after the server verifies subscription, contractual territory, device and simultaneous-viewer limits does the app get a short-lived playback session.
- Premium DRM should use vendor or licensed DRM service with FairPlay on Apple and Widevine on Android devices when required.
- Billing events from Stripe US and Paystack Nigeria reach authenticated and signature-verified webhooks on your backend; only valid events change entitlements.

## Later: self-operated media ingest (only when contracted)

Licensed channel feed (SRT/HLS with redistribution permission) -> AWS MediaConnect / MediaLive if transcoding is needed -> MediaPackage/DRM -> CloudFront CDN -> authorized client.

Do not pay for 24/7 MediaLive processing until the contractual feed format actually requires it. Use licensed provider CDN if already included.

## Suggested production data tables

users, devices, countries, channels, channel_rights, content_contracts, bouquets, plan_products, subscriptions, subscription_entitlements, playback_sessions, payment_events, audit_events.

Store date-based contract validity; rights by country, platform, content type, permitted uses, maximum concurrent sessions and DRM requirements.

## Suggested APIs

- `GET /health`
- `GET /v1/catalog/channels` (server-filtered by verified rights context)
- `GET /v1/epg` (country/plan aware)
- `GET /v1/me/entitlements`
- `POST /v1/auth/tv/pair` and `POST /v1/auth/tv/claim` (short-lived device linking)
- `POST /v1/playback/sessions` (authorized, DRM-ready playback)
- `DELETE /v1/playback/sessions/{id}`
- `POST /v1/webhooks/stripe` and `/v1/webhooks/paystack` (verified signatures)

Neither the local demo nor these diagrams are a legal approval or a production security review.
