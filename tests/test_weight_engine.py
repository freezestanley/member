from datetime import date
import math
import sys

sys.path.insert(0, "scripts")

from weight_engine import (  # noqa: E402
    DEFAULT_CONFIG,
    WeightEngine,
    build_metadata,
)


def test_importance_one_does_not_extend_half_life():
    config = DEFAULT_CONFIG.copy()
    config["category_half_life"] = {"general": 30}
    meta = build_metadata(
        {
            "initial_weight": "1.0",
            "category": "general",
            "importance": "1",
            "last_activated": "2026-05-07",
            "ewma_access": "0.0",
        },
        date(2026, 6, 6),
        config,
    )

    weight = WeightEngine(config).compute(meta)

    assert weight == 0.5


def test_importance_five_extends_half_life_to_3_4x():
    config = DEFAULT_CONFIG.copy()
    config["category_half_life"] = {"general": 30}
    meta = build_metadata(
        {
            "initial_weight": "1.0",
            "category": "general",
            "importance": "5",
            "last_activated": "2026-02-24",
            "ewma_access": "0.0",
        },
        date(2026, 6, 6),
        config,
    )

    weight = WeightEngine(config).compute(meta)

    assert weight == 0.5


def test_frequency_bonus_is_one_for_zero_ewma_and_capped_for_large_ewma():
    config = DEFAULT_CONFIG.copy()
    engine = WeightEngine(config)
    zero = engine.compute(
        build_metadata(
            {"initial_weight": "1.0", "last_activated": "2026-06-06", "ewma_access": "0.0"},
            date(2026, 6, 6),
            config,
        )
    )
    huge = engine.compute(
        build_metadata(
            {"initial_weight": "1.0", "last_activated": "2026-06-06", "ewma_access": "1000000"},
            date(2026, 6, 6),
            config,
        )
    )

    assert zero == 1.0
    assert huge <= config["freq_bonus_max"]


def test_boost_expires_after_ttl_and_unknown_category_uses_general():
    config = DEFAULT_CONFIG.copy()
    meta = build_metadata(
        {
            "initial_weight": "1.0",
            "category": "missing",
            "importance": "1",
            "last_activated": "2026-06-06",
            "ewma_access": "0.0",
            "last_boost": "1.4",
            "last_boosted_at": "2026-05-01",
        },
        date(2026, 6, 6),
        config,
    )

    assert meta.category == "general"
    assert WeightEngine(config).compute(meta) == 1.0


def test_invalid_numeric_fields_fall_back_to_defaults():
    config = DEFAULT_CONFIG.copy()
    meta = build_metadata(
        {
            "initial_weight": "bad",
            "importance": "bad",
            "last_activated": "bad",
            "ewma_access": "bad",
        },
        date(2026, 6, 6),
        config,
    )

    assert math.isclose(meta.initial_weight, 1.0)
    assert meta.importance == 1
    assert meta.days_idle == 0
    assert math.isclose(meta.ewma_access, 0.0)
