import { CodeSearch } from "../../components/CodeSearch";

export const dynamic = "force-dynamic";

export default function CodePage() {
  return (
    <main>
      <h1>Ask Code (Phase 1)</h1>
      <p>
        Sync a repo, then ask grounded questions. Every hit cites{" "}
        <code>repo/path#Lstart-Lend</code> from the real index.
      </p>
      <CodeSearch />
    </main>
  );
}
