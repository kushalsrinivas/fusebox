import { InsightsPanel } from "../../components/InsightsPanel";

export const dynamic = "force-dynamic";

export default function InsightsPage() {
  return (
    <main>
      <h1>Insights & Metrics (Phase 5)</h1>
      <p>Aggregated feature demand for PMs, plus the learning-loop dashboard.</p>
      <InsightsPanel />
    </main>
  );
}
