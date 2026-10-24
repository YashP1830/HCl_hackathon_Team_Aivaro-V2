import { createContext, useContext, useEffect, useState } from "react";
import { api } from "./api.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const raw = localStorage.getItem("user");
    return raw ? JSON.parse(raw) : null;
  });
  const [ready, setReady] = useState(false);

  useEffect(() => {
    // Validate stored token on load; clear if invalid.
    const token = localStorage.getItem("token");
    if (!token) {
      setReady(true);
      return;
    }
    api
      .me()
      .then((u) => {
        setUser(u);
        localStorage.setItem("user", JSON.stringify(u));
      })
      .catch(() => logout())
      .finally(() => setReady(true));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function persist(resp) {
    localStorage.setItem("token", resp.access_token);
    const u = { name: resp.name, email: resp.email, role: resp.role };
    localStorage.setItem("user", JSON.stringify(u));
    setUser(u);
  }

  async function login(email, password) {
    const resp = await api.login({ email, password });
    persist(resp);
    return resp;
  }

  async function register(name, email, password) {
    const resp = await api.register({ name, email, password });
    persist(resp);
    return resp;
  }

  function logout() {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, ready, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
