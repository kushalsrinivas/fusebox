"use client";

import { useState } from "react";

interface Step {
  key: string;
  label: string;
  done: boolean;
}

export function OnboardingPanel() {
  const [steps, setSteps] = useState<Step[]>([]);
  const [msg, setMsg] = useState<string | null>(null);

  const headers = { "X-API-Key": process.env.NEXT_PUBLIC_API_KEY ?? "dev-key" };
  const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  async function status() {
    const r = await fetch(`${base}/v1/onboarding/status`, { headers, cache: "no-store" });
    const data = await r.json();
    setSteps(data.steps);
    setMsg(data.complete ? "Onboarding complete." : null);
  }

  async function demo() {
    setMsg("seeding demo data…");
    const r = await fetch(`${base}/v1/onboarding/demo`, { method: "POST", headers });
    if (!r.ok) {
      setMsg((await r.text()).slice(0, 300));
      return;
    }
    const data = await r.json();
    setMsg(`seeded ${data.feedback} reports, ${data.clusters} clusters. ${data.next}`);
    await status();
  }

  return (
    <div>
      <p>
        <button onClick={status}>Check status</button>{" "}
        <button onClick={demo}>Load demo data (no GitHub needed)</button>
      </p>
      {msg && <p>{msg}</p>}
      <ul>
        {steps.map((s) => (
          <li key={s.key}>
            {s.done ? "✅" : "⬜"} {s.label}
          </li>
        ))}
      </ul>
    </div>
  );
}
