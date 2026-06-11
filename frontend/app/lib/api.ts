// Tiny typed client for the Apply Co-Pilot backend.
// Carries a JWT (when logged in) and falls back to the dev tenant header otherwise.

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";
const TENANT = process.env.NEXT_PUBLIC_TENANT_ID ?? "devtenant";
const TOKEN_KEY = "ac_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}
export function setToken(t: string) {
  window.localStorage.setItem(TOKEN_KEY, t);
}
export function clearToken() {
  window.localStorage.removeItem(TOKEN_KEY);
}

function headers(json = true): HeadersInit {
  const h: Record<string, string> = {};
  const token = getToken();
  if (token) h["Authorization"] = `Bearer ${token}`;
  else h["X-Tenant-Id"] = TENANT;
  if (json) h["Content-Type"] = "application/json";
  return h;
}

async function handle<T>(res: Response, path: string): Promise<T> {
  if (!res.ok) {
    let detail = "";
    try { detail = (await res.json()).detail ?? ""; } catch {}
    throw new Error(detail || `${path} -> ${res.status}`);
  }
  return res.json();
}

export async function apiGet<T = any>(path: string): Promise<T> {
  return handle(await fetch(`${BASE}${path}`, { headers: headers(false), cache: "no-store" }), path);
}

export async function apiPost<T = any>(path: string, body?: unknown): Promise<T> {
  return handle(await fetch(`${BASE}${path}`, {
    method: "POST", headers: headers(),
    body: body === undefined ? undefined : JSON.stringify(body),
  }), path);
}

export async function apiUpload<T = any>(path: string, file: File): Promise<T> {
  const fd = new FormData();
  fd.append("file", file);
  return handle(await fetch(`${BASE}${path}`, { method: "POST", headers: headers(false), body: fd }), path);
}

export const apiBase = BASE;
export const tenantId = TENANT;
