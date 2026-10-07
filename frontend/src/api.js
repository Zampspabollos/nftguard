const TOKEN_KEY = "nftguard_token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}
export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

function extractMessage(data, fallback) {
  if (!data || !data.detail) return fallback;
  if (Array.isArray(data.detail)) {
    return data.detail.map((d) => d.msg || JSON.stringify(d)).join(", ");
  }
  return String(data.detail);
}

export async function apiFetch(path, { method = "GET", body, auth = true } = {}) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (auth) {
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`/api${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401 && auth) {
    clearToken();
    if (!location.pathname.startsWith("/login")) {
      location.href = "/login";
    }
    throw new ApiError(401, "Sesión expirada");
  }

  if (!res.ok) {
    let data = null;
    try {
      data = await res.json();
    } catch {
      /* respuesta sin cuerpo json */
    }
    throw new ApiError(res.status, extractMessage(data, `Error ${res.status}`));
  }

  if (res.status === 204) return null;
  return res.json();
}

export async function apiFetchBlob(path) {
  const token = getToken();
  const res = await fetch(`/api${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (res.status === 401) {
    clearToken();
    location.href = "/login";
    throw new ApiError(401, "Sesión expirada");
  }
  if (!res.ok) {
    throw new ApiError(res.status, `Error ${res.status}`);
  }
  return res.blob();
}

export async function login(username, password) {
  const body = new URLSearchParams({ username, password });
  const res = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  if (!res.ok) {
    throw new ApiError(res.status, "Usuario o contraseña incorrectos");
  }
  const data = await res.json();
  setToken(data.access_token);
  return data;
}

export function wsStatusUrl() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${location.host}/api/status/ws?token=${encodeURIComponent(getToken() || "")}`;
}
