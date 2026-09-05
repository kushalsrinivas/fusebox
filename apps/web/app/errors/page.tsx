import { ErrorsPanel } from "../../components/ErrorsPanel";

export const dynamic = "force-dynamic";

export default function ErrorsPage() {
  return (
    <main>
      <h1>Errors & Suspects (Phase 2)</h1>
      <p>
        Sentry groups on the left of the pipeline, suspect deploys on the right of the
        reasoning — every suspect cites a deploy id + commit sha in the 6h pre-spike window.
      </p>
      <ErrorsPanel />
    </main>
  );
}
