// Thin fetch wrappers for the backend's JSON API (/api/*).
// Set window.ARITH_API_BASE (e.g. "http://127.0.0.1:8000") to use an API on another origin.

const BASE = window.ARITH_API_BASE ?? "";

async function request(path, options = {}) {
  const response = await fetch(BASE + path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = body.detail;
    const message = typeof detail === "string" ? detail
      : detail?.message ?? (Array.isArray(detail) ? detail.map((d) => d.msg).join("; ") : response.statusText);
    const error = new Error(message);
    error.status = response.status;
    error.detail = detail;
    throw error;
  }
  return body;
}

export const getModels = () => request("/api/models");
export const getState = () => request("/api/state");
export const switchModel = (modelId, key) =>
  request("/api/switch_model", { method: "POST", body: JSON.stringify({ model_id: modelId, key: key || null }) });
export const sendMessage = (sender, text) =>
  request("/api/send", { method: "POST", body: JSON.stringify({ sender, text }) });
