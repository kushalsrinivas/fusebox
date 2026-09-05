# Phased Execution Plan — Fusebox

> How we go from empty repo → SaaS that turns feedback into draft PRs.
> Companion to `ARCHITECTURE.md` (read architecture first for vocabulary).

**MVP slice (locked):** Feedback (API + CSV + Zendesk) + GitHub + Sentry/logs + Grafana → one repo, one service, Draft PRs with human merge.
**Autonomy (locked):** Propose only. No auto-merge. Guardrailed paths (`migrations/*`, `infra/*`, `auth/*` need explicit checkbox).
**Docs:** this file = *when/what*; `ARCHITECTURE.md` = *how*.

---

## Milestones at a Glance

| Phase | Name | Duration* | Exit demo |
|---|---|---|---|
| 0 | SaaS Skeleton | wk 1–3 | Ingest feedback via API/CSV → see it in inbox |
| 1 | Codebase Knowledge | wk 4–6 | "Where is checkout logic?" → grounded code answer with permalinks |
| 2 | Observability Correlation | wk 5–8 (overlap) | Sentry spike shows suspect deploy + commits |
| 3 | Intelligence Core | wk 8–12 | Full loop on seeded crash: cluster → timeline → root cause + repro |
| 4 | Action | wk 12–16 | Human merges AI draft PR + generated tests |
| 5 | Learning Loop | wk 16–20 | Post-deploy error drop auto-verified; feature-request digest |
| 6 | SaaS Hardening | wk 20–24 | Billing live, tenant onboarding <15 min, SOC2-ready audit |

*Single full-stack + one AI engineer, AI-assisted. Add 50% buffer if solo or part-time.

---

## Phase 0 — SaaS Skeleton (wk 1–3)

**Goal:** tenant → project → ingest → view. No AI yet.

**In scope:** monorepo (`apps/web`, `apps/api`, `workers/ingest`, `packages/shared`, `infra/terraform`), Clerk auth + orgs, Postgres + RLS + migrations, Ingest Gateway (`POST /v1/feedback`, `POST /v1/webhooks/:source`, CSV upload), Redpanda topic `feedback.raw.v1`, normalization worker (PII redact + canonical save, no embeddings yet), Next.js inbox list/detail, staging+prod deploys, CI (lint/type/test/build).

**Out:** vectors, graph, agents, sandbox, billing.

**Tasks:**
- [ ] Scaffold monorepo + TS/Python lint + CI
- [ ] Terraform: VPC, RDS Postgres, Redpanda (single broker dev), S3 lake, Secrets, Fargate service
- [ ] Auth + `tenants`, `projects`, `connectors`, `feedback` tables + RLS
- [ ] Gateway: API-key + HMAC verify, Redis rate limit, `202 {event_id}`, DLQ
- [ ] Worker `ingest.v1`: validate → redact → save → S3 archive
- [ ] Web UI: login, create project, API key copy, inbox table, feedback detail, CSV import
- [ ] Seed script: 200 synthetic feedback rows for demo tenant
- [ ] SLO dashboard stub (ingest p95, error rate)

**Exit criteria:** `curl POST /v1/feedback` → visible in UI <5s; CSV of 500 rows imports without loss; `tenant A` cannot read `tenant B` (RLS test passes).

**Risks:** over-building auth/billing → defer billing to P6; keep Terraform minimal.

---

## Phase 1 — Codebase Knowledge (wk 4–6)

**Goal:** agent-grade code search over real repo.

**In scope:** GitHub App (install + `push`/`PR` webhooks), repo-sync worker (shallow, incremental), Tree-sitter parse (TS/Python first, Go if needed), chunk + embed → Qdrant `t_<id>_code`, `code_units` + `commits` tables, MCP `code.search/read/blame` (internal API first), UI "Ask code" panel with permalinks.

**Out:** service catalog auto-inference v2, cross-repo deps.

