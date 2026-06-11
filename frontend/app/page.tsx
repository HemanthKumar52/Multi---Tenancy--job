import Link from "next/link";

export default function Dashboard() {
  return (
    <>
      <header style={{ maxWidth: "64ch", marginBottom: 40 }}>
        <span className="kicker reveal">Resume → tailored → applied → tracked</span>
        <h1 className="reveal d1" style={{ marginTop: 18 }}>
          Your job search,<br />on a precision co-pilot.
        </h1>
        <p className="lede reveal d2" style={{ marginTop: 18 }}>
          One master resume becomes per-job, ATS-tuned applications — edited inside your own
          layout, never fabricated, and never sent until you approve.
        </p>
      </header>

      <section className="grid">
        {[
          { n: "01", t: "Profile", d: "Upload your resume. We parse it into a master profile and score its ATS-friendliness.", href: "/profile", cta: "Upload resume" },
          { n: "02", t: "Jobs", d: "Pull roles from ATS boards, see honest fit scores, and tailor in your resume's own layout.", href: "/jobs", cta: "Find & match" },
          { n: "03", t: "Applications", d: "Review the tailored diff, approve to apply, then track outcomes and interview prep.", href: "/applications", cta: "Track progress" },
        ].map((s, i) => (
          <Link key={s.n} href={s.href} style={{ textDecoration: "none", color: "inherit" }}>
            <div className={`card interactive reveal d${i + 1}`} style={{ height: "100%", marginBottom: 0 }}>
              <div className="step-no">{s.n}</div>
              <h2 style={{ margin: "10px 0 8px" }}>{s.t}</h2>
              <p className="muted" style={{ margin: 0 }}>{s.d}</p>
              <p style={{ color: "var(--accent)", fontWeight: 600, marginTop: 16, marginBottom: 0 }}>
                {s.cta} →
              </p>
            </div>
          </Link>
        ))}
      </section>

      <section className="card reveal d4" style={{ marginTop: 26 }}>
        <span className="kicker">The three guarantees</span>
        <ul className="ruled" style={{ marginTop: 14 }}>
          <li><span className="mark">◆</span><span><strong>Co-pilot.</strong> Nothing is submitted to a company without your explicit one-click approval — which doubles as the consent record.</span></li>
          <li><span className="mark">◆</span><span><strong>Truthful.</strong> We only resurface and rephrase facts already in your resume. A guard blocks any edit that would invent a skill.</span></li>
          <li><span className="mark">◆</span><span><strong>Format-preserving.</strong> Edits go back into <em>your</em> layout — same fonts, same structure. No generic template, ever.</span></li>
        </ul>
      </section>
    </>
  );
}
