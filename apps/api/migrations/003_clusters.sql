-- Phase 3: clusters + investigations. Apply: psql $DATABASE_URL -f 003_clusters.sql

create table if not exists issue_clusters (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  key text not null,
  title text not null default '',
  count int not null default 0,
  service_hint text,
  status text not null default 'auto',
  member_ids uuid[] not null default '{}',
  created_at timestamptz not null default now(),
  unique (tenant_id, key)
);
create index if not exists clusters_tenant_count_idx
  on issue_clusters (tenant_id, count desc);

create table if not exists investigations (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  cluster_id uuid not null references issue_clusters(id) on delete cascade,
  status text not null default 'needs_info',
  severity int not null default 2,
  confidence numeric not null default 0.3,
  result jsonb not null default '{}',
  created_at timestamptz not null default now()
);
create index if not exists investigations_tenant_cluster_idx
  on investigations (tenant_id, cluster_id, created_at desc);

alter table issue_clusters enable row level security;
drop policy if exists issue_clusters_tenant_isolation on issue_clusters;
create policy issue_clusters_tenant_isolation on issue_clusters
  using (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);

alter table investigations enable row level security;
drop policy if exists investigations_tenant_isolation on investigations;
create policy investigations_tenant_isolation on investigations
  using (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);
