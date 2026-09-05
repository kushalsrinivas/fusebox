import type { FeedbackRow } from "../../../packages/shared";

export type { FeedbackRow };

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY ?? "dev-key";

export async function fetchFeedback(limit = 50): Promise<FeedbackRow[]> {
  const res = await fetch(`${API_URL}/v1/feedback?limit=${limit}`, {
    headers: { "X-API-Key": API_KEY },
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`api ${res.status}`);
  const data = await res.json();
  return data.items as FeedbackRow[];
}

export interface CodeHit {
  path: string;
  repo: string;
  symbol: string;
  kind: string;
  lines: string;
  excerpt: string;
  ref: string;
  score: number;
}

export interface RepoStatus {
  repo: string;
  files: number;
  chunks: number;
  last_sync: string | null;
  head_sha: string | null;
}

export async function searchCode(q: string, top_k = 8): Promise<CodeHit[]> {
  const res = await fetch(
    `${API_URL}/v1/code/search?q=${encodeURIComponent(q)}&top_k=${top_k}`,
    { headers: { "X-API-Key": API_KEY }, cache: "no-store" }
  );
  if (!res.ok) throw new Error(`api ${res.status}`);
  return ((await res.json()).items ?? []) as CodeHit[];
}

export async function listRepos(): Promise<RepoStatus[]> {
  const res = await fetch(`${API_URL}/v1/repos`, {
    headers: { "X-API-Key": API_KEY },
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`api ${res.status}`);
  return ((await res.json()).items ?? []) as RepoStatus[];
}

export async function syncRepo(repo_url: string): Promise<unknown> {
  const res = await fetch(`${API_URL}/v1/repos/sync`, {
    method: "POST",
    headers: { "X-API-Key": API_KEY, "Content-Type": "application/json" },
    body: JSON.stringify({ repo_url }),
  });
  if (!res.ok) throw new Error((await res.text()).slice(0, 300));
  return res.json();
}

export interface ErrorGroup {
  fingerprint: string;
  service: string;
  release: string | null;
  title: string;
  count: number;
  first_seen: string;
  last_seen: string;
}

export interface Suspect {
  deployment: {
    id: string;
    service: string;
    version: string;
    commit_sha: string | null;
    env: string;
    deployed_at: string;
  };
  score: number;
  reason: string;
}

export async function fetchErrorGroups(service?: string): Promise<ErrorGroup[]> {
  const qs = service ? `?service=${encodeURIComponent(service)}` : "";
  const res = await fetch(`${API_URL}/v1/errors/groups${qs}`, {
    headers: { "X-API-Key": API_KEY },
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`api ${res.status}`);
  return ((await res.json()).items ?? []) as ErrorGroup[];
}

export async function correlate(service: string, spike_start: string): Promise<Suspect[]> {
  const res = await fetch(
    `${API_URL}/v1/correlate?service=${encodeURIComponent(service)}&spike_start=${encodeURIComponent(spike_start)}`,
    { headers: { "X-API-Key": API_KEY }, cache: "no-store" }
  );
  if (!res.ok) throw new Error(`api ${res.status}`);
  return ((await res.json()).suspects ?? []) as Suspect[];
}

export interface Cluster {
  id: string;
  key: string;
  title: string;
  count: number;
  service_hint: string | null;
  status: string;
  member_ids: string[];
}

export interface Hypothesis {
  title: string;
  confidence: number;
  reason: string;
  citations: string[];
  contradicts: string;
  commit_sha: string | null;
}

export interface TimelineEvent {
  kind: string;
  ref: string;
  excerpt: string;
}

export interface InvestigationResult {
  cluster_key: string;
  status: string;
  severity: number;
  confidence: number;
  hypotheses: Hypothesis[];
  repro_steps: string[];
  service: string | null;
}

export async function rebuildClusters(): Promise<Cluster[]> {
  const res = await fetch(`${API_URL}/v1/clusters/rebuild`, {
    method: "POST",
    headers: { "X-API-Key": API_KEY },
  });
  if (!res.ok) throw new Error(`api ${res.status}`);
  return ((await res.json()).items ?? []) as Cluster[];
}

export async function fetchClusters(): Promise<Cluster[]> {
  const res = await fetch(`${API_URL}/v1/clusters`, {
    headers: { "X-API-Key": API_KEY },
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`api ${res.status}`);
  return ((await res.json()).items ?? []) as Cluster[];
}

export async function investigateCluster(id: string): Promise<{
  investigation_id: string;
  result: InvestigationResult;
  timeline: TimelineEvent[];
}> {
  const res = await fetch(`${API_URL}/v1/clusters/${id}/investigate`, {
    method: "POST",
    headers: { "X-API-Key": API_KEY },
  });
  if (!res.ok) throw new Error((await res.text()).slice(0, 300));
  return res.json();
}

export interface Action {
  id: string;
  cluster_id: string | null;
  repo: string;
  branch: string;
  title: string;
  status: string;
  risk: { score: number; level: string; factors: string[]; requires_two_approvals: boolean };
  sandbox: { ok?: boolean; logs?: string[]; levels?: Record<string, string> };
  pr_url: string | null;
  dry_run: boolean;
}

export async function proposeAction(cluster_id: string, repo: string, diff: string): Promise<{
  action: Action;
  risk: Action["risk"];
  sandbox: { ok: boolean; logs: string[] };
}> {
  const res = await fetch(`${API_URL}/v1/actions/propose`, {
    method: "POST",
    headers: { "X-API-Key": API_KEY, "Content-Type": "application/json" },
    body: JSON.stringify({ cluster_id, repo, diff }),
  });
  if (!res.ok) throw new Error((await res.text()).slice(0, 500));
  return res.json();
}

export async function fetchActions(cluster_id?: string): Promise<Action[]> {
  const qs = cluster_id ? `?cluster_id=${encodeURIComponent(cluster_id)}` : "";
  const res = await fetch(`${API_URL}/v1/actions${qs}`, {
    headers: { "X-API-Key": API_KEY },
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`api ${res.status}`);
  return ((await res.json()).items ?? []) as Action[];
}

export async function approveAction(id: string, confirm_high_risk = false): Promise<{
  action: Action;
  pr: { dry_run: boolean; pr_url?: string; title?: string };
}> {
  const res = await fetch(`${API_URL}/v1/actions/${id}/approve`, {
    method: "POST",
    headers: { "X-API-Key": API_KEY, "Content-Type": "application/json" },
    body: JSON.stringify({ confirm_high_risk }),
  });
  if (!res.ok) throw new Error((await res.text()).slice(0, 500));
  return res.json();
}

export async function verifyAction(id: string): Promise<{
  verification_id: string;
  status: string;
  groups: { fingerprint: string; before: number; after: number; verdict: string; reason: string }[];
  elapsed_h: number;
}> {
  const res = await fetch(`${API_URL}/v1/actions/${id}/verify?window_h=24`, {
    method: "POST",
    headers: { "X-API-Key": API_KEY },
  });
  if (!res.ok) throw new Error((await res.text()).slice(0, 500));
  return res.json();
}

export interface DigestItem {
  cluster_key: string;
  title: string;
  requests: number;
  feature_ratio: number;
  service_hint: string | null;
  sample_titles: string[];
}

export async function fetchDigest(): Promise<DigestItem[]> {
  const res = await fetch(`${API_URL}/v1/insights/digest`, {
    headers: { "X-API-Key": API_KEY },
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`api ${res.status}`);
  return ((await res.json()).items ?? []) as DigestItem[];
}

export interface MetricsSummary {
  feedback: number;
  clusters: number;
  actions_by_status: Record<string, number>;
  verifications_by_status: Record<string, number>;
  pr_acceptance: { approved: number; proposed_total: number; rate: number };
  signals: Record<string, number>;
}

export async function fetchMetrics(): Promise<MetricsSummary> {
  const res = await fetch(`${API_URL}/v1/metrics/summary`, {
    headers: { "X-API-Key": API_KEY },
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`api ${res.status}`);
  return res.json();
}

export async function sendSignal(investigation_id: string, signal: string): Promise<void> {
  const res = await fetch(`${API_URL}/v1/investigations/${investigation_id}/feedback`, {
    method: "POST",
    headers: { "X-API-Key": API_KEY, "Content-Type": "application/json" },
    body: JSON.stringify({ signal }),
  });
  if (!res.ok) throw new Error((await res.text()).slice(0, 300));
}
