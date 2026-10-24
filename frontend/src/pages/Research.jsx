import { useState } from "react";
import { api } from "../lib/api.js";
import { Alert, Spinner } from "../components/common.jsx";

export default function Research() {
  const [topic, setTopic] = useState("");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  async function run(e) {
    e.preventDefault();
    setErr("");
    setLoading(true);
    setData(null);
    try {
      setData(await api.research(topic, 6));
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <h1 className="page-title">Research Papers</h1>
      <p className="page-sub">Google Scholar results via SerpAPI. Snippets are search snippets, not full-paper summaries.</p>

      <form className="row" onSubmit={run} style={{ marginBottom: 18 }}>
        <input placeholder="e.g. retrieval augmented generation" value={topic} onChange={(e) => setTopic(e.target.value)} style={{ maxWidth: 480 }} required />
        <button disabled={loading || !topic.trim()}>Search</button>
      </form>

      <Alert type="error">{err}</Alert>
      {loading && <Spinner label="Searching Google Scholar…" />}

      {data && data.note && <Alert type="info">{data.note}</Alert>}

      {data && data.results.length > 0 && (
        <div className="grid">
          {data.results.map((r, i) => (
            <div className="card" key={i}>
              <p className="book-title">
                {r.url ? <a href={r.url} target="_blank" rel="noreferrer">{r.title}</a> : r.title}
              </p>
              <p className="book-author">
                {(r.authors && r.authors.length) ? r.authors.join(", ") : "Authors not listed"}
                {r.year ? ` · ${r.year}` : ""}
              </p>
              {r.snippet && <p className="book-desc"><span className="muted">Snippet:</span> {r.snippet}</p>}
              {r.doi && <span className="muted" style={{ fontSize: 13 }}>DOI: {r.doi}</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
