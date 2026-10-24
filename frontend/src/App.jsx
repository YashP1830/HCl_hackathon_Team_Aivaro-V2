import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./lib/auth.jsx";
import { Spinner } from "./components/common.jsx";

import Login from "./pages/Login.jsx";
import Catalog from "./pages/Catalog.jsx";
import Recommendations from "./pages/Recommendations.jsx";
import FaqChat from "./pages/FaqChat.jsx";
import Research from "./pages/Research.jsx";
import MyLoans from "./pages/MyLoans.jsx";
import AdminBooks from "./pages/AdminBooks.jsx";
import Analytics from "./pages/Analytics.jsx";

function Sidebar() {
  const { user, logout } = useAuth();
  const link = ({ isActive }) => "navlink" + (isActive ? " active" : "");
  return (
    <aside className="sidebar">
      <div className="brand">📚 <span>Library&nbsp;AI</span></div>
      <NavLink to="/catalog" className={link}>Catalog</NavLink>
      <NavLink to="/recommend" className={link}>Recommendations</NavLink>
      <NavLink to="/faq" className={link}>FAQ Assistant</NavLink>
      <NavLink to="/research" className={link}>Research Papers</NavLink>
      <NavLink to="/loans" className={link}>My Loans</NavLink>
      {user?.role === "admin" && <NavLink to="/admin/books" className={link}>Admin · Books</NavLink>}
      {user?.role === "admin" && <NavLink to="/admin/analytics" className={link}>Admin · Analytics</NavLink>}
      <div className="spacer" />
      <div className="userbox">
        <div style={{ color: "var(--text)", fontWeight: 600 }}>{user?.name}</div>
        <div>{user?.email}</div>
        <div style={{ margin: "4px 0 10px" }}>
          <span className={`badge ${user?.role === "admin" ? "amber" : "gray"}`}>{user?.role}</span>
        </div>
        <button className="secondary" style={{ width: "100%" }} onClick={logout}>Sign out</button>
      </div>
    </aside>
  );
}

function RequireAuth({ children }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

function RequireAdmin({ children }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== "admin") return <Navigate to="/catalog" replace />;
  return children;
}

export default function App() {
  const { user, ready } = useAuth();

  if (!ready) {
    return <div className="auth-wrap"><Spinner label="Starting…" /></div>;
  }

  if (!user) {
    return (
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }

  return (
    <div className="app">
      <Sidebar />
      <main className="main">
        <Routes>
          <Route path="/login" element={<Navigate to="/catalog" replace />} />
          <Route path="/catalog" element={<RequireAuth><Catalog /></RequireAuth>} />
          <Route path="/recommend" element={<RequireAuth><Recommendations /></RequireAuth>} />
          <Route path="/faq" element={<RequireAuth><FaqChat /></RequireAuth>} />
          <Route path="/research" element={<RequireAuth><Research /></RequireAuth>} />
          <Route path="/loans" element={<RequireAuth><MyLoans /></RequireAuth>} />
          <Route path="/admin/books" element={<RequireAdmin><AdminBooks /></RequireAdmin>} />
          <Route path="/admin/analytics" element={<RequireAdmin><Analytics /></RequireAdmin>} />
          <Route path="*" element={<Navigate to="/catalog" replace />} />
        </Routes>
      </main>
    </div>
  );
}
