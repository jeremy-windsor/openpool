from __future__ import annotations

import json
import struct
from datetime import date, timedelta
from pathlib import Path

STATIC_DIR = Path(__file__).parents[1] / "openpool" / "static"


def _png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    assert data[12:16] == b"IHDR"
    return struct.unpack(">II", data[16:24])


def test_health_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["app"] == "openpool"


def test_responses_include_nosniff_header(client):
    response = client.get("/api/health")

    assert response.headers["x-content-type-options"] == "nosniff"


def test_version_reports_build_metadata(client):
    body = client.get("/api/version").json()
    assert body["app"] == "openpool"
    assert "buildSha" in body
    assert "buildRef" in body


def test_dashboard_renders(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "openpool" in response.text.lower()


def test_app_shell_links_icons_and_manifest(client):
    response = client.get("/")

    assert response.status_code == 200
    assert 'href="/static/favicon.svg"' in response.text
    assert 'href="/static/icon-192.png"' in response.text
    assert 'href="/static/apple-touch-icon.png"' in response.text
    assert 'href="/static/manifest.webmanifest"' in response.text

    favicon = STATIC_DIR / "favicon.svg"
    assert favicon.exists()
    assert "<svg" in favicon.read_text()

    expected_pngs = {
        "icon-192.png": (192, 192),
        "icon-512.png": (512, 512),
        "apple-touch-icon.png": (180, 180),
    }
    for filename, size in expected_pngs.items():
        assert _png_size(STATIC_DIR / filename) == size

    manifest = json.loads((STATIC_DIR / "manifest.webmanifest").read_text())
    icons = {icon["src"]: icon for icon in manifest["icons"]}
    assert icons["/static/icon-192.png"]["sizes"] == "192x192"
    assert icons["/static/icon-192.png"]["type"] == "image/png"
    assert icons["/static/icon-512.png"]["sizes"] == "512x512"
    assert icons["/static/icon-512.png"]["type"] == "image/png"


def test_dashboard_cautions_for_non_chlorine_out_of_range_readings(client):
    created = client.post(
        "/api/pools/example/readings",
        json={"fc": 6, "cya": 40, "ch": 900, "csi": 0.7},
    )
    assert created.status_code == 201

    response = client.get("/")

    assert response.status_code == 200
    assert "2 readings outside range" in response.text
    assert "Balanced - no action needed" not in response.text


def test_help_page_links_generated_api_docs(client):
    response = client.get("/help")

    assert response.status_code == 200
    assert 'href="/docs"' in response.text
    assert 'href="/redoc"' in response.text
    assert 'href="/openapi.json"' in response.text


def test_help_page_uses_configured_default_pool_id(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.delenv("OPENPOOL_DATABASE_URL", raising=False)
    monkeypatch.setenv("OPENPOOL_DB", str(tmp_path / "openpool.sqlite"))
    monkeypatch.setenv("OPENPOOL_DEFAULT_POOL_ID", "configured-pool")
    monkeypatch.setenv("OPENPOOL_TIMEZONE", "America/Phoenix")

    from openpool.main import create_app

    with TestClient(create_app()) as test_client:
        response = test_client.get("/help")

    assert response.status_code == 200
    assert "http://testserver/api/pools/configured-pool/readings" in response.text


def test_openapi_json_returns_expected_document(client):
    response = client.get("/openapi.json")

    assert response.status_code == 200
    body = response.json()
    assert {"openapi", "info", "paths"} <= body.keys()
    assert body["info"]["title"] == "openpool"
    assert isinstance(body["paths"], dict)


def test_openapi_paths_match_current_routes(client):
    response = client.get("/openapi.json")

    assert set(response.json()["paths"]) == {
        "/",
        "/additions/new",
        "/additions/{addition_id}/delete",
        "/additions/{addition_id}/edit",
        "/api/health",
        "/api/pools",
        "/api/pools/{pool_id}",
        "/api/pools/{pool_id}/additions",
        "/api/pools/{pool_id}/additions/{addition_id}",
        "/api/pools/{pool_id}/calculate",
        "/api/pools/{pool_id}/export/additions.csv",
        "/api/pools/{pool_id}/export/all.json",
        "/api/pools/{pool_id}/export/maintenance.csv",
        "/api/pools/{pool_id}/export/readings.csv",
        "/api/pools/{pool_id}/maintenance",
        "/api/pools/{pool_id}/maintenance/{event_id}",
        "/api/pools/{pool_id}/readings",
        "/api/pools/{pool_id}/readings/latest",
        "/api/pools/{pool_id}/readings/{reading_id}",
        "/api/pools/{pool_id}/share.json",
        "/api/version",
        "/calculator",
        "/help",
        "/history",
        "/maintenance/new",
        "/maintenance/{event_id}/delete",
        "/maintenance/{event_id}/edit",
        "/readings/new",
        "/readings/{reading_id}/delete",
        "/readings/{reading_id}/edit",
        "/settings",
        "/share/{pool_id}",
        "/share/{pool_id}.json",
    }


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


def test_bad_z_timestamp_returns_400(client):
    response = client.post(
        "/api/pools/example/readings",
        json={"tested_at": "2026-99-99T00:00Z", "fc": 3},
    )

    assert response.status_code == 400
    assert "invalid timestamp" in response.json()["detail"]


def test_malformed_stored_timestamp_does_not_crash_pages(client):
    from openpool import db
    from openpool.config import get_settings

    created = client.post(
        "/api/pools/example/readings",
        json={"tested_at": "2026-06-01T12:00:00Z", "fc": 3},
    ).json()

    conn = db.connect(get_settings().db_path)
    try:
        conn.execute(
            "update test_readings set tested_at = ? where id = ?",
            ("bad-timestampZ", created["id"]),
        )
        conn.commit()
    finally:
        conn.close()

    dashboard = client.get("/")
    history = client.get("/history")

    assert dashboard.status_code == 200
    assert history.status_code == 200
    assert "bad-timestampZ" in dashboard.text
    assert "bad-timestampZ" in history.text


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


def test_pool_update_preserves_existing_share_token(client):
    client.put(
        "/api/pools/example",
        json={"share_enabled": True, "share_token": "read-only-token-123"},
    )

    updated = client.put(
        "/api/pools/example",
        json={"name": "Renamed Pool", "share_enabled": True},
    )
    allowed = client.get("/share/example.json", params={"token": "read-only-token-123"})

    assert updated.status_code == 200
    assert updated.json()["name"] == "Renamed Pool"
    assert allowed.status_code == 200


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


def test_update_and_delete_reading(client):
    created = client.post(
        "/api/pools/example/readings",
        json={"fc": 3, "cc": 0.5, "ph": 7.6, "ta": 70, "ch": 350, "cya": 40},
    ).json()

    updated = client.put(
        f"/api/pools/example/readings/{created['id']}",
        json={"fc": 5},
    )
    assert updated.status_code == 200
    assert updated.json()["fc"] == 5
    assert updated.json()["tc"] == 5.5

    fetched = client.get(f"/api/pools/example/readings/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["fc"] == 5

    deleted = client.delete(f"/api/pools/example/readings/{created['id']}")
    assert deleted.status_code == 204
    assert client.get(f"/api/pools/example/readings/{created['id']}").status_code == 404


def test_update_missing_reading_returns_404(client):
    assert client.put("/api/pools/example/readings/nope", json={"fc": 5}).status_code == 404
    assert client.delete("/api/pools/example/readings/nope").status_code == 404


def test_csi_computed_and_recomputed(client):
    created = client.post(
        "/api/pools/example/readings",
        json={"fc": 5, "ph": 7.5, "ta": 70, "ch": 350, "cya": 40, "salt": 3000, "water_temp_f": 80},
    ).json()
    assert created["csi"] is not None
    assert abs(created["csi"] - (-0.21)) < 0.03

    updated = client.put(
        f"/api/pools/example/readings/{created['id']}",
        json={"ch": 600},
    ).json()
    assert updated["csi"] > created["csi"]


def test_csi_missing_inputs_stays_none(client):
    created = client.post("/api/pools/example/readings", json={"fc": 5, "ph": 7.5}).json()
    assert created["csi"] is None


def test_update_and_delete_addition(client):
    created = client.post(
        "/api/pools/example/additions",
        json={"chemical": "liquid_chlorine", "amount": 32, "unit": "fl_oz"},
    ).json()

    updated = client.put(
        f"/api/pools/example/additions/{created['id']}",
        json={"amount": 64},
    )
    assert updated.status_code == 200
    assert updated.json()["amount"] == 64

    deleted = client.delete(f"/api/pools/example/additions/{created['id']}")
    assert deleted.status_code == 204
    assert client.get("/api/pools/example/additions").json() == []


def test_maintenance_crud_and_export(client):
    created = client.post(
        "/api/pools/example/maintenance",
        json={"event_type": "backwash", "notes": "20 psi -> 12 psi"},
    )
    assert created.status_code == 201
    event = created.json()
    assert event["event_type"] == "backwash"

    listed = client.get("/api/pools/example/maintenance").json()
    assert len(listed) == 1

    updated = client.put(
        f"/api/pools/example/maintenance/{event['id']}",
        json={"event_type": "clean_filter"},
    )
    assert updated.status_code == 200
    assert updated.json()["event_type"] == "clean_filter"

    csv_export = client.get("/api/pools/example/export/maintenance.csv")
    assert csv_export.status_code == 200
    assert "clean_filter" in csv_export.text

    backup = client.get("/api/pools/example/export/all.json").json()
    assert len(backup["maintenance"]) == 1

    deleted = client.delete(f"/api/pools/example/maintenance/{event['id']}")
    assert deleted.status_code == 204
    assert client.get("/api/pools/example/maintenance").json() == []


def test_maintenance_requires_event_type(client):
    response = client.post("/api/pools/example/maintenance", json={"notes": "missing type"})
    assert response.status_code == 422


def test_calculate_ch_and_ta_goals(client):
    ch = client.post(
        "/api/pools/example/calculate",
        json={"goal": "raise_ch", "current": 240, "target": 250, "pool_gallons": 10000},
    )
    assert ch.status_code == 200
    assert ch.json()["dose"]["chemical"] == "calcium_chloride_dihydrate"
    assert abs(ch.json()["dose"]["amount"] - 19.6) < 0.5

    ta = client.post(
        "/api/pools/example/calculate",
        json={"goal": "raise_ta", "current": 60, "target": 70, "pool_gallons": 10000},
    )
    assert ta.status_code == 200
    assert ta.json()["dose"]["chemical"] == "baking_soda"
    assert abs(ta.json()["dose"]["amount"] - 22.4) < 0.5


def test_reading_edit_pages(client):
    client.post("/readings/new", data={"fc": "4", "ph": "7.8", "ta": "70", "ch": "350"})
    reading = client.get("/api/pools/example/readings/latest").json()

    edit_page = client.get(f"/readings/{reading['id']}/edit")
    assert edit_page.status_code == 200
    assert "Edit Reading" in edit_page.text

    saved = client.post(
        f"/readings/{reading['id']}/edit",
        data={"fc": "6", "ph": "7.4", "ta": "70", "ch": "350"},
        follow_redirects=False,
    )
    assert saved.status_code == 303
    updated = client.get("/api/pools/example/readings/latest").json()
    assert updated["fc"] == 6
    assert updated["ph"] == 7.4
    assert updated["csi"] is not None

    deleted = client.post(f"/readings/{reading['id']}/delete", follow_redirects=False)
    assert deleted.status_code == 303
    assert client.get("/api/pools/example/readings").json() == []


def test_addition_edit_pages(client):
    client.post(
        "/additions/new",
        data={"chemical": "liquid_chlorine", "amount": "32", "unit": "fl_oz"},
    )
    addition = client.get("/api/pools/example/additions").json()[0]

    edit_page = client.get(f"/additions/{addition['id']}/edit")
    assert edit_page.status_code == 200
    assert "Edit Addition" in edit_page.text

    saved = client.post(
        f"/additions/{addition['id']}/edit",
        data={"chemical": "baking_soda", "amount": "22.4", "unit": "oz_weight"},
        follow_redirects=False,
    )
    assert saved.status_code == 303
    updated = client.get("/api/pools/example/additions").json()[0]
    assert updated["chemical"] == "baking_soda"
    assert updated["amount"] == 22.4

    deleted = client.post(f"/additions/{addition['id']}/delete", follow_redirects=False)
    assert deleted.status_code == 303
    assert client.get("/api/pools/example/additions").json() == []


def test_maintenance_pages(client):
    form_page = client.get("/maintenance/new")
    assert form_page.status_code == 200

    saved = client.post(
        "/maintenance/new",
        data={"event_type": "backwash", "notes": "weekly"},
        follow_redirects=False,
    )
    assert saved.status_code == 303
    event = client.get("/api/pools/example/maintenance").json()[0]

    history = client.get("/history")
    assert "backwash" in history.text

    edited = client.post(
        f"/maintenance/{event['id']}/edit",
        data={"event_type": "vacuum"},
        follow_redirects=False,
    )
    assert edited.status_code == 303
    assert client.get("/api/pools/example/maintenance").json()[0]["event_type"] == "vacuum"

    deleted = client.post(f"/maintenance/{event['id']}/delete", follow_redirects=False)
    assert deleted.status_code == 303
    assert client.get("/api/pools/example/maintenance").json() == []


def test_calculate_raise_fc_with_trichlor_reports_cya_effect(client):
    response = client.post(
        "/api/pools/example/calculate",
        json={
            "goal": "raise_fc",
            "current": 0,
            "target": 10,
            "pool_gallons": 10000,
            "product": "trichlor",
        },
    )
    assert response.status_code == 200
    dose = response.json()["dose"]
    assert dose["chemical"] == "trichlor"
    assert abs(dose["effects"]["cya"] - 6.1) < 0.3
    assert any("acidic" in warning for warning in dose["warnings"])


def test_calculate_slam_uses_cya_shock_target(client):
    response = client.post(
        "/api/pools/example/calculate",
        json={"goal": "slam_fc", "current": 4, "cya": 40, "pool_gallons": 10000},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["targetFc"] == 16
    assert body["dose"]["chemical"] == "liquid_chlorine"
    assert any("SLAM is a process" in warning for warning in body["dose"]["warnings"])


def test_calculate_lower_ph_returns_acid_and_ta_effect(client):
    response = client.post(
        "/api/pools/example/calculate",
        json={
            "goal": "lower_ph",
            "current": 7.8,
            "target": 7.5,
            "ta": 100,
            "cya": 40,
            "pool_gallons": 10000,
        },
    )
    assert response.status_code == 200
    dose = response.json()["dose"]
    assert dose["chemical"] == "muriatic_acid"
    assert dose["confidence"] == "medium"
    assert abs(dose["amount"] - 10.1) < 1.0
    assert dose["effects"]["ta"] < 0


def test_calculate_lower_ph_missing_ta_is_400(client):
    response = client.post(
        "/api/pools/example/calculate",
        json={"goal": "lower_ph", "current": 7.8, "target": 7.5},
    )
    assert response.status_code == 400
    assert "ta" in response.json()["detail"]


def test_calculate_raise_ph_returns_soda_ash(client):
    response = client.post(
        "/api/pools/example/calculate",
        json={
            "goal": "raise_ph",
            "current": 7.2,
            "target": 7.5,
            "ta": 70,
            "cya": 40,
            "pool_gallons": 10000,
        },
    )
    assert response.status_code == 200
    dose = response.json()["dose"]
    assert dose["chemical"] == "soda_ash"
    assert dose["confidence"] == "low"
    assert abs(dose["amount"] - 12.3) < 1.0
    assert any("Aeration" in warning for warning in dose["warnings"])


def test_calculate_dilution(client):
    response = client.post(
        "/api/pools/example/calculate",
        json={
            "goal": "lower_by_dilution",
            "current": 100,
            "target": 50,
            "pool_gallons": 20000,
        },
    )
    assert response.status_code == 200
    dose = response.json()["dose"]
    assert dose["chemical"] == "water_replacement"
    assert dose["amount"] == 10000
    assert dose["secondary"]["percent_of_pool"] == 50


def test_calculate_swg_runtime(client):
    response = client.post(
        "/api/pools/example/calculate",
        json={
            "goal": "swg_runtime",
            "target": 4,
            "cell_lbs_per_day": 1.4,
            "pump_hours": 24,
            "pool_gallons": 10000,
        },
    )
    assert response.status_code == 200
    dose = response.json()["dose"]
    assert dose["unit"] == "percent"
    assert abs(dose["amount"] - 24) <= 1


def test_calculate_swg_runtime_missing_cell_rating_is_400(client):
    response = client.post(
        "/api/pools/example/calculate",
        json={"goal": "swg_runtime", "target": 4},
    )
    assert response.status_code == 400
    assert "cell_lbs_per_day" in response.json()["detail"]


def test_calculator_page_renders_new_goals(client):
    response = client.get(
        "/calculator",
        params={"goal": "lower_ph", "current": 7.8, "target": 7.5, "ta": 100},
    )
    assert response.status_code == 200
    assert "muriatic acid" in response.text
    assert "Also changes" in response.text


def test_calculator_page_accepts_blank_optional_numeric_query_fields(client):
    response = client.get(
        "/calculator?goal=raise_fc&product=liquid_chlorine&current=6&target=12"
        "&ta=&cya=&borates=&cell_lbs_per_day=&pump_hours=&pool_gallons=18500&strength=12"
    )

    assert response.status_code == 200
    assert "Add 118.4 fl oz" in response.text
    assert "liquid chlorine" in response.text


def test_calculator_page_shows_inline_error_for_invalid_numeric_query(client):
    response = client.get(
        "/calculator",
        params={"goal": "raise_fc", "current": "six", "target": "12"},
    )

    assert response.status_code == 200
    assert "current must be a number" in response.text


def test_calculator_page_shows_inline_error_instead_of_400(client):
    response = client.get(
        "/calculator",
        params={"goal": "lower_ph", "current": 7.8, "target": 7.5},
    )
    assert response.status_code == 200
    assert "lower_ph needs: ta" in response.text


def test_calculator_page_without_params_renders_form(client):
    response = client.get("/calculator")

    assert response.status_code == 200
    assert "<h1>Calculator</h1>" in response.text
    assert "dose-card" not in response.text


def test_history_filters_by_record_type_and_date(client):
    client.post(
        "/api/pools/example/readings",
        json={"tested_at": "2026-06-01T12:00:00+00:00", "fc": 5},
    )
    client.post(
        "/api/pools/example/additions",
        json={
            "added_at": "2026-06-05T12:00:00+00:00",
            "chemical": "liquid_chlorine",
            "amount": 10,
            "unit": "fl_oz",
        },
    )

    response = client.get("/history", params={"record": "additions"})
    assert response.status_code == 200
    assert "liquid chlorine" in response.text
    assert "Tested" not in response.text  # readings table hidden

    response = client.get(
        "/history", params={"start": "2026-06-04", "end": "2026-06-06"}
    )
    assert response.status_code == 200
    assert "liquid chlorine" in response.text


def test_history_date_range_finds_rows_older_than_newest_100(client):
    from openpool import db
    from openpool.config import get_settings

    conn = db.connect(get_settings().db_path)
    try:
        for offset in range(120):
            day = date(2026, 7, 1) + timedelta(days=offset)
            db.create_reading(
                conn,
                "example",
                {"tested_at": f"{day.isoformat()}T12:00:00Z", "fc": 10 + offset},
            )
        db.create_reading(
            conn,
            "example",
            {"tested_at": "2026-03-10T12:00:00Z", "fc": 1.23},
        )
        db.create_reading(
            conn,
            "example",
            {"tested_at": "2026-03-11T12:00:00Z", "fc": 2.34},
        )
    finally:
        conn.close()

    response = client.get(
        "/history",
        params={"record": "readings", "start": "2026-03-10", "end": "2026-03-11"},
    )

    assert response.status_code == 200
    assert "1.23" in response.text
    assert "2.34" in response.text


def test_history_date_range_uses_pool_local_inclusive_days(client):
    for tested_at, fc in [
        ("2026-06-01T06:59:59Z", 1.01),
        ("2026-06-01T07:00:00Z", 2.02),
        ("2026-06-02T06:59:59Z", 3.03),
        ("2026-06-02T07:00:00Z", 4.04),
    ]:
        client.post(
            "/api/pools/example/readings",
            json={"tested_at": tested_at, "fc": fc},
        )

    response = client.get(
        "/history",
        params={"record": "readings", "start": "2026-06-01", "end": "2026-06-01"},
    )

    assert response.status_code == 200
    assert "2.02" in response.text
    assert "3.03" in response.text
    assert "1.01" not in response.text
    assert "4.04" not in response.text
