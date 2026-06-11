"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiGet, apiPost, clearToken, getToken } from "../lib/api";

export default function SettingsPage() {
  const router = useRouter();
  const [me, setMe] = useState<any>(null);
  const [plan, setPlan] = useState<any>(null);
  const [err, setErr] = useState("");

  async function refresh() {
    setMe(await apiGet("/auth/me"));
    setPlan(await apiGet("/billing/plan"));
  }

  useEffect(() => {
    if (!getToken()) { router.push("/login"); return; }
    refresh().catch((e) => setErr(e.message));
  }, [router]);

  async function upgrade() {
    try { await apiPost("/billing/dev-upgrade"); refresh(); }
    catch (e: any) { setErr(e.message); }
  }

  function logout() { clearToken(); router.push("/login"); }

  if (err) return <p style={{ color: "var(--danger)" }}>{err}</p>;
  if (!me) return <p className="muted mono">Loading…</p>;

  const bar = (used: number, cap: number) => (
    <div className="score-track" style={{ maxWidth: 280 }}>
      <div className="score-fill" style={{ width: `${Math.min(100, (used / cap) * 100)}%` }} />
    </div>
  );

  return (
    <>
      <span className="kicker reveal">Account</span>
      <h1 className="reveal d1" style={{ marginTop: 16 }}>Settings</h1>

      <div className="card reveal d2" style={{ marginTop: 22 }}>
        <span className="kicker">Profile</span>
        <h2 style={{ marginTop: 10 }}>{me.name || me.email}</h2>
        <p className="muted mono">{me.email}</p>
      </div>

      <div className="card reveal d2">
        <span className="kicker">Inbox alias</span>
        <p style={{ marginTop: 10 }}>
          Forward job emails here and we'll classify them + prep you for interviews:
        </p>
        <p className="mono" style={{ fontSize: 15, color: "var(--trust)" }}>{me.inbox_alias}</p>
        <p className="muted" style={{ fontSize: 13 }}>
          Native Gmail/IMAP connect is available as a later add-on (kept optional to avoid the
          Google verification wall).
        </p>
      </div>

      {plan && (
        <div className="card reveal d3">
          <span className="kicker">Plan &amp; usage · {plan.plan}</span>
          <div style={{ marginTop: 12 }}>
            {Object.entries(plan.usage).map(([k, v]: any) => (
              <div key={k} style={{ marginBottom: 12 }}>
                <div className="row" style={{ justifyContent: "space-between", maxWidth: 280 }}>
                  <strong style={{ textTransform: "capitalize" }}>{k}</strong>
                  <span className="mono muted">{v.used}/{v.cap} this month</span>
                </div>
                {bar(v.used, v.cap)}
              </div>
            ))}
          </div>
          {plan.plan !== "pro" && (
            <button onClick={upgrade} style={{ marginTop: 8 }}>Upgrade to Pro</button>
          )}
        </div>
      )}

      <div className="card reveal d4">
        <button className="secondary" onClick={logout}>Sign out</button>
      </div>
    </>
  );
}
