"""Full product demo through the real API (TestClient): resume -> profile -> answers -> daily
search (real Greenhouse board) -> build batch (real discovery + tailoring) -> DRY-RUN a prepared
application against the LIVE form (fills it, stops before submit). Nothing is submitted.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

os.environ["STORAGE_DIR"] = tempfile.mkdtemp(prefix="ac_demo_")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

RESUME = Path(r"C:\Users\venka\apply-copilot\backend\storage\hemanth_resume.docx")
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def main() -> int:
    with TestClient(app) as c:
        print("1) Upload resume → master profile")
        up = c.post("/profiles/upload", files={"file": ("resume.docx", RESUME.read_bytes(), DOCX)}).json()
        pid = up["profile_id"]
        print(f"   profile {pid} · skills parsed: {len(up['profile']['skills'])}")

        print("2) Save reusable answers (work-auth, why-interested)")
        c.post("/auto-apply/answers", json={
            "profile_id": pid,
            "identity": {"first_name": "Hemanth", "last_name": "Kumar",
                         "email": "hemanthkumar215hk@gmail.com", "phone": "+919360959520"},
            "answers": {"Why are you interested in this role?": "I build reliable full-stack products end to end.",
                        "Are you authorized to work in this country?": "Yes (India); sponsorship required elsewhere."}})

        print("3) Create daily search (real Greenhouse board: gitlab, cap=2)")
        sid = c.post("/auto-apply/searches", json={
            "profile_id": pid, "name": "demo", "daily_cap": 2,
            "source_specs": [{"vendor": "greenhouse", "board": "gitlab"}]}).json()["id"]

        print("4) Build today's batch (LIVE discovery + tailoring)…")
        batch = c.post(f"/auto-apply/searches/{sid}/run").json()
        print(f"   prepared: {batch['prepared_count']} · manual: {batch['manual_count']}")
        for p in batch["prepared"]:
            print(f"   - [{p['fit']}] {p['title']} @ {p['company']}  {p['url']}")

        if not batch["prepared"]:
            print("No ATS-direct jobs prepared (board may be empty right now).")
            return 1

        app_id = batch["prepared"][0]["application_id"]
        print(f"\n5) DRY-RUN application {app_id} against the REAL form (fill, then STOP before submit)…")
        dr = c.post(f"/applications/{app_id}/dry-run").json()
        print(f"   status      : {dr.get('status')}")
        print(f"   submit_ready: {dr.get('submit_ready')}")
        print(f"   message     : {dr.get('message')}")
        print(f"   screenshot  : {dr.get('screenshot_path')}")
        print("\nNothing was submitted. This is the agent working end-to-end up to the send click.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
