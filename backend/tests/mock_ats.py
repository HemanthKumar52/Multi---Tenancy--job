"""A local mock Greenhouse-style apply form for safely testing the Playwright adapter.

Reproduces the real Greenhouse field ids the adapter targets (#first_name, #last_name, #email,
#phone, hidden #resume file input, custom-question fields, "Submit application" button) and a
/confirmation page with the real success copy. It talks to nobody external — automated apply
tests target ONLY 127.0.0.1, never a real company (see recon guardrails).
"""
from __future__ import annotations

import threading
import time

import uvicorn
from starlette.applications import Starlette
from starlette.datastructures import UploadFile
from starlette.responses import HTMLResponse
from starlette.routing import Route

FORM_HTML = """<!doctype html><html><body>
<form id="application-form" action="/mock/greenhouse/confirmation" method="post" enctype="multipart/form-data">
  <label for="first_name">First Name *</label>
  <input id="first_name" name="first_name" type="text" aria-required="true">
  <label for="last_name">Last Name *</label>
  <input id="last_name" name="last_name" type="text">
  <label for="email">Email *</label>
  <input id="email" name="email" type="email">
  <label for="phone">Phone</label>
  <input id="phone" name="phone" type="tel">
  <div role="group" aria-labelledby="upload-label-resume">
    <div id="upload-label-resume">Resume/CV</div>
    <input id="resume" name="resume" type="file" accept=".pdf,.doc,.docx,.txt,.rtf">
  </div>
  <label for="question_1">Why do you want to work here?</label>
  <textarea id="question_1" name="question_1"></textarea>
  <label for="question_2">Are you authorized to work?</label>
  <input id="question_2" name="question_2" type="text">
  <button type="submit">Submit application</button>
</form></body></html>"""

CONFIRM_HTML = ("<!doctype html><html><body><h1>Thank you for applying</h1>"
                "<p>Your submission has been received.</p></body></html>")

# A form fronted by a bot-check / login wall — the adapter must hand off, never bypass it.
HANDOFF_FORM_HTML = """<!doctype html><html><body>
<form id="application-form">
  <div class="g-recaptcha" data-sitekey="test-sitekey"></div>
  <label for="account-password">Sign in to continue</label>
  <input id="account-password" name="pw" type="password">
</form></body></html>"""


class MockGreenhouse:
    def __init__(self, port: int = 8791, handoff: bool = False):
        self.port = port
        self.handoff = handoff
        self.received: dict = {}
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None

        async def apply(request):
            return HTMLResponse(HANDOFF_FORM_HTML if self.handoff else FORM_HTML)

        async def confirm(request):
            form = await request.form()
            data: dict = {}
            for key, value in form.multi_items():
                if isinstance(value, UploadFile):
                    content = await value.read()
                    data[key] = {"filename": value.filename, "size": len(content)}
                else:
                    data[key] = value
            self.received.clear()
            self.received.update(data)
            return HTMLResponse(CONFIRM_HTML)

        self.app = Starlette(routes=[
            Route("/mock/greenhouse/apply", apply, methods=["GET"]),
            Route("/mock/greenhouse/confirmation", confirm, methods=["GET", "POST"]),
        ])

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    @property
    def apply_url(self) -> str:
        return f"{self.base_url}/mock/greenhouse/apply"

    def __enter__(self) -> "MockGreenhouse":
        config = uvicorn.Config(self.app, host="127.0.0.1", port=self.port, log_level="warning")
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, daemon=True)
        self._thread.start()
        for _ in range(200):  # wait up to ~10s for startup
            if getattr(self._server, "started", False):
                break
            time.sleep(0.05)
        return self

    def __exit__(self, *exc) -> None:
        if self._server:
            self._server.should_exit = True
        if self._thread:
            self._thread.join(timeout=5)
