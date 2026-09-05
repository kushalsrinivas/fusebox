# Fusebox

Phase 0 skeleton. See `ARCHITECTURE.md` (how) + `PHASED_PLAN.md` (when/what).

## Quickstart (local, no cloud)

```bash
# 1. infra
docker compose up -d postgres redis redpanda
# 2. api
cd apps/api && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head  # or: psql $DATABASE_URL -f migrations/001_init.sql
uvicorn app.main:app --reload --port 8000
# 3. web
cd apps/web && npm install && npm run dev
# 4. demo
curl -X POST localhost:8000/v1/feedback \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: dev-key' \
  -d '{"source":"sdk","title":"checkout crash on pay","body":"taps pay, app closes","app_version":"1.4.2"}'
open http://localhost:3000
```

Demo tenant api key: `dev-key` → `tenant_id 00000000-0000-0000-0000-000000000001`.

## Layout

- `apps/api` — FastAPI gateway (feedback, repos/code-search, telemetry/deploys, clusters/investigations)
- `workers/ingest` — normalize/redact/group feedback (`group_feedback` → clusters)
- `workers/indexer` — repo chunk/embed/search lib (`make index-demo`, `make eval-code`)
- `workers/correlation` — spike → suspect-deploy ranker (pure, tested)
- `workers/graph` — knowledge graph (file-backed; Neo4j later)
- `workers/action` — fix pipeline: validate → sandbox → risk → draft PR (`make eval-actions`)
- `workers/verify` — post-deploy verdicts from error deltas
- `workers/insights` — feature-request digest for PMs
- `workers/agent` — LangChain + LangGraph investigator + deterministic `runner` (`make agent`, `make eval-investigations`)
- `workers/billing` — plans, quotas, Stripe checkout/webhook helpers
- `docs/` — API reference, connector setup, operations runbooks
- `scripts/load_test.py` — stdlib load generator (`make load-test`)
- `apps/web` — Next.js inbox (list/detail/CSV import)
- `packages/shared` — canonical event JSON schema + TS types
- `infra/` — docker-compose (local) + terraform stub (AWS)
