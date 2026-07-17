from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from openpool import services
from openpool.chemistry.dosing import PRODUCT_LABEL_WARNING

TESTED_AT = datetime(2026, 7, 17, 12, 0, tzinfo=UTC)


def _pool(**overrides):
    pool = {
        "volume_gallons": 20_000,
        "sanitizer": "liquid_chlorine",
        "default_chlorine_percent": 10,
        "jug_size_fl_oz": 128,
        "bag_size_lbs": 40,
        "timezone": "UTC",
    }
    pool.update(overrides)
    return pool


def _reading(*, fc=6, cya=40):
    return {
        "tested_at": TESTED_AT.isoformat().replace("+00:00", "Z"),
        "fc": fc,
        "cya": cya,
    }


def test_humanize_number_does_not_hide_small_nonzero_amount():
    assert services.humanize_number(0.0038) == "0.0038"
    assert services.humanize_number(-0.0038) == "-0.0038"


@pytest.mark.parametrize(
    ("goal", "values", "message"),
    [
        (
            "raise_fc",
            {"current": 1, "target": 2, "pool_gallons": 0},
            "pool_gallons",
        ),
        (
            "raise_fc",
            {"current": 1, "target": 2, "strength": 0},
            "strength",
        ),
        (
            "lower_ph",
            {"current": 7.8, "target": 7.5, "ta": 100, "strength": 0},
            "strength",
        ),
        (
            "swg_runtime",
            {"target": 4, "cell_lbs_per_day": 1.4, "pump_hours": 0},
            "pump_hours",
        ),
        (
            "swg_runtime",
            {"target": 4, "cell_lbs_per_day": 0},
            "cell_lbs_per_day",
        ),
    ],
)
def test_calculation_explicit_zero_is_not_treated_as_missing(goal, values, message):
    with pytest.raises(ValueError, match=message):
        services.calculate_goal(_pool(), goal, values)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("ta", -1),
        ("ta", 2_001),
        ("cya", -1),
        ("cya", 501),
        ("borates", -1),
        ("borates", 201),
    ],
)
def test_calculation_enforces_optional_physical_bounds(name, value):
    values = {"current": 7.8, "target": 7.5, "ta": 100, name: value}

    with pytest.raises(ValueError, match=name):
        services.calculate_goal(_pool(), "lower_ph", values)


def test_unknown_sanitizer_fails_closed_without_a_dose():
    actions = services.recommended_actions(
        _pool(sanitizer="swgg"),
        _reading(fc=1),
        now=TESTED_AT + timedelta(hours=1),
    )

    assert actions[0]["kind"] == "retest"
    assert "sanitizer must be liquid_chlorine or swg" in actions[0]["why"]
    assert "dose" not in actions[0]


def test_stale_in_range_reading_requires_retest():
    reading = _reading(fc=6)
    now = TESTED_AT + timedelta(hours=13)

    actions = services.recommended_actions(_pool(), reading, now=now)

    assert actions[0]["kind"] == "retest"
    assert "more than 12 hours old" in actions[0]["why"]
    assert services.status_summary(_pool(), reading, now=now)["level"] == "caution"


def test_stale_low_reading_leads_with_retest_status():
    reading = _reading(fc=1)
    now = TESTED_AT + timedelta(hours=13)

    assert services.status_summary(_pool(), reading, now=now) == {
        "level": "caution",
        "text": "Retest before dosing",
    }


def test_superseded_in_range_reading_requires_retest():
    reading = _reading(fc=6)
    additions = [
        {
            "chemical": "liquid_chlorine",
            "added_at": (TESTED_AT + timedelta(minutes=30)).isoformat(),
        }
    ]

    actions = services.recommended_actions(
        _pool(),
        reading,
        additions,
        now=TESTED_AT + timedelta(hours=1),
    )

    assert actions[0]["kind"] == "retest"
    assert "Chlorine was logged" in actions[0]["why"]
    assert services.status_summary(
        _pool(), reading, additions, now=TESTED_AT + timedelta(hours=1)
    )["level"] == "caution"


def test_superseded_out_of_range_reading_leads_with_retest_status():
    reading = _reading(fc=1)
    additions = [
        {
            "chemical": "liquid_chlorine",
            "added_at": (TESTED_AT + timedelta(minutes=30)).isoformat(),
        }
    ]

    assert services.status_summary(
        _pool(), reading, additions, now=TESTED_AT + timedelta(hours=1)
    ) == {"level": "caution", "text": "Retest before dosing"}


def test_missing_fc_reading_requires_retest():
    reading = _reading(fc=None)

    actions = services.recommended_actions(
        _pool(), reading, now=TESTED_AT + timedelta(hours=1)
    )

    assert actions[0]["kind"] == "retest"
    assert "no FC value" in actions[0]["why"]
    assert services.status_summary(
        _pool(), reading, now=TESTED_AT + timedelta(hours=1)
    )["level"] == "caution"


def test_missing_cya_warning_is_preserved_in_recommendation():
    actions = services.recommended_actions(
        _pool(),
        _reading(fc=1, cya=None),
        now=TESTED_AT + timedelta(hours=1),
    )

    action = actions[0]
    assert action["kind"] == "chlorine"
    assert "No CYA reading yet" in action["why"]
    assert any("No CYA reading yet" in warning for warning in action["dose"]["warnings"])
    assert action["dose"]["warnings"][0] == PRODUCT_LABEL_WARNING


def test_fresh_in_range_reading_remains_good():
    reading = _reading(fc=6)
    now = TESTED_AT + timedelta(hours=1)

    assert services.recommended_actions(_pool(), reading, now=now) == []
    assert services.status_summary(_pool(), reading, now=now) == {
        "level": "good",
        "text": "All readings in range",
    }
