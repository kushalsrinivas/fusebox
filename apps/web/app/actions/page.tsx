import { ActionsPanel } from "../../components/ActionsPanel";

export const dynamic = "force-dynamic";

export default function ActionsPage() {
  return (
    <main>
      <h1>Actions & Draft PRs (Phase 4)</h1>
      <p>
        Propose a unified diff → policy check + secret scan + sandbox + risk score →
        human approve → draft PR (dry-run without <code>PIL_GITHUB_TOKEN</code>).
      </p>
      <ActionsPanel />
    </main>
  );
}
