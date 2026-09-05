-- Phase 5: verification runs + human signals. Apply: psql $DATABASE_URL -f 005_verification.sql

create table if not exists verifications (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  action_id uuid not null references actions(id) on delete cascade,
  status text not null default 'inconclusive',
  result jsonb not null default '{}',
  checked_at timestamptz not null default now()
);
create index if not exists verifications_tenant_action_idx
  on verifications (tenant_id, action_id, checked_at desc);

create table if not exists signals (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  investigation_id uuid references investigations(id) on delete cascade,
  signal text not null,
  note text not null default '',
  created_at timestamptz not null default now()
);
create index if not exists signals_tenant_idx on signals (tenant_id, created_at desc);

alter table verifications enable row level security;
drop policy if exists verifications_tenant_isolation on verifications;
create policy verifications_tenant_isolation on verifications
  using (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);

alter table signals enable row level security;
drop policy if exists signals_tenant_isolation on signals;
create policy signals_tenant_isolation on signals
  using (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);
