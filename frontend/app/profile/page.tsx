"use client";

import { useState } from "react";
import { apiGet, apiUpload } from "../lib/api";

function scoreClass(s: number) {
  return s >= 85 ? "good" : s >= 65 ? "warn" : "bad";
}

export default function ProfilePage() {
  const [data, setData] = useState<any>(null);
  const [templates, setTemplates] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function onUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setErr("");
    setTemplates(null);
    try {
      const res = await apiUpload("/profiles/upload", file);
      setData(res);
      localStorage.setItem("profile_id", res.profile_id);
      try { setTemplates(await apiGet(`/templates/recommend/${res.profile_id}`)); } catch {}
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  const ats = data?.ats_report;
  const profile = data?.profile;

  return (
    <>
      <span className="kicker reveal">Step 01 · Master profile</span>
      <h1 className="reveal d1" style={{ marginTop: 16 }}>Your resume, understood.</h1>
      <p className="lede reveal d2" style={{ marginTop: 14 }}>
        Upload a <strong>.docx</strong> (best) or .pdf. We never redesign it — tailoring edits
        later go back into your own layout.
      </p>

      <div className="card reveal d3" style={{ marginTop: 22 }}>
        <label htmlFor="resume-file">Resume file</label>
        <input id="resume-file" type="file" accept=".docx,.pdf" onChange={onUpload} disabled={busy} />
        {busy && <p className="muted mono" style={{ margin: 0 }}>Parsing…</p>}
        {err && <p style={{ color: "var(--danger)", margin: "6px 0 0" }}>{err}</p>}
      </div>

      {data?.warnings?.length > 0 && (
        <div className="card" style={{ borderColor: "var(--warn)", background: "var(--warn-tint)" }}>
          {data.warnings.map((w: string, i: number) => (
            <p key={i} className="muted" style={{ margin: i ? "8px 0 0" : 0 }}>⚠ {w}</p>
          ))}
        </div>
      )}

      {profile && (
        <div className="card reveal">
          <span className="kicker">Parsed profile</span>
          <h2 style={{ marginTop: 12 }}>{profile.name || "Unnamed"}</h2>
          <p className="muted mono" style={{ marginTop: 2 }}>{profile.email} · {profile.phone}</p>
          <hr className="hairline" />
          <p style={{ margin: 0 }}><strong>Skills</strong> &nbsp;<span className="muted">{profile.skills?.join(" · ") || "—"}</span></p>
          <p style={{ margin: "10px 0 0" }}>
            <span className="pill">{profile.experience?.length ?? 0} experience</span>{" "}
            <span className="pill">{profile.skills?.length ?? 0} skills</span>{" "}
            <span className="pill">source: {data.source_format}</span>
          </p>
        </div>
      )}

      {ats && (
        <div className="card reveal">
          <span className="kicker">ATS compatibility</span>
          <div className="score-block" style={{ marginTop: 10 }}>
            <span className={`score ${scoreClass(ats.score)}`}>{ats.score}</span>
            <span className="muted mono">/ 100</span>
          </div>
          <div className="score-track"><div className="score-fill" style={{ width: `${ats.score}%` }} /></div>

          {ats.issues?.length === 0 && (
            <p className="muted" style={{ marginTop: 16 }}>Clean and parseable — no issues found. ✓</p>
          )}
          {ats.issues?.map((it: any, i: number) => (
            <div key={i} style={{ marginTop: 16, display: "flex", gap: 12, alignItems: "flex-start" }}>
              <span className={`badge ${it.tier === 1 ? "t1" : "t2"}`}>
                {it.tier === 1 ? "safe · in-place" : "structural · opt-in"}
              </span>
              <span>
                <strong>{it.message}</strong>
                <div className="muted">{it.suggestion}</div>
              </span>
            </div>
          ))}
        </div>
      )}

      {templates && (
        <div className="card reveal">
          <span className="kicker">ATS template suggestions</span>
          <p className="muted" style={{ marginTop: 10 }}>{templates.note}</p>
          {templates.recommendations?.map((t: any) => (
            <div key={t.id} style={{ borderTop: "1px solid var(--line)", padding: "12px 0" }}>
              <div className="row">
                <strong>{t.name}</strong>
                <span className="pill">{t.layout}</span>
                <a href={t.url} target="_blank" rel="noreferrer" style={{ marginLeft: "auto" }}>Open ↗</a>
              </div>
              <div className="muted" style={{ fontSize: 13 }}>{t.why} — <em>{t.match_reason}</em></div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
