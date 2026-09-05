# Operations

## Deploy
`docker compose up -d postgres redis redpanda` → apply `apps/api/migrations/*.sql`
in order → `make api` / `make web`. Terraform in `infra/terraform/envs/dev` is a
stub until the first prod cut (RDS + Fargate + S3 + Secrets).

## Backup & restore (drill)
1. Postgres: `pg_dump $DATABASE_URL` nightly; restore to staging monthly.
2. Derived stores are disposable: delete any `PIL_INDEX_ROOT/<tenant>`,
   re-run `POST /v1/admin/replay` — index + clusters + graph rebuild from source.
   CI covers the wipe-and-restore path (`test_replay_restores_wiped_index`).
3. Raw payloads: S3 lakehouse (arch §4.4) replaces local disk in prod.

## Quotas & rate limits
- Plans: free 500/50/20, pro 50k/5k/1k (feedback/investigations/actions).
  Metered at ingest/investigate/propose; 429 carries limits + upgrade hint.
- Global per-key rate limit: `PIL_RATE_LIMIT`/min (default 1000, Redis in prod).

## Privacy & deletion
- PII is redacted before embedding; raw logs need `pii_access` (roadmap role).
- Tenant erasure: `DELETE /v1/admin/tenants/{id}` purges Postgres rows across all
  13 tables plus index/graph/cache dirs, and writes an audit entry. Covered by
  `test_purge_removes_all_tenant_data`. S3 tombstones + KMS rotation are the prod
  additions; use this endpoint's output as the DPA evidence artifact.

## Incidents
- Ingest p95 > 2s → check Redpanda lag, then Postgres connections.
- Investigation p50 > 3min → check tool-call depth cap (12) and index size.
- Poison events land in DLQ/S3 quarantine; replay after fix, never blocking.

## Load test
`make load-test` (needs `make api` running): default 5 tenants × 40 events.
Measured locally (2026-09-05, MacBook, memory stores): 60 events, 60/60
accepted, p50=0.013s, p95=0.069s. Tune sampling/caching before touching
instance sizes.
