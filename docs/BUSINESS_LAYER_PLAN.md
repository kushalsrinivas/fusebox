# Business-Context Layer Plan — Fusebox

> Companion to `ARCHITECTURE.md` (§4.11) and `PHASED_PLAN.md` (phases 0–6).
> Status: planned, sequenced **after** the 3-week benchmark freeze lifts.

## Scope contract

The full-loop wedge (complaint → verified fix) is unchanged. This layer is
**prioritization intelligence that feeds the wedge**: it reorders which
clusters get investigated first and adds a "why this matters" evidence section
to investigations and PR bodies. It does not create new action types, and the
opportunity digest (B4) is read-only ranking until the wedge passes its kill
bars. First analytics source: **PostHog**. Business goals: per-tenant
**`goals.yaml`**, versioned and reviewable.

## B0 — Business goals config

**Goal:** tenants can state what matters in a reviewable file; invalid configs
fail closed.

- [ ] `goals.yaml` JSON-schema: `north_star`, `funnels[]` (`{name, steps[],
      weight, revenue_linked}`), `guardrails[]` (metrics never to trade away),
      `weights {business_impact}` for the §8 priority formula.
- [ ] Pure `goals` lib: parse + validate + `business_weight(service, funnel)`
      lookup. Unknown service/funnel → weight 0 with a visible "unmapped" flag,
      never a silent default.
- [ ] Sample `goals.yaml` for the demo tenant + validation tests
      (missing file, bad weight sum, unknown funnel reference).
- [ ] Docs: `docs/CONNECTORS.md` section on writing goals.

**Exit:** malformed config returns a reviewable error; sample file validates.

## B1 — PostHog connector + funnel stores

**Goal:** drop-off and event data flows like every other source.

- [ ] PostHog connector worker: API key per tenant, backfill + webhook/capture
      sync of funnel insights and event series.
- [ ] `funnel_events` table (Postgres now, ClickHouse-shape + 90d TTL later,
      RLS + migration) mirroring the `error_occurrences` pattern.
- [ ] Graph nodes `Metric` / `FunnelStep` + deterministic edges (`STEP_EMITS`,
      `MEASURED_BY`); file backend first, same schema for Neo4j later.
- [ ] `GET /v1/funnels` (steps + drop-off rates for a funnel/window).

**Exit:** drop-off query returns real steps and rates on a demo PostHog project.

## B2 — Behavior↔technical joiner

**Goal:** a drop-off step links to the same evidence the wedge already uses.

- [ ] Extend the correlation lib's join keys with `funnel_step + time window`
      (same pure-function style as `find_suspects`): inputs are funnel-step
      deltas; outputs are linked error groups, latency deltas, deploys, and
      ticket clusters with recency-weighted scores.
- [ ] Unit tests on seeded histories: planted deploy + error spike behind a
      drop-off must rank first; unrelated-window decoys must not.
- [ ] Served behind the correlate path (`service` + `funnel_step` params).

**Exit:** seeded drop-off attributes to the planted cause, decoys excluded.

## B3 — Impact estimator

**Goal:** investigations and PRs gain a Business-case section with stated
uncertainty — never fabricated numbers.

- [ ] Pure estimator over joined evidence: relative deltas it can defend
      (`14% latency rise + 22% ticket rise → checkout completion at risk`),
      each claim tagged `high/medium/low` confidence with the inputs listed.
- [ ] Hard rule, tested: unattributable impact renders as `"unquantified"`,
      never a guessed `$` figure. Evals assert zero fabricated quantities.
- [ ] Wire into investigation results (`business_case` block) and PR body
      template (after root cause, before risk).

**Exit:** evals show calibrated statements; fabrication probe suite passes.

## B4 — Opportunity stream (read-only)

**Goal:** one ranked queue across fix/UX/perf/experiment/debt, with shown math.

- [ ] Ranking = existing §8 priority score + `goals.yaml` business-weight term
      (explicit, tenant-tunable, always in the breakdown).
- [ ] `GET /v1/opportunities` + weekly digest UI reusing the insights page
      pattern. Read-only: no new action types, no auto-creation of work.
- [ ] Ranking eval: a revenue-linked seed must outrank cosmetic seeds, with the
      weight math inspectable in the response.

**Exit:** mixed-seed queue orders correctly with visible reasoning.

## B5 — Continuous watcher

**Goal:** surfacing on a clock instead of on-demand only.

- [ ] Scheduler invoking existing endpoints (replay/correlation/investigate
      paths) on a tenant cadence. No new investigation logic.
- [ ] Dedupe against previously surfaced items; Slack digest delivery.
- [ ] Second run with no new signals surfaces nothing (tested).

**Exit:** quiet-second-run test passes; digest delivers end-to-end on demo data.

## Evals (same bar culture)

- Funnel-attribution accuracy on seeded histories.
- Impact-statement calibration (confidence labels vs. outcomes on the
  investigation-eval scenarios).
- Ranking eval per B4; fabrication probes per B3.

## Risks

- **Analytics-join false positives** (correlation ≠ causation across funnels) →
  confidence labels + `needs_info` discipline carry over unchanged.
- **Scope creep back into soup** → B4 is read-only; new action types wait for
  wedge kill bars to pass.
- **Goals gaming the queue** → weights versioned, visible, audit-logged.
- **PostHog API drift/quotas** → connector owns retries + sampling notes like
  the Sentry path.

## Sequencing vs. benchmark

Nothing here starts until the benchmark freeze lifts. Unresolved inputs owned
by the grill follow-up: corpus source, correctness definition, grading
protocol, and exact kill-bar thresholds (see planning notes — decide these
before the 3-week clock starts).
