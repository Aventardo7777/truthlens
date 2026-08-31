"""API integration tests using FastAPI TestClient."""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from backend.api.main import app

client = TestClient(app)
DEMO = Path(__file__).resolve().parent.parent / "datasets" / "examples" / "suspicious_sales.xlsx"


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_demo_scan():
    r = client.get("/api/demo")
    assert r.status_code == 200
    body = r.json()
    assert body["scan_id"]
    assert body["case_number"].startswith("TL-")
    assert body["integrity"]["total"] > 0
    assert len(body["findings"]) >= 10
    assert body["correlation_network"]["nodes"]


def test_upload_scan():
    with DEMO.open("rb") as f:
        r = client.post("/api/analyze", files={"file": (DEMO.name, f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert r.status_code == 200
    body = r.json()
    assert body["filename"] == DEMO.name
    assert body["n_rows"] > 0


def test_report_html():
    scan_id = client.get("/api/demo").json()["scan_id"]
    r = client.get(f"/api/analyses/{scan_id}/report", params={"format": "html"})
    assert r.status_code == 200
    assert "<html" in r.text.lower()


def test_report_json():
    scan_id = client.get("/api/demo").json()["scan_id"]
    r = client.get(f"/api/analyses/{scan_id}/report", params={"format": "json"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")


def test_report_pdf():
    scan_id = client.get("/api/demo").json()["scan_id"]
    r = client.get(f"/api/analyses/{scan_id}/report", params={"format": "pdf"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/pdf")
    assert r.content[:4] == b"%PDF"


def test_unknown_scan_404():
    r = client.get("/api/analyses/does-not-exist")
    assert r.status_code == 404
