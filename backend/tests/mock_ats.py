"""Local mock ATS apply forms (Greenhouse / Lever / Ashby) for safely testing the Playwright
adapters without ever contacting a real company. Reproduces each vendor's real field selectors,
submit control, and success markup."""
from __future__ import annotations

import threading
import time

import uvicorn
from starlette.applications import Starlette
from starlette.datastructures import UploadFile
from starlette.responses import HTMLResponse
from starlette.routing import Route

GREENHOUSE_FORM = """<!doctype html><html><body>
<form id="application-form" action="/mock/greenhouse/confirmation" method="post" enctype="multipart/form-data">
  <label for="first_name">First Name *</label><input id="first_name" name="first_name" type="text" aria-required="true">
  <label for="last_name">Last Name *</label><input id="last_name" name="last_name" type="text">
  <label for="email">Email *</label><input id="email" name="email" type="email">
  <label for="phone">Phone</label><input id="phone" name="phone" type="tel">
  <div role="group" aria-labelledby="upload-label-resume"><div id="upload-label-resume">Resume/CV</div>
    <input id="resume" name="resume" type="file" accept=".pdf,.doc,.docx,.txt,.rtf"></div>
  <label for="question_1">Why do you want to work here?</label><textarea id="question_1" name="question_1"></textarea>
  <label for="question_2">Are you authorized to work?</label><input id="question_2" name="question_2" type="text">
  <button type="submit">Submit application</button>
</form></body></html>"""

LEVER_FORM = """<!doctype html><html><body>
<form id="lever-form" action="/mock/lever/thanks" method="post" enctype="multipart/form-data">
  <input name="name" type="text" placeholder="Full name">
  <input name="email" type="email">
  <input name="phone" type="tel">
  <input id="resume-upload-input" name="resume" type="file">
  <a id="btn-submit" data-qa="btn-submit" href="#"
     onclick="document.getElementById('lever-form').submit();return false;">Submit application</a>
</form></body></html>"""

ASHBY_FORM = """<!doctype html><html><body>
<div class="ashby-application-form-container">
<form id="ashby-form" action="/mock/ashby/done" method="post" enctype="multipart/form-data">
  <input aria-label="Name" name="name" type="text">
  <input aria-label="Email" name="email" type="email">
  <input aria-label="Phone" name="phone" type="tel">
  <input type="file" name="resume">
  <button class="ashby-application-form-submit-button" type="submit">Submit Application</button>
</form></div></body></html>"""

FORMS = {"greenhouse": GREENHOUSE_FORM, "lever": LEVER_FORM, "ashby": ASHBY_FORM}

SUCCESS = {
    "greenhouse": "<!doctype html><html><body><h1>Thank you for applying</h1>"
                  "<p>Your submission has been received.</p></body></html>",
    "lever": "<!doctype html><html><body class='page thanks'>"
             "<h3 data-qa='msg-submit-success'>Application submitted!</h3></body></html>",
    "ashby": "<!doctype html><html><body>"
             "<div class='ashby-application-form-success-container'>Application submitted</div></body></html>",
}

HANDOFF_FORM_HTML = """<!doctype html><html><body>
<form id="application-form">
  <div class="g-recaptcha" data-sitekey="test-sitekey"></div>
  <label for="account-password">Sign in to continue</label>
  <input id="account-password" name="pw" type="password">
</form></body></html>"""


class MockATS:
    def __init__(self, port: int = 8791, handoff: bool = False, vendor: str = "greenhouse"):
        self.port = port
        self.handoff = handoff
        self.vendor = vendor
        self.received: dict = {}
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None

        async def apply(request):
            if self.handoff:
                return HTMLResponse(HANDOFF_FORM_HTML)
            v = request.path_params["vendor"]
            return HTMLResponse(FORMS.get(v, GREENHOUSE_FORM))

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
            path = request.url.path
            vendor = "lever" if "lever" in path else "ashby" if "ashby" in path else "greenhouse"
            return HTMLResponse(SUCCESS[vendor])

        self.app = Starlette(routes=[
            Route("/mock/{vendor}/apply", apply, methods=["GET"]),
            Route("/mock/greenhouse/confirmation", confirm, methods=["GET", "POST"]),
            Route("/mock/lever/thanks", confirm, methods=["GET", "POST"]),
            Route("/mock/ashby/done", confirm, methods=["GET", "POST"]),
        ])

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    @property
    def apply_url(self) -> str:
        return f"{self.base_url}/mock/{self.vendor}/apply"

    def __enter__(self) -> "MockATS":
        config = uvicorn.Config(self.app, host="127.0.0.1", port=self.port, log_level="warning")
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, daemon=True)
        self._thread.start()
        for _ in range(200):
            if getattr(self._server, "started", False):
                break
            time.sleep(0.05)
        return self

    def __exit__(self, *exc) -> None:
        if self._server:
            self._server.should_exit = True
        if self._thread:
            self._thread.join(timeout=5)


# Back-compat alias for existing Greenhouse tests.
MockGreenhouse = MockATS
