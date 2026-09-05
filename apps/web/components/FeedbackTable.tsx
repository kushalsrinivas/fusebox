import type { FeedbackRow } from "../lib/api";

export function FeedbackTable({ items }: { items: FeedbackRow[] }) {
  if (items.length === 0) {
    return (
      <p>
        No feedback yet. POST to <code>/v1/feedback</code> with{" "}
        <code>X-API-Key: dev-key</code> or run <code>make seed</code>.
      </p>
    );
  }
  return (
    <table cellPadding={8} style={{ borderCollapse: "collapse", width: "100%" }}>
      <thead>
        <tr>
          <th align="left">Title</th>
          <th align="left">Type</th>
          <th align="left">Source</th>
          <th align="left">Version</th>
        </tr>
      </thead>
      <tbody>
        {items.map((i) => (
          <tr key={i.id} style={{ borderTop: "1px solid #ddd" }}>
            <td>
              <strong>{i.title}</strong>
              <br />
              <small>{i.body.slice(0, 120)}</small>
            </td>
            <td>{i.type}</td>
            <td>{i.source}</td>
            <td>{i.app_version ?? "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
