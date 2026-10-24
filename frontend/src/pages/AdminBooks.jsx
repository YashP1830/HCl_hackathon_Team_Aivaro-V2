import { useEffect, useState } from "react";
import { api } from "../lib/api.js";
import { Alert, EmbeddingBadge, Spinner, StatusBadge } from "../components/common.jsx";

const EMPTY = { title: "", author: "", description: "", genre: "", publisher: "", publication_year: "", stock_quantity: 1 };

export default function AdminBooks() {
  const [books, setBooks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState(EMPTY);
  const [editId, setEditId] = useState(null);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const data = await api.listBooks("", 1, 100);
      setBooks(data.items);
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { load(); }, []);

  function edit(b) {
    setEditId(b.id);
    setForm({
      title: b.title, author: b.author, description: b.description, genre: b.genre,
      publisher: b.publisher, publication_year: b.publication_year || "", stock_quantity: b.stock_quantity,
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function reset() { setEditId(null); setForm(EMPTY); }

  async function submit(e) {
    e.preventDefault();
    setErr(""); setMsg(""); setBusy(true);
    const payload = {
      ...form,
      publication_year: form.publication_year ? Number(form.publication_year) : null,
      stock_quantity: Number(form.stock_quantity),
    };
    try {
      const resp = editId ? await api.updateBook(editId, payload) : await api.createBook(payload);
      setMsg(`"${resp.book.title}" saved · embedding status: ${resp.embedding_status}` +
        (resp.embedding_detail ? ` (${resp.embedding_detail})` : ""));
      reset();
      load();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  return (
    <div>
      <h1 className="page-title">Admin · Books</h1>
      <p className="page-sub">Create or edit catalog books. Saving descriptive fields re-generates the embedding; stock-only edits do not.</p>

      <div className="card" style={{ marginBottom: 22 }}>
        <h3 style={{ marginTop: 0 }}>{editId ? "Edit book" : "Add a book"}</h3>
        <Alert type="ok">{msg}</Alert>
        <Alert type="error">{err}</Alert>
        <form onSubmit={submit}>
          <div className="grid cols-2">
            <div><label>Title *</label><input value={form.title} onChange={set("title")} required /></div>
            <div><label>Author *</label><input value={form.author} onChange={set("author")} required /></div>
            <div><label>Genre</label><input value={form.genre} onChange={set("genre")} /></div>
            <div><label>Publisher</label><input value={form.publisher} onChange={set("publisher")} /></div>
            <div><label>Publication year</label><input type="number" value={form.publication_year} onChange={set("publication_year")} /></div>
            <div><label>Stock quantity</label><input type="number" min="0" value={form.stock_quantity} onChange={set("stock_quantity")} /></div>
          </div>
          <label>Description</label>
          <textarea rows={3} value={form.description} onChange={set("description")} />
          <div className="row" style={{ marginTop: 14 }}>
            <button disabled={busy}>{busy ? "Saving…" : editId ? "Update book" : "Create book"}</button>
            {editId && <button type="button" className="secondary" onClick={reset}>Cancel</button>}
          </div>
        </form>
      </div>

      {loading ? <Spinner /> : (
        <div className="card">
          <table>
            <thead><tr><th>Title</th><th>Author</th><th>Stock</th><th>Availability</th><th>Index</th><th></th></tr></thead>
            <tbody>
              {books.map((b) => (
                <tr key={b.id}>
                  <td>{b.title}</td>
                  <td>{b.author}</td>
                  <td>{b.stock_quantity}</td>
                  <td><StatusBadge status={b.stock_quantity > 0 ? "in_library_available" : "in_library_out_of_stock"} /></td>
                  <td><EmbeddingBadge status={b.embedding_status} /></td>
                  <td><button className="secondary" onClick={() => edit(b)}>Edit</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
