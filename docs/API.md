# API reference (v0.6)

Auth: `X-API-Key: <tenant key>` (`dev-key` locally). Admin: `X-Admin-Key: $PIL_ADMIN_KEY`.
Over-quota → `429 {error, kind, limit, used, plan}`. Rate-limited → `429 + X-RateLimit-Remaining`.

| Method & path | Purpose |
|---|---|
| GET /healthz | liveness (unlimited) |
| POST /v1/feedback · GET /v1/feedback · POST /v1/feedback/csv | feedback ingest/list (metered) |
| POST /v1/webhooks/{sentry,github,stripe,zendesk,…} | source webhooks |
| POST /v1/repos/sync · GET /v1/repos · GET /v1/code/search | codebase index |
| POST /v1/deploys · GET /v1/deploys · GET /v1/errors/groups · POST /v1/telemetry/errors/batch | observability |
| GET /v1/correlate?service=&spike_start= | suspect deploys |
| POST /v1/clusters/rebuild · GET /v1/clusters[/{id}] · POST /v1/clusters/{id}/investigate | intelligence |
| POST /v1/graph/rebuild · GET /v1/graph/timeline | knowledge graph |
| POST /v1/actions/propose · GET /v1/actions[/{id}] · POST /v1/actions/{id}/approve · POST /v1/actions/{id}/verify · GET /v1/verifications | actions |
| GET /v1/insights/digest · GET /v1/insights/proposals · GET /v1/metrics/summary | insights |
| POST /v1/investigations/{id}/feedback · GET /v1/signals/summary | learning signals |
| GET /v1/billing/status · POST /v1/billing/checkout · GET /v1/audit | billing/audit |
| GET /v1/onboarding/status · POST /v1/onboarding/demo | onboarding |
| POST /v1/admin/plan · DELETE /v1/admin/tenants/{id} · POST /v1/admin/replay | admin |
