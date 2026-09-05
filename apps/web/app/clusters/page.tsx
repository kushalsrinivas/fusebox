import { ClustersPanel } from "../../components/ClustersPanel";

export const dynamic = "force-dynamic";

export default function ClustersPage() {
  return (
    <main>
      <h1>Clusters & Investigations (Phase 3)</h1>
      <p>
        Grouped feedback → evidence timeline → cited hypotheses. Every claim links
        back to a report, error, deploy, or code ref.
      </p>
      <ClustersPanel />
    </main>
  );
}
