import { useState } from "react";
import { api } from "../lib/api.js";
import { Alert, Spinner, StatusBadge } from "../components/common.jsx";

export default function Recommendations() {
  const [query, setQuery] = useState("");
  const [items, setItems] = useState(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  async function run(e) {
    e.preventDefault();
    setErr("");
    setLoading(true);
    setItems(null);
    try {
      const data = await api.recommend(query, 6);
      setItems(data.recommendations);
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <h1 className="page-title">Recommendations</h1>
      <p className="page-sub">
        Describe a topic. Results combine library matches with extra suggestions — each clearly labelled.
      </p>

      <form className="row" onSubmit={run} style={{ marginBottom: 18 }}>
        <input placeholder="e.g. Suggest me books on Generative AI" value={query} onChange={(e) => setQuery(e.target.value)} style={{ maxWidth: 480 }} required />
        <button disabled={loading || !query.trim()}>Recommend</button>
      </form>

      <Alert type="error">{err}</Alert>
      {loading && <Spinner label="Searching catalog and generating suggestions…" />}

      {items && items.length === 0 && <Alert type="info">No recommendations found. Try another topic.</Alert>}

      {items && items.length > 0 && (
        <div className="grid cols-2">
          {items.map((it, i) => (
            <div className="card" key={i}>
              <div className="row space-between">
                <p className="book-title">{it.book_name}</p>
                <StatusBadge status={it.library_status} />
              </div>
              <p className="book-author">{it.author}</p>
              <p className="book-desc">{it.description}</p>
              {it.library_status === "not_in_library" && (
                <span className="muted" style={{ fontSize: 13 }}>
                  External suggestion — not owned by the library.
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
