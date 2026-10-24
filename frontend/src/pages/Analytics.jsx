import { useEffect, useState } from "react";
import { api } from "../lib/api.js";
import { Alert, Spinner } from "../components/common.jsx";

function BarChart({ chart }) {
  const max = Math.max(...chart.series[0].data, 1);
  return (
    <div className="bars">
      {chart.categories.map((c, i) => (
        <div className="bar-row" key={i}>
          <span title={c} style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{c}</span>
          <div className="bar-track"><div className="bar-fill" style={{ width: `${(chart.series[0].data[i] / max) * 100}%` }} /></div>
          <span style={{ textAlign: "right" }}>{chart.series[0].data[i]}</span>
        </div>
      ))}
    </div>
  );
}

export default function Analytics() {
  const today = new Date().toISOString().slice(0, 10);
  const yearAgo = new Date(Date.now() - 365 * 864e5).toISOString().slice(0, 10);
  const [from, setFrom] = useState(yearAgo);
  const [to, setTo] = useState(today);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [reminderMsg, setReminderMsg] = useState("");

  async function load() {
    setLoading(true); setErr("");
    try {
      setData(await api.analytics(from, to));
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { load(); }, []);

  async function runReminders() {
    setReminderMsg("");
    try {
      const r = await api.runReminders();
      setReminderMsg(`Reminder job: checked ${r.checked}, sent ${r.sent}, skipped ${r.skipped_already_sent}, failed ${r.failed}.`);
    } catch (e) {
      setErr(e.message);
    }
  }

  return (
    <div>
      <h1 className="page-title">Admin · Analytics</h1>
      <p className="page-sub">Metrics are computed exactly in Python; the narrative is an LLM explanation of those numbers.</p>

      <div className="row" style={{ marginBottom: 18 }}>
        <div><label>From</label><input type="date" value={from} onChange={(e) => setFrom(e.target.value)} /></div>
        <div><label>To</label><input type="date" value={to} onChange={(e) => setTo(e.target.value)} /></div>
        <div style={{ alignSelf: "end" }}><button onClick={load}>Apply</button></div>
        <div style={{ alignSelf: "end" }}><button className="secondary" onClick={runReminders}>Run due-date reminders</button></div>
      </div>

      <Alert type="ok">{reminderMsg}</Alert>
      <Alert type="error">{err}</Alert>

      {loading ? <Spinner /> : data && (
        <>
          <div className="kpis">
            <div className="kpi"><div className="v">{data.totals.total_purchase_events}</div><div className="l">Purchase events</div></div>
            <div className="kpi"><div className="v">{data.totals.total_units}</div><div className="l">Units sold</div></div>
            <div className="kpi"><div className="v">₹{data.totals.total_revenue.toLocaleString()}</div><div className="l">Revenue</div></div>
            <div className="kpi"><div className="v">{data.totals.unique_titles}</div><div className="l">Unique titles</div></div>
          </div>

          <div className="card" style={{ marginBottom: 18 }}>
            <h3 style={{ marginTop: 0 }}>Narrative {data.llm_used ? <span className="badge green">LLM</span> : <span className="badge gray">local</span>}</h3>
            <p style={{ whiteSpace: "pre-wrap", margin: 0 }}>{data.narrative}</p>
          </div>

          <div className="grid cols-2">
            {data.charts.map((chart, i) => (
              <div className="card" key={i}>
                <h3 style={{ marginTop: 0 }}>{chart.title}</h3>
                <BarChart chart={chart} />
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
