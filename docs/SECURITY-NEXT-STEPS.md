# Security gates before any public subscribers

This development project has **no login**, **no payment processing**, **no real licensed channels**, **no playable video**, and **no production API security**. It is safe to run as a local demonstration but is NOT ready for internet exposure.

- Keep the database private on the Compose network. Never publish TCP 5432.
- Do not configure router forwarding (port 8000/5432), DMZ, or UPnP rules.
- Bind API to loopback for Day 1. For LAN-only testing, bind to a trusted LAN IP and restrict Windows Defender Firewall to the local subnet/private profile.
- Production: authentication (e.g., Cognito/OIDC), role-based authorization, verified subscriptions/entitlements, geo-licensed access, device and concurrency limits, provider-signed playback tokens, DRM, short-lived access tokens, rate limits, secure cookie/cors policy, server logs with redacted PII, webhook verification, and audited payment state.
- Keep signed rights contracts and add per-channel US/NG territory and per-device permissions.
- Public deployment needs TLS, an ingress/reverse proxy or an appropriately protected tunnel, DDoS mitigation, structured backups, patching, alerting, availability planning, privacy policy, support and recovery procedures. A Cloudflare Tunnel does NOT replace app authentication and is not automatically appropriate for licensed video delivery.
- Do not store payment-card numbers on the server: use compliant hosted checkout providers and verify webhooks server-side.
- Protect the .env file. Rotate the database password if it is leaked. Do not paste secrets into chat.
- Windows desktop + Docker Desktop depend on an active host with working networking and supported OS. Consider a dedicated Linux host/UPS and cloud failover for a real 24/7 customer service.
