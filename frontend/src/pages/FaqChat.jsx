import { useState } from "react";
import { api } from "../lib/api.js";
import { Spinner } from "../components/common.jsx";

export default function FaqChat() {
  const [log, setLog] = useState([
    { who: "bot", text: "Hi! Ask me anything about borrowing, returning, or using the library." },
  ]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);

  async function send(e) {
    e.preventDefault();
    const question = q.trim();
    if (!question) return;
    setLog((l) => [...l, { who: "user", text: question }]);
    setQ("");
    setBusy(true);
    try {
      const resp = await api.faq(question);
      let text = resp.answer;
      if (resp.status === "fallback" && resp.support_contact) {
        text += `\n\nSupport: ${resp.support_contact}`;
      }
      setLog((l) => [...l, { who: "bot", text, status: resp.status }]);
    } catch (e) {
      setLog((l) => [...l, { who: "bot", text: `Error: ${e.message}`, status: "error" }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <h1 className="page-title">FAQ Assistant</h1>
      <p className="page-sub">Answers come from approved FAQ content, with a support fallback after one retry.</p>

      <div className="card">
        <div className="chat-log">
          {log.map((m, i) => (
            <div key={i} className={`bubble ${m.who}`} style={{ whiteSpace: "pre-wrap" }}>
              {m.text}
              {m.status === "fallback" && <div className="badge amber" style={{ marginTop: 8 }}>fallback</div>}
            </div>
          ))}
          {busy && <div className="bubble bot"><Spinner label="Thinking…" /></div>}
        </div>
        <form className="row" onSubmit={send}>
          <input placeholder="How do I borrow a book?" value={q} onChange={(e) => setQ(e.target.value)} />
          <button disabled={busy}>Send</button>
        </form>
      </div>
    </div>
  );
}
