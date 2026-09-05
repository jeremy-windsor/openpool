from __future__ import annotations

import pytest

from openpool import services

CAL_HYPO = {
    "goal": "raise_fc",
    "product": "cal_hypo",
    "current": 0,
    "target": 6,
    "pool_gallons": 10_000,
    "strength": 65,
    "strength_confirmed": True,
    "strength_product": "cal_hypo",
}


@pytest.mark.parametrize(
    "overrides",
    [
        {"strength": 10},
        {"strength": "10"},
        {"strength": None},
        {"strength_confirmed": False},
        {"strength_confirmed": None},
        {"strength_product": "liquid_chlorine"},
        {"strength_product": None},
    ],
)
def test_cal_hypo_rejects_unsafe_or_unconfirmed_requests_on_all_paths(client, overrides):
    payload = {**CAL_HYPO, **overrides}
    with pytest.raises(ValueError):
        services.calculate_goal({"volume_gallons": 10_000}, payload["goal"], payload)
    response = client.post("/api/pools/example/calculate", json=payload)
    assert response.status_code in {400, 422}
    assert "dose" not in response.json()
    params = {k: v for k, v in payload.items() if v is not None}
    page = client.get("/calculator", params=params)
    assert page.status_code == 200
    assert 'class="dose-card"' not in page.text
    assert "Log this dose" not in page.text


@pytest.mark.parametrize("confirmation", ["false", "true", 1, 0, [], {}])
def test_api_confirmation_requires_json_boolean(client, confirmation):
    response = client.post(
        "/api/pools/example/calculate", json={**CAL_HYPO, "strength_confirmed": confirmation}
    )
    assert response.status_code == 422


def test_cal_hypo_confirmed_dose_and_log_use_actual_strength(client):
    response = client.post("/api/pools/example/calculate", json=CAL_HYPO)
    assert response.status_code == 200
    assert response.json()["dose"]["amount"] == 12.3
    assert response.json()["dose"]["unit"] == "oz_weight"
    assert response.json()["strengthPercent"] == 65
    page = client.get("/calculator", params=CAL_HYPO)
    assert "Add 12.3 oz weight" in page.text
    assert "Confirmed label strength: 65%" in page.text
    assert "strength_percent=65&amp;reason=raise_fc" in page.text
    confirmation = page.text.split('name="strength_confirmed"', 1)[1].split(">", 1)[0]
    assert "checked" not in confirmation  # Every new calculation needs confirmation.


@pytest.mark.parametrize(
    "goal,product,strength",
    [
        ("raise_fc", "liquid_chlorine", 10),
        ("slam_fc", "liquid_chlorine", 10),
        ("lower_ph", "muriatic_acid", 31.45),
    ],
)
def test_variable_strength_goals_require_explicit_confirmation(client, goal, product, strength):
    payload = {"goal": goal, "current": 7.8, "target": 7.5, "ta": 100, "cya": 40}
    response = client.post("/api/pools/example/calculate", json=payload)
    assert response.status_code == 400
    payload.update(strength=strength, strength_product=product, strength_confirmed=True)
    assert client.post("/api/pools/example/calculate", json=payload).status_code == 200


def test_slam_rejects_stale_cal_hypo_product_even_with_liquid_confirmation(client):
    payload = {
        **CAL_HYPO,
        "goal": "slam_fc",
        "cya": 40,
        "strength": 10,
        "strength_product": "liquid_chlorine",
    }
    response = client.post("/api/pools/example/calculate", json=payload)
    assert response.status_code == 400
    assert "uses liquid_chlorine" in response.json()["detail"]


@pytest.mark.parametrize("product", ["trichlor", "dichlor"])
def test_fixed_dry_formulations_do_not_log_a_liquid_strength(client, product):
    page = client.get(
        "/calculator", params={"goal": "raise_fc", "product": product, "current": 0, "target": 6}
    )
    assert 'class="dose-card"' in page.text
    assert "strength_percent=" not in page.text


def test_initial_cal_hypo_form_suggests_product_specific_strength(client):
    page = client.get("/calculator", params={"product": "cal_hypo"})
    assert 'name="strength" inputmode="decimal" value="65"' in page.text
    assert 'name="strength_product" value="cal_hypo"' in page.text
    assert 'class="dose-card"' not in page.text


def test_invalid_saved_liquid_strength_refuses_recommendation_without_crashing():
    from datetime import UTC, datetime

    now = datetime(2026, 9, 5, 12, tzinfo=UTC)
    pool = {"volume_gallons": 10_000, "default_chlorine_percent": 65, "timezone": "UTC"}
    reading = {"fc": 1, "cya": 40, "tested_at": now.isoformat()}
    actions = services.recommended_actions(pool, reading, now=now)
    assert "dose" not in actions[0]
    assert "liquid_chlorine strength" in actions[0]["why"]
