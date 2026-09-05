-- Phase 6: plans, usage metering, audit log. Apply: psql $DATABASE_URL -f 006_billing.sql

alter table tenants add column if not exists plan text not null default 'free';

create table if not exists usage_counters (
  tenant_id uuid not null references tenants(id) on delete cascade,
  kind text not null,
  used bigint not null default 0,
  updated_at timestamptz not null default now(),
  primary key (tenant_id, kind)
);

create table if not exists audit_log (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid references tenants(id) on delete cascade,
  actor text not null default 'system',
  action text not null,
  args jsonb not null default '{}',
  created_at timestamptz not null default now()
);
create index if not exists audit_tenant_created_idx
  on audit_log (tenant_id, created_at desc);

alter table usage_counters enable row level security;
drop policy if exists usage_counters_tenant_isolation on usage_counters;
create policy usage_counters_tenant_isolation on usage_counters
  using (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);

alter table audit_log enable row level security;
drop policy if exists audit_log_tenant_isolation on audit_log;
create policy audit_log_tenant_isolation on audit_log
  using (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid
         or tenant_id is null);
