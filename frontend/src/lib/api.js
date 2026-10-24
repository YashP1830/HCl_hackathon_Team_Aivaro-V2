// Typed-ish API client. All requests go through here so error handling and
// auth headers are consistent.

const BASE = (import.meta.env.VITE_API_BASE_URL || "/api/v1").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(status, code, message) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

function authHeaders() {
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request(path, { method = "GET", body, auth = false } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (auth) Object.assign(headers, authHeaders());

  let resp;
  try {
    resp = await fetch(`${BASE}${path}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch (e) {
    throw new ApiError(0, "NETWORK", "Could not reach the server. Is the backend running?");
  }

  if (resp.status === 204) return null;

  let data = null;
  const text = await resp.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { message: text };
    }
  }

  if (!resp.ok) {
    const err = data && data.error ? data.error : {};
    throw new ApiError(resp.status, err.code || "ERROR", err.message || data?.detail || `Request failed (${resp.status})`);
  }
  return data;
}

export const api = {
  // auth
  register: (payload) => request("/auth/register", { method: "POST", body: payload }),
  login: (payload) => request("/auth/login", { method: "POST", body: payload }),
  me: () => request("/auth/me", { auth: true }),
  // books
  listBooks: (q, page = 1, pageSize = 20) =>
    request(`/books?q=${encodeURIComponent(q || "")}&page=${page}&page_size=${pageSize}`),
  getBook: (id) => request(`/books/${id}`),
  createBook: (payload) => request("/admin/books", { method: "POST", body: payload, auth: true }),
  updateBook: (id, payload) => request(`/admin/books/${id}`, { method: "PATCH", body: payload, auth: true }),
  // ai
  recommend: (query, topK = 5) => request("/recommendations", { method: "POST", body: { query, top_k: topK } }),
  faq: (question) => request("/chat/faq", { method: "POST", body: { question } }),
  research: (topic, maxResults = 5) =>
    request("/research/search", { method: "POST", body: { topic, max_results: maxResults } }),
  // loans
  myLoans: () => request("/loans/me", { auth: true }),
  borrow: (bookId) => request("/loans", { method: "POST", body: { book_id: bookId }, auth: true }),
  returnLoan: (loanId) => request(`/loans/${loanId}/return`, { method: "POST", auth: true }),
  // analytics
  analytics: (from, to) => {
    const qs = [];
    if (from) qs.push(`from=${from}`);
    if (to) qs.push(`to=${to}`);
    return request(`/admin/analytics${qs.length ? "?" + qs.join("&") : ""}`, { auth: true });
  },
  runReminders: () => request("/admin/reminders/run", { method: "POST", auth: true }),
  health: () => request("/health"),
};