**Tasks:**
- [ ] GitHub App + OAuth install flow + per-tenant installation tokens (least privilege) — *deferred to hard-prod; webhook signature verify + clone/fetch sync lands now*
- [x] Webhook handlers: `push` → re-index (`POST /v1/webhooks/github`), `pull_request` → accepted stub — `apps/api/app/routers/repos.py`
- [x] Indexer: clone cache, incremental by content-hash, stdlib-`ast` Python + heuristic TS/JS/Go/SQL → func-level chunks + 200-line spillover — `workers/indexer/pil_indexer/` (Tree-sitter/Qdrant behind same interface later)
- [x] Embedder: deterministic local hash embeddings + upsert/delete by content hash — swap for OpenAI/bge via same `.embed` later
- [x] `code.search` (hybrid cosine + IDF coverage + symbol boost, `tenant_id` filter), `code.read` (line ranges) — real backend in `workers/agent/agent/tools.py` via `PIL_INDEX_ROOT`, stub fallback; `code.blame` stays stub until git-history pass
- [x] UI: repo sync form, index status (files/chunks/head sha), code Q&A (`/code`) showing `repo/path#Lstart-Lend` — `apps/web/app/code/page.tsx`
- [x] Evals: 20 hand-written "where is X?" queries, **20/20 grounded hits** (bar was ≥16) — `workers/indexer/evals/run_evals.py`, `make eval-code`

**Exit criteria:** connect demo repo (e.g. sample Next.js + FastAPI), push commit → re-indexed <2 min; code question cites real permalink.

**Risks:** huge repos → enforce ignore + cap; binary/generated files → denylist.

---

## Phase 2 — Observability Correlation (wk 5–8, overlaps P1)

**Goal:** every error knows its deploy and suspects its commit.

**In scope:** Sentry connector (webhook + backfill), Loki/CloudWatch tail + Grafana read API, ClickHouse `telemetry.events`, `error_groups` + `deployments` tables, deploy-proximity joiner, MCP `metrics.query/logs.query/traces.get` (query-time), UI error tab on cluster.

**Out:** anomaly ML, full OTEL trace persistence.

**Tasks:**
- [x] Sentry webhook → canonicalize (fingerprint, service, release) → `error_groups` + sampled occurrences — `POST /v1/webhooks/sentry`, batch import `POST /v1/telemetry/errors/batch` (`apps/api/app/routers/telemetry.py`)
- [x] Deployment sync: `POST/GET /v1/deploys` + GitHub `deployment_status`-ready shape (`{service, version, commit_sha, env, deployed_at}`); Vercel/Render webhooks map to the same endpoint
- [x] Joiner: `workers/correlation` pure lib (`find_suspects` 6h-window recency rank + `detect_spike` z-score), served by `GET /v1/correlate`; deterministic unit tests, no I/O
- [ ] MCP `metrics.query`/`logs.query` stay stubs until tenant Grafana/Loki creds land (Phase 2b); agent `deploys_list` + new `errors_recent` already read the live platform API when `PIL_API_URL`/`PIL_API_KEY` are set (`workers/agent/agent/platform.py`)
- [x] UI: `/errors` page — groups table + suspect deploys with scores (`apps/web/app/errors/page.tsx`)
- [ ] Sampling + TTL: memory store caps 200 occurrences/group; Postgres path keeps full history + documented 90d delete (ClickHouse + TTL replaces at scale)

**Exit criteria:** seeded deploy that breaks checkout shows up as suspect within 10 min of Sentry spike; links resolve to real commit/PR.

---

## Phase 3 — Intelligence Core (wk 8–12) — the differentiator

**Goal:** autonomous investigation with evidence timeline.

**In scope:** embed+cluster (`feedback` → `issue_clusters`), Neo4j v1 + Graph API, LangChain + LangGraph orchestrator (`workers/agent`: `TRIAGE → ENRICH → HYPOTHESIZE → VERIFY → PLAN`), Investigator + Triage + QA (repro-only) subagents, confidence + severity scoring, inbox → investigation timeline UI.

