"use client";

import { useState } from "react";
import { correlate, fetchErrorGroups, type ErrorGroup, type Suspect } from "../lib/api";

export function ErrorsPanel() {
  const [service, setService] = useState("payments-api");
  const [spike, setSpike] = useState("2026-09-05T12:00:00Z");
  const [groups, setGroups] = useState<ErrorGroup[]>([]);
  const [suspects, setSuspects] = useState<Suspect[]>([]);
  const [msg, setMsg] = useState<string | null>(null);

  async function run(e: React.FormEvent) {
    e.preventDefault();
    setMsg(null);
    try {
      const [g, s] = await Promise.all([fetchErrorGroups(service), correlate(service, spike)]);
      setGroups(g);
      setSuspects(s);
      if (s.length === 0) setMsg("No deploy in the 6h window before the spike — likely not deploy-caused.");
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "failed");
    }
  }

  return (
    <div>
      <form onSubmit={run} style={{ marginBottom: 16 }}>
        <input value={service} onChange={(e) => setService(e.target.value)} style={{ width: 180 }} />{" "}
        <input value={spike} onChange={(e) => setSpike(e.target.value)} style={{ width: 220 }} />{" "}
        <button type="submit">Correlate</button>
      </form>
      {msg && <p>{msg}</p>}
      <h3>Suspect deploys</h3>
      {suspects.length === 0 ? (
        <p>None.</p>
      ) : (
        <ul>
          {suspects.map((s) => (
            <li key={s.deployment.id}>
              <code>
                {s.deployment.service} {s.deployment.version} @ {s.deployment.commit_sha}
              </code>{" "}
              — score {s.score} ({s.reason})
            </li>
          ))}
        </ul>
      )}
      <h3>Error groups ({groups.length})</h3>
      <table cellPadding={8} style={{ borderCollapse: "collapse", width: "100%" }}>
        <thead>
          <tr>
            <th align="left">Title</th>
            <th align="left">Count</th>
            <th align="left">Release</th>
            <th align="left">Last seen</th>
          </tr>
        </thead>
        <tbody>
          {groups.map((g) => (
            <tr key={g.fingerprint} style={{ borderTop: "1px solid #ddd" }}>
              <td>
                <strong>{g.title || g.fingerprint}</strong>
                <br />
                <small>{g.fingerprint}</small>
              </td>
              <td>{g.count}</td>
              <td>{g.release ?? "—"}</td>
              <td>{g.last_seen}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
