export function Spinner({ label }) {
  return (
    <span className="muted">
      <span className="spinner" /> {label || "Loading…"}
    </span>
  );
}

export function Alert({ type = "info", children }) {
  if (!children) return null;
  return <div className={`alert ${type}`}>{children}</div>;
}

const STATUS_META = {
  in_library_available: { cls: "green", text: "Available in library" },
  in_library_out_of_stock: { cls: "amber", text: "In library · out of stock" },
  not_in_library: { cls: "gray", text: "Suggestion · not in library" },
};

export function StatusBadge({ status }) {
  const meta = STATUS_META[status] || { cls: "gray", text: status };
  return <span className={`badge ${meta.cls}`} title={status}>{meta.text}</span>;
}

export function EmbeddingBadge({ status }) {
  const map = { ready: "green", pending: "amber", failed: "red" };
  return <span className={`badge ${map[status] || "gray"}`}>index: {status}</span>;
}
