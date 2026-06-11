"""Parser tests for the remote/international + gated sources. No network."""
from __future__ import annotations

from app.services.discovery import apify, remote_boards, usajobs


def test_remotive():
    jobs = remote_boards.parse_remotive({"jobs": [{
        "id": 1, "title": "Backend Engineer", "company_name": "Acme",
        "candidate_required_location": "Worldwide", "description": "<p>Python and AWS</p>",
        "url": "https://remotive.com/x", "publication_date": "2026-06-01"}]})
    assert len(jobs) == 1
    j = jobs[0]
    assert j.source == "remotive" and j.ats_vendor == "external"
    assert j.company == "Acme" and j.location == "Worldwide"
    assert "<" not in j.description and "python" in j.skills


def test_remoteok_skips_legal_header():
    jobs = remote_boards.parse_remoteok([
        {"legal": "By using this API you agree..."},                     # header element
        {"id": "123", "position": "Senior Python Dev", "company": "Globex",
         "location": "Remote", "description": "<p>Django</p>", "url": "https://remoteok.com/x",
         "date": "2026-06-01"}])
    assert len(jobs) == 1                                                # legal header skipped
    assert jobs[0].title == "Senior Python Dev" and jobs[0].company == "Globex"


def test_arbeitnow():
    jobs = remote_boards.parse_arbeitnow({"data": [{
        "slug": "abc", "company_name": "Berlin GmbH", "title": "Data Engineer",
        "description": "<p>SQL and Python</p>", "remote": True, "url": "https://arbeitnow.com/x",
        "created_at": 1700000000, "location": "Berlin"}]})
    assert jobs[0].location == "Berlin" and jobs[0].external_id == "abc"


def test_themuse_joins_locations():
    jobs = remote_boards.parse_themuse({"results": [{
        "id": 99, "name": "Frontend Dev", "company": {"name": "Muse Co"},
        "locations": [{"name": "New York"}, {"name": "Remote"}], "contents": "<p>React</p>",
        "refs": {"landing_page": "https://themuse.com/x"}, "publication_date": "2026-06-01"}]})
    assert jobs[0].location == "New York, Remote" and jobs[0].company == "Muse Co"


def test_jobicy():
    jobs = remote_boards.parse_jobicy({"jobs": [{
        "id": 5, "jobTitle": "DevOps", "companyName": "Cloudy", "jobGeo": "USA",
        "jobDescription": "<p>Kubernetes and Docker</p>", "url": "https://jobicy.com/x",
        "pubDate": "2026-06-01"}]})
    assert jobs[0].title == "DevOps" and "kubernetes" in jobs[0].skills


def test_apify_best_effort_mapping():
    jobs = apify.parse([{"title": "ML Engineer", "company": "DeepCo", "location": "London",
                         "description": "PyTorch and Python", "url": "https://x"}], "apify:linkedin")
    assert len(jobs) == 1
    assert jobs[0].source == "apify:linkedin" and jobs[0].ats_vendor == "external"
    assert jobs[0].company == "DeepCo"


def test_usajobs_parse():
    jobs = usajobs.parse({"SearchResult": {"SearchResultItems": [{"MatchedObjectDescriptor": {
        "PositionTitle": "Data Analyst", "OrganizationName": "DoD",
        "PositionLocationDisplay": "Washington, DC",
        "UserArea": {"Details": {"JobSummary": "<p>SQL and Python</p>"}},
        "PositionURI": "https://usajobs.gov/x", "PositionID": "P1",
        "PublicationStartDate": "2026-06-01"}}]}})
    assert jobs[0].title == "Data Analyst" and jobs[0].company == "DoD"
    assert "sql" in jobs[0].skills
