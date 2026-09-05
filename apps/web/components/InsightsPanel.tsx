"use client";

import { useState } from "react";
import { fetchDigest, fetchMetrics, type DigestItem, type MetricsSummary } from "../lib/api";

export function InsightsPanel() {
  const [digest, setDigest] = useState<DigestItem[]>([]);
  const [metrics, setMetrics] = useState<MetricsSummary | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  async function load() {
    setMsg(null);
    try {
      const [d, m] = await Promise.all([fetchDigest(), fetchMetrics()]);
      setDigest(d);
      setMetrics(m);
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "load failed");
    }
  }

  return (
    <div>
      <p>
        <button onClick={load}>Load insights</button>
      </p>
      {msg && <p>{msg}</p>}
      {metrics && (
        <section>
          <h3>Platform metrics</h3>
          <ul>
            <li>Feedback: {metrics.feedback}</li>
            <li>Clusters: {metrics.clusters}</li>
            <li>
              PR acceptance: {metrics.pr_acceptance.approved}/{metrics.pr_acceptance.proposed_total} (
              {(metrics.pr_acceptance.rate * 100).toFixed(0)}%)
            </li>
            <li>Verifications: {JSON.stringify(metrics.verifications_by_status)}</li>
            <li>Signals: {JSON.stringify(metrics.signals)}</li>
          </ul>
        </section>
      )}
      <h3>Feature demand ({digest.length})</h3>
      {digest.map((d) => (
        <div key={d.cluster_key} style={{ borderTop: "1px solid #ddd", padding: "8px 0" }}>
          <strong>{d.title}</strong> — {d.requests} requests (ratio {d.feature_ratio})
          <ul>
            {d.sample_titles.map((t) => (
              <li key={t}>
                <small>{t}</small>
              </li>
            ))}
          </ul>
        </div>
      ))}
      {digest.length === 0 && <p>No feature demand yet — request-type feedback clusters show up here.</p>}
    </div>
  );
}
