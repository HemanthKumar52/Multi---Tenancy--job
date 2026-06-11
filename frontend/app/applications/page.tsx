"use client";

import { useEffect, useState } from "react";
import { apiGet, apiPost, apiBase } from "../lib/api";

export default function ApplicationsPage() {
  const [apps, setApps] = useState<any[]>([]);
  const [notes, setNotes] = useState<any[]>([]);
  const [email, setEmail] = useState({
    subject: "Interview invite",
    body: "We'd love to schedule a call — please share your availability via Calendly.",
    application_id: "",
  });
  const [prep, setPrep] = useState<any>(null);

  async function refresh() {
    setApps((await apiGet("/applications")).applications);
    setNotes((await apiGet("/notifications")).notifications);
  }
  useEffect(() => { refresh().catch(() => {}); }, []);

  async function simulateInbound() {
    const res = await apiPost("/inbox/inbound", {
      from_addr: "recruiter@company.com",
      subject: email.subject,
      body: email.body,
      application_id: email.application_id || null,
    });
    setPrep(res.prep_plan || null);
    refresh();
  }

  return (
    <>
      <span className="kicker reveal">Step 04 · Track &amp; prepare</span>
      <h1 className="reveal d1" style={{ marginTop: 16 }}>Every application, every outcome.</h1>

      <div className="card reveal d2" style={{ marginTop: 20 }}>
        <span className="kicker">Pipeline</span>
        <table style={{ marginTop: 12 }}>
          <thead><tr><th>State</th><th>Fit</th><th>Job</th><th>Submitted</th><th></th></tr></thead>
          <tbody>
            {apps.map((a) => (
              <tr key={a.application_id}>
                <td><span className="badge state">{a.state}</span></td>
                <td className="mono">{a.match_score}</td>
                <td className="muted mono" style={{ fontSize: 12 }}>{a.job_id}</td>
                <td className="muted mono" style={{ fontSize: 12 }}>{a.submitted_at || "—"}</td>
                <td>
                  <a href={`${apiBase}/applications/${a.application_id}/document`} target="_blank" rel="noreferrer">
                    Resume ↓
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {apps.length === 0 && <p className="muted" style={{ marginTop: 8 }}>No applications yet — tailor a job to create one.</p>}
      </div>

      <div className="card reveal d3">
        <span className="kicker">Inbox &amp; interview prep</span>
        <p className="muted" style={{ marginTop: 10 }}>
          Simulate an email arriving at your forwarding alias (<span className="mono">you@inbox.applycopilot…</span>).
          The classifier routes it; interview invites auto-generate a prep plan.
        </p>
        <input placeholder="Subject" value={email.subject} onChange={(e) => setEmail({ ...email, subject: e.target.value })} />
        <textarea rows={3} placeholder="Email body" value={email.body} onChange={(e) => setEmail({ ...email, body: e.target.value })} />
        <input placeholder="Link to application id (optional)" value={email.application_id} onChange={(e) => setEmail({ ...email, application_id: e.target.value })} />
        <button onClick={simulateInbound}>Process email</button>

        {prep && (
          <div style={{ marginTop: 18 }}>
            <hr className="hairline" />
            <h2>Prep plan — {prep.role} @ {prep.company}</h2>
            <p style={{ margin: "6px 0" }}><strong>Topics</strong> &nbsp;<span className="muted">{prep.topics?.join(" · ")}</span></p>
            <p style={{ margin: "12px 0 4px" }}><strong>Likely questions</strong></p>
            <ul className="ruled">{prep.likely_questions?.map((q: string, i: number) => <li key={i}><span className="mark">›</span><span>{q}</span></li>)}</ul>
            <p style={{ margin: "12px 0 4px" }}><strong>Study plan</strong></p>
            <ul className="ruled">{prep.study_plan?.map((q: string, i: number) => <li key={i}><span className="mark">›</span><span>{q}</span></li>)}</ul>
          </div>
        )}
      </div>

      <div className="card reveal d4">
        <span className="kicker">Notifications</span>
        <div style={{ marginTop: 10 }}>
          {notes.map((n) => (
            <div key={n.id} style={{ borderTop: "1px solid var(--line)", padding: "12px 0" }}>
              <strong>{n.title}</strong>
              <div className="muted">{n.body}</div>
            </div>
          ))}
          {notes.length === 0 && <p className="muted" style={{ margin: 0 }}>No notifications yet.</p>}
        </div>
      </div>
    </>
  );
}
