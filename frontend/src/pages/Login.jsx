import { useState } from "react";
import { useAuth } from "../lib/auth.jsx";
import { Alert } from "../components/common.jsx";

export default function Login() {
  const { login, register } = useAuth();
  const [mode, setMode] = useState("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setErr("");
    setBusy(true);
    try {
      if (mode === "login") await login(email, password);
      else await register(name, email, password);
    } catch (e) {
      setErr(e.message || "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-wrap">
      <div className="card auth-card">
        <div className="brand" style={{ padding: "0 0 14px" }}>📚 <span>Library&nbsp;AI</span></div>
        <div className="tabs">
          <button className={mode === "login" ? "" : "secondary"} onClick={() => setMode("login")}>Sign in</button>
          <button className={mode === "register" ? "" : "secondary"} onClick={() => setMode("register")}>Register</button>
        </div>
        <Alert type="error">{err}</Alert>
        <form onSubmit={submit}>
          {mode === "register" && (
            <>
              <label>Name</label>
              <input value={name} onChange={(e) => setName(e.target.value)} required />
            </>
          )}
          <label>Email</label>
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          <label>Password</label>
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={6} />
          <button style={{ width: "100%", marginTop: 16 }} disabled={busy}>
            {busy ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
          </button>
        </form>
        <Alert type="info">
          Demo accounts — admin: <b>admin@example.com / admin123</b> · user: <b>user@example.com / user123</b>
        </Alert>
      </div>
    </div>
  );
}
