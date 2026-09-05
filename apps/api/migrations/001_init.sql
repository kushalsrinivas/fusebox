-- Phase 0 source of truth. Apply: psql $DATABASE_URL -f 001_init.sql
create extension if not exists "pgcrypto";

create table if not exists tenants (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  plan text not null default 'free'
);

create table if not exists projects (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  name text not null,
  repo_urls text[] not null default '{}'
);

create table if not exists connectors (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  type text not null,
  status text not null default 'active'
);

create table if not exists feedback (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  source text not null default 'api',
  type text not null default 'other',
  title text not null,
  body text not null default '',
  app_version text,
  os text,
  service_hint text,
  external_id text,
  occurred_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);
create index if not exists feedback_tenant_created_idx on feedback (tenant_id, created_at desc);

-- Demo tenant (matches dev-key)
insert into tenants (id, name) values
  ('00000000-0000-0000-0000-000000000001', 'demo')
on conflict (id) do nothing;

-- Row-level security: every row scoped by app.tenant_id
alter table feedback enable row level security;
drop policy if exists feedback_tenant_isolation on feedback;
create policy feedback_tenant_isolation on feedback
  using (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);
