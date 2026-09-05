"use client";

import { useState } from "react";
import {
  approveAction,
  fetchActions,
  fetchClusters,
  proposeAction,
  verifyAction,
  type Action,
  type Cluster,
} from "../lib/api";

export function ActionsPanel() {
  const [clusters, setClusters] = useState<Cluster[]>([]);
  const [actions, setActions] = useState<Action[]>([]);
  const [clusterId, setClusterId] = useState("");
  const [repo, setRepo] = useState("demo");
  const [diff, setDiff] = useState(
    "--- a/apps/payments/checkout.py\n+++ b/apps/payments/checkout.py\n@@ -1,2 +1,2 @@\n-    return 1\n+    return 2\n"
  );
  const [msg, setMsg] = useState<string | null>(null);

  async function load() {
    try {
      const [c, a] = await Promise.all([fetchClusters(), fetchActions()]);
      setClusters(c);
      setActions(a);
      if (!clusterId && c.length > 0) setClusterId(c[0].id);
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "load failed");
    }
  }

  async function propose(e: React.FormEvent) {
    e.preventDefault();
    setMsg("validating + sandboxing…");
    try {
      const out = await proposeAction(clusterId, repo, diff);
      setMsg(`proposed: ${out.action.status}, risk ${out.risk.level} (${out.risk.score})`);
      setActions(await fetchActions());
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "propose failed");
    }
  }

  async function approve(a: Action, confirm = false) {
    setMsg(null);
    try {
      const out = await approveAction(a.id, confirm);
      setMsg(
        out.pr.dry_run
          ? `approved (dry-run PR draft: ${out.pr.title})`
          : `approved: ${out.pr.pr_url}`
      );
      setActions(await fetchActions());
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "approve failed");
    }
  }

  async function verify(a: Action) {
    setMsg("checking error deltas…");
    try {
      const out = await verifyAction(a.id);
      setMsg(`verification: ${out.status} (${out.elapsed_h}h elapsed)`);
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "verify failed");
    }
  }

  return (
    <div>
      <p>
        <button onClick={load}>Load clusters + actions</button>
      </p>
      {msg && <p>{msg}</p>}
      <form onSubmit={propose}>
        <p>
          <select value={clusterId} onChange={(e) => setClusterId(e.target.value)}>
            <option value="">— pick cluster —</option>
            {clusters.map((c) => (
              <option key={c.id} value={c.id}>
                {c.title || c.key} ×{c.count}
              </option>
            ))}
          </select>{" "}
          <input value={repo} onChange={(e) => setRepo(e.target.value)} style={{ width: 120 }} />
        </p>
        <p>
          <textarea value={diff} onChange={(e) => setDiff(e.target.value)} rows={10} cols={80} />
        </p>
        <button type="submit">Propose fix (validate + sandbox + risk)</button>
      </form>
      <h3>Actions ({actions.length})</h3>
      <ul>
        {actions.map((a) => (
          <li key={a.id} style={{ marginBottom: 8 }}>
            <code>{a.branch || "(rejected)"}</code> — <strong>{a.status}</strong>
            {a.risk?.level ? (
              <>
                {" "}risk {a.risk.level} ({a.risk.score})
              </>
            ) : null}{" "}
            {a.pr_url ? <a href={a.pr_url}>PR</a> : null}{" "}
            {a.status === "sandbox_passed" && (
              <>
                <button onClick={() => approve(a)}>Approve</button>{" "}
                {a.risk?.requires_two_approvals && (
                  <button onClick={() => approve(a, true)}>Approve (confirm high risk)</button>
                )}
              </>
            )}
            <br />
            <small>{a.title}</small>{" "}
            {(a.status === "approved" || a.status === "sandbox_passed") && (
              <button onClick={() => verify(a)}>Verify fix</button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
