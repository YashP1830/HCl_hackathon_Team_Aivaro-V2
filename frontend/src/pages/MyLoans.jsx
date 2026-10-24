import { useEffect, useState } from "react";
import { api } from "../lib/api.js";
import { Alert, Spinner } from "../components/common.jsx";

function fmt(d) {
  if (!d) return "—";
  return new Date(d).toLocaleDateString();
}

export default function MyLoans() {
  const [loans, setLoans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");

  async function load() {
    setLoading(true);
    setErr("");
    try {
      setLoans(await api.myLoans());
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function doReturn(loan) {
    setMsg(""); setErr("");
    try {
      await api.returnLoan(loan.id);
      setMsg(`Returned "${loan.book_title}".`);
      load();
    } catch (e) {
      setErr(e.message);
    }
  }

  return (
    <div>
      <h1 className="page-title">My Loans</h1>
      <p className="page-sub">Your borrowed books and due dates. Overdue items trigger an email reminder.</p>

      <Alert type="ok">{msg}</Alert>
      <Alert type="error">{err}</Alert>

      {loading ? <Spinner /> : loans.length === 0 ? (
        <Alert type="info">You have no loans yet. Borrow a book from the Catalog.</Alert>
      ) : (
        <div className="card">
          <table>
            <thead>
              <tr><th>Book</th><th>Borrowed</th><th>Due</th><th>Status</th><th></th></tr>
            </thead>
            <tbody>
              {loans.map((l) => (
                <tr key={l.id}>
                  <td>{l.book_title}</td>
                  <td>{fmt(l.borrowed_at)}</td>
                  <td>{fmt(l.due_at)}</td>
                  <td>
                    {l.returned_at ? <span className="badge gray">Returned</span>
                      : l.is_overdue ? <span className="badge red">Overdue</span>
                      : <span className="badge green">On loan</span>}
                  </td>
                  <td>
                    {!l.returned_at && <button className="secondary" onClick={() => doReturn(l)}>Return</button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
