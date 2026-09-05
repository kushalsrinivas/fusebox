"use client";

import { useState } from "react";
import {
  fetchClusters,
  investigateCluster,
  rebuildClusters,
  sendSignal,
  type Cluster,
  type InvestigationResult,
  type TimelineEvent,
} from "../lib/api";

export function ClustersPanel() {
  const [clusters, setClusters] = useState<Cluster[]>([]);
  const [active, setActive] = useState<Cluster | null>(null);
  const [investigationId, setInvestigationId] = useState<string | null>(null);
  const [result, setResult] = useState<InvestigationResult | null>(null);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function refresh() {
    try {
      setClusters(await fetchClusters());
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "failed");
    }
  }

  async function rebuild() {
    setBusy(true);
    setMsg(null);
    try {
      setClusters(await rebuildClusters());
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "rebuild failed");
    } finally {
      setBusy(false);
    }
  }

  async function investigate(c: Cluster) {
    setActive(c);
    setBusy(true);
    setMsg(null);
    try {
      const out = await investigateCluster(c.id);
      setInvestigationId(out.investigation_id);
      setResult(out.result);
      setTimeline(out.timeline);
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "investigation failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <p>
        <button onClick={rebuild} disabled={busy}>
          Rebuild clusters
        </button>{" "}
        <button onClick={refresh} disabled={busy}>
          Refresh
        </button>
      </p>
      {msg && <p>{msg}</p>}
      <ul>
        {clusters.map((c) => (
          <li key={c.id}>
            <button onClick={() => investigate(c)} disabled={busy}>
              Investigate
            </button>{" "}
            <strong>{c.title || c.key}</strong> ×{c.count}
            {c.service_hint ? (
              <>
                {" "}<code>{c.service_hint}</code>
              </>
            ) : null}{" "}
            <small>({c.status})</small>
          </li>
        ))}
      </ul>
      {clusters.length === 0 && <p>No clusters yet — ingest feedback, then rebuild.</p>}
      {active && result && (
        <section style={{ borderTop: "2px solid #333", marginTop: 16, paddingTop: 8 }}>
          <h3>
            {active.title} — {result.status} (conf {result.confidence}, sev {result.severity})
          </h3>
          {investigationId && (
            <p>
              Was this right?{" "}
              <button
                onClick={() =>
                  sendSignal(investigationId, "helpful").then(
                    () => setMsg("signal recorded: helpful"),
                    (e) => setMsg(e instanceof Error ? e.message : "signal failed")
                  )
                }
              >
                Helpful
              </button>{" "}
              <button
                onClick={() =>
                  sendSignal(investigationId, "wrong_cause").then(
                    () => setMsg("signal recorded: wrong_cause"),
                    (e) => setMsg(e instanceof Error ? e.message : "signal failed")
                  )
                }
              >
                Wrong cause
              </button>
            </p>
          )}
          {result.hypotheses.map((h, i) => (
            <div key={i} style={{ marginBottom: 12 }}>
              <p>
                <strong>{h.title}</strong> — conf {h.confidence}
              </p>
              <p>{h.reason}</p>
              <ul>
                {h.citations.map((cit) => (
                  <li key={cit}>
                    <code>{cit}</code>
                  </li>
                ))}
              </ul>
            </div>
          ))}
          {result.repro_steps.length > 0 && (
            <>
              <h4>Repro</h4>
              <ol>
                {result.repro_steps.map((s) => (
                  <li key={s}>{s}</li>
                ))}
              </ol>
            </>
          )}
          <h4>Timeline</h4>
          <ul>
            {timeline.map((e, i) => (
              <li key={i}>
                <code>[{e.kind}]</code> {e.excerpt} <small>({e.ref})</small>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
