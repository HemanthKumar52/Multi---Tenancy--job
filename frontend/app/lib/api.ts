// Tiny typed client for the Apply Co-Pilot backend.
// Multi-tenant: every request carries the tenant header (dev default).

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";
const TENANT = process.env.NEXT_PUBLIC_TENANT_ID ?? "devtenant";

function headers(json = true): HeadersInit {
  const h: Record<string, string> = { "X-Tenant-Id": TENANT };
  if (json) h["Content-Type"] = "application/json";
  return h;
}

export async function apiGet<T = any>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { headers: headers(false), cache: "no-store" });
  if (!res.ok) throw new Error(`GET ${path} -> ${res.status}`);
  return res.json();
}

export async function apiPost<T = any>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: headers(),
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`POST ${path} -> ${res.status}`);
  return res.json();
}

export async function apiUpload<T = any>(path: string, file: File): Promise<T> {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(`${BASE}${path}`, { method: "POST", headers: headers(false), body: fd });
  if (!res.ok) throw new Error(`UPLOAD ${path} -> ${res.status}`);
  return res.json();
}

export const apiBase = BASE;
export const tenantId = TENANT;
