"""Workable parser test — uses a representative payload, no network."""
from __future__ import annotations

from app.services.discovery import workable

_PAYLOAD = {
    "name": "Mercier Consultancy",
    "description": "<p>We consult.</p>",
    "jobs": [
        {
            "title": "Senior Python Engineer",
            "shortcode": "9027EBDF1B",
            "telecommuting": True,
            "department": "Engineering",
            "url": "https://apply.workable.com/mercier/j/9027EBDF1B/",
            "application_url": "https://apply.workable.com/mercier/j/9027EBDF1B/apply/",
            "published_on": "2026-06-01",
            "locations": [{"city": "Athens", "region": "Attica", "country": "Greece"}],
            "description": "<p>Build APIs with <b>Python</b> and AWS. PostgreSQL a plus.</p>",
        },
        {
            "title": "Data Analyst",
            "shortcode": "AA11BB22",
            "telecommuting": False,
            "city": "Berlin",
            "country": "Germany",
            "application_url": "https://apply.workable.com/mercier/j/AA11BB22/apply/",
            "description": "<p>SQL and dashboards.</p>",
        },
    ],
}


def test_parse_maps_fields_and_extracts_skills():
    jobs = workable.parse(_PAYLOAD, "mercier")
    assert len(jobs) == 2

    j0 = jobs[0]
    assert j0.company == "Mercier Consultancy"
    assert j0.title == "Senior Python Engineer"
    assert j0.ats_vendor == "workable"
    assert j0.external_id == "9027EBDF1B"
    assert j0.location == "Remote"                       # telecommuting
    assert "apply" in j0.url
    assert "<" not in j0.description                       # HTML stripped
    assert "python" in j0.skills and "aws" in j0.skills    # auto skill extraction

    j1 = jobs[1]
    assert j1.location == "Berlin, Germany"               # composed from city/country


def test_aggregator_registers_workable():
    from app.services.discovery.aggregator import _VENDORS
    assert "workable" in _VENDORS


def test_location_and_external_id_fallbacks():
    payload = {
        "name": "Acme",
        "jobs": [
            {"title": "A", "shortcode": "SC1",
             "locations": [{"city": "Paris", "region": "Ile-de-France", "country": "France"}]},
            {"title": "B", "shortcode": "SC2"},                    # no location at all
            {"title": "C", "code": "CODE3"},                        # only `code`, no shortcode
            {"title": "D"},                                          # neither id
        ],
    }
    jobs = workable.parse(payload, "acme")
    assert jobs[0].location == "Paris, Ile-de-France, France"       # locations[] join order
    assert jobs[1].location == ""                                    # nothing to compose
    assert jobs[2].external_id == "CODE3"                            # shortcode -> code fallback
    assert jobs[3].external_id == ""                                 # neither present
