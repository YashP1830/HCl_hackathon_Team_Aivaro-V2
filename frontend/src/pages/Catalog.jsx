import { useEffect, useState } from "react";
import { api } from "../lib/api.js";
import { Alert, Spinner, StatusBadge } from "../components/common.jsx";

function statusForBook(b) {
  return b.stock_quantity > 0 ? "in_library_available" : "in_library_out_of_stock";
}

export default function Catalog() {
  const [q, setQ] = useState("");
  const [books, setBooks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");

  async function load(query = "") {
    setLoading(true);
    setErr("");
    try {
      const data = await api.listBooks(query, 1, 50);
      setBooks(data.items);
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function borrow(book) {
    setMsg("");
    setErr("");
    try {
      await api.borrow(book.id);
      setMsg(`Borrowed "${book.title}". See it under My Loans.`);
      load(q);
    } catch (e) {
      setErr(e.message);
    }
  }

  return (
    <div>
      <h1 className="page-title">Catalog</h1>
      <p className="page-sub">Search the library and borrow available titles.</p>

      <form className="row" onSubmit={(e) => { e.preventDefault(); load(q); }} style={{ marginBottom: 18 }}>
        <input placeholder="Search by title, author or genre…" value={q} onChange={(e) => setQ(e.target.value)} style={{ maxWidth: 420 }} />
        <button>Search</button>
        {q && <button type="button" className="secondary" onClick={() => { setQ(""); load(""); }}>Clear</button>}
      </form>

      <Alert type="ok">{msg}</Alert>
      <Alert type="error">{err}</Alert>

      {loading ? <Spinner /> : books.length === 0 ? (
        <Alert type="info">No books found.</Alert>
      ) : (
        <div className="grid cols-2">
          {books.map((b) => (
            <div className="card" key={b.id}>
              <div className="row space-between">
                <p className="book-title">{b.title}</p>
                <StatusBadge status={statusForBook(b)} />
              </div>
              <p className="book-author">{b.author} {b.publication_year ? `· ${b.publication_year}` : ""}</p>
              <p className="book-desc">{b.description}</p>
              <div className="row space-between">
                <span className="muted">{b.genre} · stock {b.stock_quantity}</span>
                <button disabled={b.stock_quantity <= 0} onClick={() => borrow(b)}>
                  {b.stock_quantity > 0 ? "Borrow" : "Out of stock"}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
