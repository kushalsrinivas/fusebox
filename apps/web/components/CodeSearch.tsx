"use client";

import { useState } from "react";
import { listRepos, searchCode, syncRepo, type CodeHit, type RepoStatus } from "../lib/api";

export function CodeSearch() {
  const [q, setQ] = useState("capture payment timeout");
  const [hits, setHits] = useState<CodeHit[]>([]);
  const [repos, setRepos] = useState<RepoStatus[]>([]);
  const [repoUrl, setRepoUrl] = useState("");
  const [msg, setMsg] = useState<string | null>(null);

  async function runSearch(e?: React.FormEvent) {
    e?.preventDefault();
    setMsg(null);
    try {
      setHits(await searchCode(q));
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "search failed");
    }
  }

  async function refreshRepos() {
    try {
      setRepos(await listRepos());
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "repos failed");
    }
  }

  async function runSync(e: React.FormEvent) {
    e.preventDefault();
    setMsg("syncing…");
    try {
      const stats = (await syncRepo(repoUrl)) as { files: number; chunks: number };
      setMsg(`synced: ${stats.files} files, ${stats.chunks} chunks`);
      await refreshRepos();
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "sync failed");
    }
  }

  return (
    <div>
      <form onSubmit={runSync} style={{ marginBottom: 16 }}>
        <input
          value={repoUrl}
          onChange={(e) => setRepoUrl(e.target.value)}
          placeholder="git URL or local path to sync"
          style={{ width: 360 }}
        />{" "}
        <button type="submit">Sync repo</button>{" "}
        <button type="button" onClick={refreshRepos}>
          Refresh status
        </button>
      </form>
      {repos.length > 0 && (
        <ul>
          {repos.map((r) => (
            <li key={r.repo}>
              <code>{r.repo}</code> — {r.files} files, {r.chunks} chunks
              {r.head_sha ? ` @ ${r.head_sha.slice(0, 7)}` : ""}
            </li>
          ))}
        </ul>
      )}
      <form onSubmit={runSearch} style={{ margin: "16px 0" }}>
        <input value={q} onChange={(e) => setQ(e.target.value)} style={{ width: 360 }} />{" "}
        <button type="submit">Ask code</button>
      </form>
      {msg && <p>{msg}</p>}
      {hits.map((h) => (
        <div key={h.ref} style={{ borderTop: "1px solid #ddd", padding: "8px 0" }}>
          <code>
            {h.repo}/{h.path}#L{h.lines}
          </code>{" "}
          <strong>{h.symbol}</strong> <small>({h.score})</small>
          <pre style={{ background: "#f6f6f6", padding: 8, overflowX: "auto" }}>
            {h.excerpt.slice(0, 500)}
          </pre>
        </div>
      ))}
    </div>
  );
}
