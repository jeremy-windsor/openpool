from __future__ import annotations


def test_health_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["app"] == "openpool"


def test_version_reports_build_metadata(client):
    body = client.get("/api/version").json()
    assert body["app"] == "openpool"
    assert "buildSha" in body
    assert "buildRef" in body


def test_dashboard_renders(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "openpool" in response.text.lower()


def test_create_and_list_reading(client):
    created = client.post(
        "/api/pools/example/readings",
        json={"fc": 3, "cc": 0.5, "ph": 7.6, "cya": 40},
    )
    assert created.status_code == 201
    assert created.json()["tc"] == 3.5

    listed = client.get("/api/pools/example/readings").json()
    assert len(listed) == 1
    latest = client.get("/api/pools/example/readings/latest").json()
    assert latest["fc"] == 3


def test_calculate_liquid_chlorine(client):
    response = client.post(
        "/api/pools/example/calculate",
        json={"goal": "raise_fc", "current": 4, "target": 5, "pool_gallons": 10000},
    )
    assert response.status_code == 200
    dose = response.json()["dose"]
    assert dose["unit"] == "fl_oz"
    assert abs(dose["amount"] - 12.8) < 0.5


def test_readings_csv_export(client):
    client.post("/api/pools/example/readings", json={"fc": 3, "cya": 40})
    response = client.get("/api/pools/example/export/readings.csv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "tested_at" in response.text


def test_share_disabled_returns_403(client):
    assert client.get("/share/example.json").status_code == 403


def test_share_enabled_with_token(client):
    client.put(
        "/api/pools/example",
        json={"share_enabled": True, "share_token": "read-only-token-123"},
    )
    denied = client.get("/share/example.json")
    assert denied.status_code == 403
    allowed = client.get("/share/example.json", params={"token": "read-only-token-123"})
    assert allowed.status_code == 200
    assert allowed.json()["pool"]["id"] == "example"


def test_share_response_never_includes_token(client):
    pools = client.get("/api/pools").json()
    assert all("share_token" not in pool for pool in pools)


def test_unknown_pool_returns_404(client):
    assert client.get("/api/pools/missing/readings").status_code == 404


def test_form_post_reading_redirects_and_persists(client):
    response = client.post(
        "/readings/new",
        data={"fc": "4", "cya": "40", "ph": "7.5"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    latest = client.get("/api/pools/example/readings/latest").json()
    assert latest["fc"] == 4
