-- Phase 2: observability stores. Apply: psql $DATABASE_URL -f 002_observability.sql
-- Production note: occurrences are hot-tailed (90d). Run a scheduled
-- `delete from error_occurrences where ts < now() - interval '90 days'`
-- (ClickHouse with TTL replaces this table at scale; same row shape).

create table if not exists deployments (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  service text not null,
  version text not null,
  commit_sha text,
  env text not null default 'production',
  deployed_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);
create index if not exists deployments_tenant_service_idx
  on deployments (tenant_id, service, deployed_at desc);

create table if not exists error_groups (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  fingerprint text not null,
  service text not null default 'unknown',
  release text,
  title text not null default '',
  first_seen timestamptz not null default now(),
  last_seen timestamptz not null default now(),
  count bigint not null default 0,
  unique (tenant_id, fingerprint)
);
create index if not exists error_groups_tenant_service_idx
  on error_groups (tenant_id, service, last_seen desc);

create table if not exists error_occurrences (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  fingerprint text not null,
  service text not null default 'unknown',
  level text not null default 'error',
  message text not null default '',
  event_id text,
  ts timestamptz not null default now()
);
create index if not exists error_occurrences_tenant_fp_ts_idx
  on error_occurrences (tenant_id, fingerprint, ts desc);

alter table deployments enable row level security;
drop policy if exists deployments_tenant_isolation on deployments;
create policy deployments_tenant_isolation on deployments
  using (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);

alter table error_groups enable row level security;
drop policy if exists error_groups_tenant_isolation on error_groups;
create policy error_groups_tenant_isolation on error_groups
  using (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);

alter table error_occurrences enable row level security;
drop policy if exists error_occurrences_tenant_isolation on error_occurrences;
create policy error_occurrences_tenant_isolation on error_occurrences
  using (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);
