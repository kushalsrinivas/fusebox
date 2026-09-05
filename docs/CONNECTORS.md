# Connectors

## Feedback in
- **API/SDK:** `POST /v1/feedback` with `X-API-Key`. Returns `202 {event_id}`.
- **CSV:** `POST /v1/feedback/csv` (multipart `file`, columns `title,body,type[,app_version]`).
- **Zendesk/Intercom/Slack:** point webhooks at `POST /v1/webhooks/{source}` with the tenant key.
- **Sentry:** Settings → Integrations → Outbound webhook to `POST /v1/webhooks/sentry`
  (same key header). Issue-alert payloads are fingerprinted into error groups;
  historical export goes to `POST /v1/telemetry/errors/batch` (≤500/batch).

## Code in
- **GitHub:** webhook `push` → `POST /v1/webhooks/github` (set `GITHUB_WEBHOOK_SECRET`
  to enforce HMAC). Manual sync: `POST /v1/repos/sync {"repo_url": "<clone-url>"}`.
  Full GitHub-App OAuth + installation tokens is the prod upgrade; the webhook
  path works without it.
- **`.pilignore`:** repo-root file merged over built-ins (`.git`, `node_modules`,
  `dist`, …). Syntax: blank lines/`#` comments, `dir/` prefixes, `*.ext` globs,
  exact rel paths. Example:
  ```
  archive/
  *.log
  vendor/large-fixture.json
  ```

## Telemetry (roadmap)
Grafana/Loki/CloudWatch stay query-time: store per-tenant creds in the
connector record, the agent calls them through MCP tools, and only the
returned evidence window is persisted. ClickHouse replaces
`error_occurrences` at scale with the same row shape.

## Billing (Stripe)
1. Create Prices for `pro` / `enterprise`, set `STRIPE_SECRET_KEY`,
   `STRIPE_PRICE_PRO`, `STRIPE_PRICE_ENTERPRISE`, `STRIPE_WEBHOOK_SECRET`.
2. `POST /v1/billing/checkout {"plan": "pro"}` → hosted URL (tenant_id in metadata).
3. `checkout.session.completed` → `POST /v1/webhooks/stripe` flips the plan.
Without keys, checkout returns 501 with setup notes; use `POST /v1/admin/plan`
(`PIL_ADMIN_KEY`) for dev/self-hosted.
