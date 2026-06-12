"use client";

import { useEffect, useState } from "react";
import { apiGet, apiPost } from "../lib/api";

export default function AutoApplyPage() {
  const [profileId, setProfileId] = useState("");
  const [identity, setIdentity] = useState({ first_name: "", last_name: "", email: "", phone: "" });
  const [answers, setAnswers] = useState({ "Why are you interested in this role?": "", "Are you authorized to work in this country?": "" });
  const [savedMsg, setSavedMsg] = useState("");

  const [search, setSearch] = useState({ name: "Daily auto-apply", daily_cap: 10, source_specs: '[{"vendor":"greenhouse","board":"gitlab"}]' });
  const [searches, setSearches] = useState<any[]>([]);
  const [batch, setBatch] = useState<any>(null);
  const [sendResult, setSendResult] = useState<any>(null);
  const [dry, setDry] = useState<Record<string, any>>({});
  const [err, setErr] = useState("");

  async function refreshSearches() {
    try { setSearches((await apiGet("/auto-apply/searches")).searches); } catch {}
  }
  useEffect(() => {
    setProfileId(localStorage.getItem("profile_id") || "");
    apiGet("/auto-apply/answers").then((a) => {
      if (a?.identity) setIdentity({ first_name: "", last_name: "", email: "", phone: "", ...a.identity });
      if (a?.answers && Object.keys(a.answers).length) setAnswers((x) => ({ ...x, ...a.answers }));
    }).catch(() => {});
    refreshSearches();
  }, []);

  async function saveAnswers() {
    setSavedMsg("");
    try {
      await apiPost("/auto-apply/answers", { profile_id: profileId, identity, answers, meta: {} });
      setSavedMsg("Saved ✓");
    } catch (e: any) { setErr(e.message); }
  }

  async function createSearch() {
    try {
      let specs: any[] = [];
      try { specs = JSON.parse(search.source_specs); } catch { return alert("source_specs must be valid JSON"); }
      await apiPost("/auto-apply/searches", { profile_id: profileId, name: search.name, daily_cap: Number(search.daily_cap), source_specs: specs });
      refreshSearches();
    } catch (e: any) { setErr(e.message); }
  }

  async function runSearch(id: string) {
    setBatch(null); setSendResult(null); setErr("");
    try { setBatch(await apiPost(`/auto-apply/searches/${id}/run`)); refreshSearches(); }
    catch (e: any) { setErr(e.message); }
  }

  async function sendAll() {
    if (!batch?.batch_id) return;
    try { setSendResult(await apiPost(`/auto-apply/batches/${batch.batch_id}/send`, { confirm: true })); }
    catch (e: any) { setErr(e.message); }
  }

  async function preview(id: string) {
    setDry((d) => ({ ...d, [id]: { status: "running…" } }));
    try {
      const r = await apiPost(`/applications/${id}/dry-run`);
      setDry((d) => ({ ...d, [id]: r }));
    } catch (e: any) {
      setDry((d) => ({ ...d, [id]: { status: "error", message: e.message } }));
    }
  }

  return (
    <>
      <span className="kicker reveal">Auto-apply agent</span>
      <h1 className="reveal d1" style={{ marginTop: 16 }}>10 a day, review-then-send.</h1>
      <p className="lede reveal d2" style={{ marginTop: 12 }}>
        The agent finds and tailors your top matches each day. You glance at the batch and send them
        all with one click. It only auto-submits on sanctioned ATS (Greenhouse/Lever/Ashby).
      </p>
      {err && <p style={{ color: "var(--danger)" }}>{err}</p>}
      {!profileId && <p style={{ color: "var(--warn)" }}>Upload a resume in the Profile tab first.</p>}

      <div className="card reveal d2">
        <span className="kicker">1 · Your reusable answers</span>
        <div className="row" style={{ marginTop: 10 }}>
          <input placeholder="First name" value={identity.first_name} onChange={(e) => setIdentity({ ...identity, first_name: e.target.value })} />
          <input placeholder="Last name" value={identity.last_name} onChange={(e) => setIdentity({ ...identity, last_name: e.target.value })} />
        </div>
        <div className="row">
          <input placeholder="Email" value={identity.email} onChange={(e) => setIdentity({ ...identity, email: e.target.value })} />
          <input placeholder="Phone" value={identity.phone} onChange={(e) => setIdentity({ ...identity, phone: e.target.value })} />
        </div>
        {Object.keys(answers).map((q) => (
          <div key={q}>
            <label>{q}</label>
            <textarea rows={2} value={(answers as any)[q]} onChange={(e) => setAnswers({ ...answers, [q]: e.target.value })} />
          </div>
        ))}
        <button onClick={saveAnswers}>Save answers</button> <span className="muted">{savedMsg}</span>
      </div>

      <div className="card reveal d3">
        <span className="kicker">2 · Daily policy</span>
        <div className="row" style={{ marginTop: 10 }}>
          <input placeholder="Name" value={search.name} onChange={(e) => setSearch({ ...search, name: e.target.value })} />
          <input type="number" placeholder="Per day" value={search.daily_cap} onChange={(e) => setSearch({ ...search, daily_cap: Number(e.target.value) })} style={{ maxWidth: 120 }} />
        </div>
        <label>Sources (JSON)</label>
        <input value={search.source_specs} onChange={(e) => setSearch({ ...search, source_specs: e.target.value })} />
        <button onClick={createSearch} disabled={!profileId}>Create daily search</button>
      </div>

      <div className="card reveal d3">
        <span className="kicker">3 · Run &amp; review</span>
        {searches.map((s) => (
          <div key={s.id} className="row" style={{ borderTop: "1px solid var(--line)", padding: "12px 0" }}>
            <strong>{s.name}</strong>
            <span className="pill">{s.daily_cap}/day</span>
            <span className="muted" style={{ fontSize: 13 }}>last run: {s.last_run_at || "—"}</span>
            <span style={{ marginLeft: "auto" }} />
            <button onClick={() => runSearch(s.id)}>Build today's batch</button>
          </div>
        ))}
        {searches.length === 0 && <p className="muted" style={{ marginTop: 8 }}>No searches yet — create one above.</p>}
      </div>

      {batch && (
        <div className="card reveal">
          <span className="kicker">Batch ready · {batch.prepared_count} tailored · {batch.manual_count} manual</span>
          <table style={{ marginTop: 12 }}>
            <thead><tr><th>Fit</th><th>Role</th><th>Company</th><th>ATS</th><th>Preview</th></tr></thead>
            <tbody>
              {batch.prepared?.map((p: any) => (
                <tr key={p.application_id}>
                  <td className="mono">{p.fit}</td><td>{p.title}</td><td>{p.company}</td>
                  <td><span className="badge t1">{p.ats_vendor}</span></td>
                  <td>
                    <button className="secondary" style={{ padding: "5px 10px", fontSize: 13 }}
                            onClick={() => preview(p.application_id)}>Dry-run</button>
                    {dry[p.application_id] && (
                      <div className="muted mono" style={{ fontSize: 11, marginTop: 4 }}>
                        {dry[p.application_id].status === "dry_run" ? "✓ filled, ready (not sent)"
                          : dry[p.application_id].status}
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="row" style={{ marginTop: 12 }}>
            <button className="success" onClick={sendAll}>✓ Send all {batch.prepared_count}</button>
            <span className="muted" style={{ fontSize: 13 }}>One click = your batch consent for these {batch.prepared_count}.</span>
          </div>
          {sendResult && (
            <p style={{ marginTop: 12 }}>
              Sent: <strong>{sendResult.counts?.submitted ?? 0}</strong> · handoff: {sendResult.counts?.human_handoff_required ?? 0} · failed: {sendResult.counts?.failed ?? 0}
              <br /><span className="muted" style={{ fontSize: 13 }}>(failed = APPLY_LIVE off — live submit needs enabling + real-site validation.)</span>
            </p>
          )}
          {batch.manual?.length > 0 && (
            <>
              <hr className="hairline" />
              <span className="kicker">Apply manually (non-ATS) · {batch.manual_count}</span>
              <ul className="ruled" style={{ marginTop: 8 }}>
                {batch.manual.slice(0, 15).map((m: any, i: number) => (
                  <li key={i}><span className="mark">›</span><span>{m.title} @ {m.company} — <a href={m.url} target="_blank" rel="noreferrer">apply ↗</a></span></li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </>
  );
}