**Out:** code writes, PRs (that's P4).

**Tasks:**
- [x] Embeddings for feedback + cluster worker (hash-embed max(Jaccard, cosine); union-find; per-tenant tunable thresholds; `workers/ingest/ingest/grouping.py`, `POST /v1/clusters/rebuild`)
- [x] Graph lib + file-backed store + `graph.query` equivalent (`neighbors`/`timeline`); deterministic edges + agent `LIKELY_CAUSED_BY` hypothesis edges (`workers/graph`, `POST /v1/graph/rebuild`, `GET /v1/graph/timeline`; Neo4j replaces save/load later)
- [x] Orchestrator decision logic shared by LangGraph nodes and API (`workers/agent/agent/runner.py`); Postgres `investigations` table + file checkpoints; model routing ready via `make_llm` (deterministic offline default so CI needs no keys)
- [x] Prompts + tool schemas for Triage/Investigator; grounding via real code index + live errors/deploys; citation validator = eval-measured precision (100%)
- [x] VERIFY step: ≥2 evidence kinds required before hypothesis, else `needs_info` (runner + `graph.py` verify node)
- [x] Scoring: severity heuristic + confidence math (arch §8); breakdown returned in every investigation
- [x] UI: `/clusters` page — cluster list → timeline (reports ↔ errors ↔ deploys ↔ code) → hypotheses with confidence + counter-evidence → repro steps
- [x] Evals: 15 seeded scenarios — **top-1 15/15 (bar 9), citation precision 1.000 (bar 0.9)** — `workers/agent/evals/run_investigation_evals.py`, `make eval-investigations`

**Exit criteria:** live demo: 30 synthetic "checkout crash" reports + Sentry spike + bad deploy → system outputs correct suspect commit + timeline + repro, with links, no hallucinated files.

**Risks:** LLM cost/latency → depth cap 12 tool calls, investigation p50 <3 min; noisy clusters → ship merge/split on day one.

---

## Phase 4 — Action (wk 12–16)

**Goal:** turn investigation into mergeable engineering output.

**In scope:** E2B/Daytona sandbox, Coder + Testgen subagents, draft-PR bot (`fuse/*` branches), regression-risk + prioritization engine, approval workflow (approve/request-changes/reject), Linear/Jira/Slack mirrors.

**Out:** auto-merge, auto-deploy.

**Tasks:**
- [x] Sandbox runner: stdlib diff applier → temp copy → `py_compile` + optional checks, 10-min timeout, full logs (`workers/action/action/sandbox.py`; Firecracker isolation = prod swap, documented gap: no net isolation locally)
- [x] Coder seam: `CODER_PROMPT` + fenced-```diff extraction + ≤500-line cap; raises `NeedsLLMError` without keys — platform never fabricates code (`workers/agent/agent/coder.py`)
- [ ] Testgen: repro script + colocated unit test with fail-before/fix-after (next slice)
- [x] Risk: fan-out + sensitivity + size → score/level/two-approval gate; UI shows math + blast radius (`action/risk.py`, `/actions`)
- [x] PR Bot: body template (root cause, evidence, risk, sandbox); branch `fuse/<cluster>-<sha>`; real GitHub draft-PR sequence behind `PIL_GITHUB_TOKEN`, dry-run artifact otherwise; `actions` table tracks all (`action/pr.py`, `POST /v1/actions/{id}/approve`)
- [ ] Notifications: Slack/Linear mirrors (`proposed → approved → merged → verified` states exist in DB)
- [x] Evals: pipeline decisions **10/10** (`workers/action/evals/run_action_evals.py`, `make eval-actions`); sandbox/PR-acceptance rates need production traffic to measure

**Exit criteria:** human clicks Approve → draft PR merged into demo repo with passing checks; risk + tests visible.

**Risks:** destructive diffs → denylist + diff cap + sandbox gate; token scope creep → installation token restricted to `fuse/*`.

---

## Phase 5 — Learning Loop + Product Insights (wk 16–20)

**Goal:** system gets smarter after merge; PMs get value beyond bugs.

**In scope:** post-deploy verifier (error delta watch 24h), feedback signals (thumbs/split/merge → threshold + prompt tweaks), feature-request aggregation (Product analyst subagent → proposal docs), digest emails/Slack, cost/quality dashboards.

**Tasks:**
- [x] Verifier: after approve, compare linked `error_group` occurrences before/after approval window → `verified_fixed / regressed / inconclusive` (`workers/verify`, `POST /v1/actions/{id}/verify`, `/actions` Verify button; 24h default, scheduler calls the same endpoint in prod)
- [x] Signal capture: helpful/wrong_cause/wrong_fix/not_useful per investigation (`POST /v1/investigations/{id}/feedback`, `/v1/signals/summary`, Helpful/Wrong-cause buttons on `/clusters`); feeds metrics, prompt-tuning job later
- [x] Product digest: top feature demand from non-bug clusters + deterministic proposal docs (`workers/insights`, `agent/analyst.py`, `GET /v1/insights/digest|/proposals`, `/insights` page)
- [x] Dashboards: feedback/clusters/actions-by-status/verifications/signals + PR acceptance rate (`GET /v1/metrics/summary`, `/insights`)
- [x] Replay: one command rebuilds index + clusters + graph from source data (`POST /v1/admin/replay`; restores a wiped index, tested)

**Exit criteria:** merged fix auto-marked verified with before/after chart; PM digest sent from real clustered feedback.

---

## Phase 6 — SaaS Hardening + Scale (wk 20–24)

**Goal:** charge money, onboard strangers, survive audit.

**In scope:** Stripe metered (events + investigations + seats), onboarding wizard (connect repo → install app → send test event → first cluster in <15 min), RLS + cross-store purge audit, PII vault + EU region flag, per-tenant budgets + degrade mode, docs + status page, load test (100 tenants synthetic).

**Out:** enterprise SSO/SAML, BYO LLM keys, on-prem — roadmap only.

**Tasks:**
- [x] Pricing enforcement: plans (free 500/50/20, pro 50k/5k/1k) metered at feedback/investigate/propose; 429 + upgrade hint (`workers/billing`, `app/quotas.py`; Stripe checkout + webhook ready behind `STRIPE_*` keys, admin plan flip for dev)
- [x] Onboarding: status checklist + one-click demo dataset, no GitHub needed (`/v1/onboarding/*`, `/onboarding` page)
- [x] Security: RLS contract test covers all 10 tenant tables; tenant purge across 13 tables + index/graph/cache dirs with audit entry; audit log + tenant read endpoint
- [x] Reliability: global per-key rate-limit middleware (Redis swap noted); replay drill tested; runbooks in `docs/OPERATIONS.md`
- [x] Docs: `docs/{API,CONNECTORS,OPERATIONS}.md`; `.pilignore` support for huge repos
- [x] Load test: `scripts/load_test.py` + `make load-test` — 60/60 accepted locally, p50 13ms / p95 69ms

**Exit criteria:** new tenant self-serves to first investigation without our help; delete-tenant test passes across all stores; billing webhook → entitlement flip works.

---

## First 2-Week Sprint (concrete start)

**Week 1:** monorepo + CI + Terraform dev + Clerk + Postgres schema + gateway stub returning 202.
**Week 2:** ingest worker + inbox UI + CSV import + seed data + RLS tests + staging deploy. Demo: `curl` → inbox.

Do not start agents, vectors, or sandbox until P0 demo passes.

---

## Cross-Cutting Tracks (run alongside phases)

- **Evals:** grow `evals/` from P1 (code search) → P3 (root cause) → P4 (PR acceptance). Block merges on eval regression.
- **Infra:** one Terraform apply per env from P0; preview envs for UI only.
- **Security:** PII redaction from P0; audit log from P3; purge job tested in P6.

---

## Definition of Done (any phase)

1. Demo on seeded + real data (not just mocks).
2. Evals updated and green.
3. Docs updated (this file checked + `ARCHITECTURE.md` if contracts changed).
4. Rollback path known (migrations reversible or forward-fix noted).
5. Cost/latency noted (tokens, p95, rows scanned).

---

## What We're Explicitly Not Building Yet

Auto-merge, auto-deploy/rollback, Datadog/Honeycomb deep integrations, mobile SDKs, SAML SSO, usage-based AI credits marketplace, multi-repo monorepo graph v2. Park in `ROADMAP_FUTURE.md` when needed.
