// Fetch wrappers for the backend's JSON API (/api/*).
// Set window.ARITH_API_BASE (e.g. "http://127.0.0.1:8000") to use an API on another origin.

const BASE = window.ARITH_API_BASE ?? "";

async function request(path, options = {}) {
  const response = await fetch(BASE + path, { headers: { "Content-Type": "application/json" }, ...options });
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

export const encode = (modelId, text, signal) =>
  request("/api/encode", { method: "POST", body: JSON.stringify({ model_id: modelId, text }), signal });

export const decode = (modelId, bits, symbols, signal) =>
  request("/api/decode", { method: "POST", body: JSON.stringify({ model_id: modelId, bits, symbols }), signal });

export const getSymbols = (modelId) => request(`/api/models/${encodeURIComponent(modelId)}/symbols`);

export const tokenize = (modelId, text, signal) =>
  request("/api/tokenize", { method: "POST", body: JSON.stringify({ model_id: modelId, text }), signal });
