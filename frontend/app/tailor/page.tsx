"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { apiPost } from "../lib/api";

function TailorInner() {
  const params = useSearchParams();
  const router = useRouter();
  const profileId = params.get("profile") || "";
  const jobId = params.get("job") || "";

  const [preview, setPreview] = useState<any>(null);
  const [appId, setAppId] = useState<string>("");
  const [draft, setDraft] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!profileId || !jobId) return;
    apiPost("/tailor/preview", { profile_id: profileId, job_id: jobId })
      .then(setPreview)
      .catch((e) => setErr(e.message));
  }, [profileId, jobId]);

  async function prepare() {
    setBusy(true);
    try {
      const res = await apiPost("/applications/prepare", { profile_id: profileId, job_id: jobId });
      setAppId(res.application_id);
      setDraft(res);
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  }

  async function approve() {
    setBusy(true);
    try {
      const res = await apiPost(`/applications/${appId}/approve`, { confirm: true });
      alert(`Application ${res.state}\n\n${(res.notes || []).join("\n")}`);
      router.push("/applications");
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  }

  if (!profileId || !jobId) return <p style={{ color: "var(--warn)" }}>Open this from a job in the Jobs tab.</p>;
  if (err) return <p style={{ color: "var(--danger)" }}>{err}</p>;
  if (!preview) return <p className="muted mono">Computing tailored edits…</p>;

  return (
    <>
      <span className="kicker reveal">Step 03 · Tailor &amp; review</span>
      <h1 className="reveal d1" style={{ marginTop: 16 }}>Review every change before it ships.</h1>

      <div className="card reveal d2" style={{ marginTop: 20, display: "flex", gap: 22, alignItems: "center", flexWrap: "wrap" }}>
        <div className="score-block">
          <span className="score good">{preview.match?.score}</span>
          <span className="muted mono">fit</span>
        </div>
        <div style={{ flex: 1, minWidth: 240 }}>
          <p style={{ margin: 0 }}>{preview.match?.explanation}</p>
          <p className="muted" style={{ margin: "6px 0 0", fontSize: 13 }}>{preview.note}</p>
        </div>
      </div>

      <div className="card reveal d3">
        <span className="kicker">
          {preview.edit_count} edit{preview.edit_count === 1 ? "" : "s"} · truthful · in-place
        </span>
        {preview.edits.length === 0 && (
          <p className="muted" style={{ marginTop: 14 }}>No changes needed — your resume already aligns well.</p>
        )}
        <div style={{ marginTop: 14 }}>
          {preview.edits.map((e: any, i: number) => (
            <div key={i} style={{ marginBottom: 18 }}>
              <div className="row" style={{ marginBottom: 6 }}>
                <span className={`badge ${e.tier === 1 ? "t1" : "t2"}`}>{e.tier === 1 ? "safe · in-place" : "structural"}</span>
                {e.section && <span className="pill">{e.section}</span>}
                <span className="muted" style={{ fontSize: 13 }}>{e.reason}</span>
              </div>
              <div className="diff">
                <div className="old">{e.original}</div>
                <div className="new">{e.new}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="card reveal d4">
        {!appId ? (
          <button onClick={prepare} disabled={busy}>Prepare tailored resume</button>
        ) : (
          <>
            <p className="muted" style={{ marginTop: 0 }}>
              Tailored document rendered in your original layout.{" "}
              {draft?.tailored_doc_path ? "Ready to review and submit." : "(A DOCX source is needed to render a file.)"}
            </p>
            <div className="row">
              <button className="success" onClick={approve} disabled={busy}>✓ Approve &amp; apply</button>
              <span className="muted" style={{ fontSize: 13 }}>
                This is the consent step — nothing is submitted before you click.
              </span>
            </div>
          </>
        )}
      </div>
    </>
  );
}

export default function TailorPage() {
  return (
    <Suspense fallback={<p className="muted mono">Loading…</p>}>
      <TailorInner />
    </Suspense>
  );
}
