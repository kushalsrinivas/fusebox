import { FeedbackTable } from "../components/FeedbackTable";
import { fetchFeedback, type FeedbackRow } from "../lib/api";

export const dynamic = "force-dynamic";

export default async function Page() {
  let items: FeedbackRow[] = [];
  let error: string | null = null;
  try {
    items = await fetchFeedback();
  } catch (e) {
    error = e instanceof Error ? e.message : "api unreachable";
  }
  return (
    <main>
      <h1>Fusebox Inbox</h1>
      <p>
        API key: <code>dev-key</code> · <code>make seed</code> to populate ·
        Phase 3 adds clustering + investigation timeline.
      </p>
      {error ? (
        <p style={{ color: "crimson" }}>
          API unreachable ({error}). Start it: <code>make api</code>
        </p>
      ) : (
        <FeedbackTable items={items} />
      )}
    </main>
  );
}
