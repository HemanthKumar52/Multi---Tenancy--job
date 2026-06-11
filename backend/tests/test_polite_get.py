"""polite_get: per-host pacing + retry/backoff with Retry-After. No real network or sleeping."""
from __future__ import annotations

import httpx
import pytest

from app.services.discovery import base


class FakeResp:
    def __init__(self, status: int, headers: dict | None = None):
        self.status_code = status
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=None)  # type: ignore[arg-type]


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    base._last_hit.clear()
    # Never actually sleep; record requested delays instead.
    self_sleeps: list[float] = []
    monkeypatch.setattr(base.time, "sleep", lambda s: self_sleeps.append(s))
    yield self_sleeps


def test_retries_on_503_then_succeeds(monkeypatch, _reset):
    responses = [FakeResp(503, {"Retry-After": "2"}), FakeResp(200)]
    calls = {"n": 0}

    def fake_get(url, **kw):
        i = calls["n"]; calls["n"] += 1
        return responses[i]

    monkeypatch.setattr(base.httpx, "get", fake_get)
    resp = base.polite_get("https://api.example.com/x")
    assert resp.status_code == 200
    assert calls["n"] == 2                       # retried once
    assert 2.0 in _reset                          # honored Retry-After: 2


def test_raises_after_exhausting_retries(monkeypatch, _reset):
    monkeypatch.setattr(base.httpx, "get", lambda url, **kw: FakeResp(503))
    with pytest.raises(httpx.HTTPStatusError):
        base.polite_get("https://api.example.com/x", retries=1)


def test_paces_repeated_hits_to_same_host(monkeypatch, _reset):
    monkeypatch.setattr(base.httpx, "get", lambda url, **kw: FakeResp(200))
    base.polite_get("https://api.example.com/a")   # first hit — no wait
    base.polite_get("https://api.example.com/b")   # second hit — must be paced
    assert any(s > 0 for s in _reset)


def test_distinct_hosts_not_paced_against_each_other(monkeypatch, _reset):
    monkeypatch.setattr(base.httpx, "get", lambda url, **kw: FakeResp(200))
    base.polite_get("https://host-one.example.com/a")
    base.polite_get("https://host-two.example.com/a")
    assert all(s <= 0 for s in _reset) or _reset == []   # no inter-host pacing sleep
