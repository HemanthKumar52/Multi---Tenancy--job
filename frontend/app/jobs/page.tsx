"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiGet, apiPost } from "../lib/api";

export default function JobsPage() {
  const router = useRouter();
  const [jobs, setJobs] = useState<any[]>([]);
  const [profileId, setProfileId] = useState<string>("");
  const [matches, setMatches] = useState<Record<string, any>>({});
  const [form, setForm] = useState({ title: "", company: "", description: "", url: "", ats_vendor: "greenhouse" });
  const [discoverSpec, setDiscoverSpec] = useState('[{"vendor":"greenhouse","board":"stripe"}]');

  async function refresh() {
    const res = await apiGet("/jobs");
    setJobs(res.jobs);
  }

  useEffect(() => {
    setProfileId(localStorage.getItem("profile_id") || "");
    refresh().catch(() => {});
  }, []);

  async function addJob() {
    await apiPost("/jobs", form);
    setForm({ title: "", company: "", description: "", url: "", ats_vendor: "greenhouse" });
    refresh();
  }

  async function discover() {
    try {
      await apiPost("/jobs/discover", { source_specs: JSON.parse(discoverSpec) });
      refresh();
    } catch (e: any) {
      alert("Discovery: " + e.message);
    }
  }

  async function matchJob(jobId: string) {
    if (!profileId) return alert("Upload a resume first (Profile tab).");
    const res = await apiPost("/matches", { profile_id: profileId, job_id: jobId });
    setMatches((m) => ({ ...m, [jobId]: res }));
  }

  function fitClass(score: number) {
    return score >= 70 ? "t1" : "t2";
  }

  return (
    <>
      <span className="kicker reveal">Step 02 · Discover &amp; match</span>
      <h1 className="reveal d1" style={{ marginTop: 16 }}>Find roles worth tailoring for.</h1>
      {!profileId && (
        <p className="reveal d2" style={{ color: "var(--warn)", marginTop: 12 }}>
          No profile yet — upload a resume in the Profile tab to unlock matching &amp; tailoring.
        </p>
      )}

      <div className="grid reveal d2" style={{ marginTop: 22 }}>
        <div className="card" style={{ marginBottom: 0 }}>
          <span className="kicker">Discover from ATS boards</span>
          <p className="muted" style={{ marginTop: 10 }}>Source specs (JSON) — Greenhouse · Lever · Ashby · Workable · Adzuna.</p>
          <input value={discoverSpec} onChange={(e) => setDiscoverSpec(e.target.value)} />
          <button onClick={discover}>Discover</button>
        </div>

        <div className="card" style={{ marginBottom: 0 }}>
          <span className="kicker">Add a job manually</span>
          <div className="row" style={{ marginTop: 10 }}>
            <input placeholder="Title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
            <input placeholder="Company" value={form.company} onChange={(e) => setForm({ ...form, company: e.target.value })} />
          </div>
          <textarea placeholder="Job description" rows={3} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          <div className="row">
            <input placeholder="Apply URL" value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} />
            <select value={form.ats_vendor} onChange={(e) => setForm({ ...form, ats_vendor: e.target.value })}>
              <option value="greenhouse">greenhouse</option>
              <option value="lever">lever</option>
              <option value="ashby">ashby</option>
              <option value="workable">workable</option>
              <option value="external">external</option>
            </select>
          </div>
          <button onClick={addJob} disabled={!form.title}>Add job</button>
        </div>
      </div>

      <div className="card reveal d3">
        <span className="kicker">Job feed · {jobs.length}</span>
        <div style={{ marginTop: 8 }}>
          {jobs.map((j) => (
            <div key={j.id} style={{ borderTop: "1px solid var(--line)", padding: "16px 0" }}>
              <div className="row">
                <strong style={{ fontSize: 15 }}>{j.title}</strong>
                <span className="pill">{j.company || "—"}</span>
                <span className="pill">{j.ats_vendor}</span>
                {j.location && <span className="pill">{j.location}</span>}
                {matches[j.id] && <span className={`badge ${fitClass(matches[j.id].score)}`}>fit {matches[j.id].score}</span>}
                <span style={{ marginLeft: "auto" }} />
                <button className="secondary" onClick={() => matchJob(j.id)}>Match</button>
                <button onClick={() => router.push(`/tailor?profile=${profileId}&job=${j.id}`)} disabled={!profileId}>
                  Tailor →
                </button>
              </div>
              {matches[j.id] && <p className="muted" style={{ margin: "8px 0 0" }}>{matches[j.id].explanation}</p>}
            </div>
          ))}
          {jobs.length === 0 && <p className="muted" style={{ marginTop: 8 }}>No jobs yet — discover or add one above.</p>}
        </div>
      </div>
    </>
  );
}
