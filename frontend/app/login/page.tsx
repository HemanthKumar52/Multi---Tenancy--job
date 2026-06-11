"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { apiPost, setToken } from "../lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [form, setForm] = useState({ email: "", password: "", name: "" });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit() {
    setBusy(true);
    setErr("");
    try {
      const path = mode === "register" ? "/auth/register" : "/auth/login";
      const res = await apiPost(path, form);
      setToken(res.access_token);
      router.push("/profile");
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ maxWidth: 440, margin: "4vh auto" }}>
      <span className="kicker reveal">{mode === "register" ? "Create account" : "Welcome back"}</span>
      <h1 className="reveal d1" style={{ marginTop: 16 }}>
        {mode === "register" ? "Start your co-pilot." : "Sign in."}
      </h1>

      <div className="card reveal d2" style={{ marginTop: 22 }}>
        {mode === "register" && (
          <>
            <label htmlFor="name">Name</label>
            <input id="name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </>
        )}
        <label htmlFor="email">Email</label>
        <input id="email" type="email" value={form.email}
               onChange={(e) => setForm({ ...form, email: e.target.value })} />
        <label htmlFor="password">Password</label>
        <input id="password" type="password" value={form.password}
               onChange={(e) => setForm({ ...form, password: e.target.value })}
               onKeyDown={(e) => e.key === "Enter" && submit()} />
        {err && <p style={{ color: "var(--danger)", margin: "4px 0" }}>{err}</p>}
        <button onClick={submit} disabled={busy || !form.email || form.password.length < 8}>
          {mode === "register" ? "Create account" : "Sign in"}
        </button>
        <p className="muted" style={{ marginTop: 14, fontSize: 13 }}>
          {mode === "register" ? "Already have an account? " : "New here? "}
          <a onClick={() => { setMode(mode === "register" ? "login" : "register"); setErr(""); }}
             style={{ cursor: "pointer" }}>
            {mode === "register" ? "Sign in" : "Create one"}
          </a>
          {mode === "register" && " · password min 8 chars"}
        </p>
      </div>
    </div>
  );
}
