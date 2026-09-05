-- Phase 4: proposed/approved engineering actions. Apply: psql $DATABASE_URL -f 004_actions.sql

create table if not exists actions (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  cluster_id uuid references issue_clusters(id) on delete cascade,
  investigation_id uuid references investigations(id) on delete cascade,
  repo text not null default '',
  branch text not null default '',
  title text not null default '',
  diff text not null default '',
  status text not null default 'proposed',
  risk jsonb not null default '{}',
  sandbox jsonb not null default '{}',
  pr_url text,
  dry_run boolean not null default true,
  created_at timestamptz not null default now()
);
create index if not exists actions_tenant_cluster_idx
  on actions (tenant_id, cluster_id, created_at desc);

alter table actions enable row level security;
drop policy if exists actions_tenant_isolation on actions;
create policy actions_tenant_isolation on actions
  using (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);
