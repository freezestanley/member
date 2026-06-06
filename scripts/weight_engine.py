from __future__ import annotations

import ast
import copy
import math
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - exercised only without dependency installed
    yaml = None


DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config" / "weight_config.yml"

DEFAULT_CONFIG = {
    "category_half_life": {
        "strategy": 90,
        "fact": 60,
        "decision": 75,
        "log": 7,
        "spec": 120,
        "general": 30,
    },
    "importance_k": 0.6,
    "freq_k": 0.15,
    "freq_bonus_max": 1.6,
    "ewma_half_life_days": 14,
    "ewma_max": 20.0,
    "ewma_migration_cap": 5.0,
    "boost_ttl_days": 7,
    "boost_keywords": {
        "high": ["重要", "紧急", "开会", "决策", "上线"],
        "medium": ["参考", "复习", "回顾"],
    },
    "boost_values": {
        "high": 1.4,
        "medium": 1.2,
        "default": 1.0,
    },
    "weight_min": 0.01,
    "weight_max": 5.0,
    "forget_threshold": 0.15,
    "revive_weight_margin": 0.05,
}


@dataclass(frozen=True)
class NoteMetadata:
    initial_weight: float = 1.0
    category: str = "general"
    importance: int = 1
    days_idle: int = 0
    ewma_access: float = 0.0
    last_boost: float = 1.0
    boost_age_days: int | None = None


def _parse_scalar(value: str):
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        try:
            return ast.literal_eval(value)
        except (SyntaxError, ValueError):
            return []
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value.strip("\"'")


def _simple_yaml_load(text: str) -> dict:
    data: dict = {}
    current_key: str | None = None
    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        key, _, value = raw_line.strip().partition(":")
        if indent == 0:
            if value.strip() == "":
                data[key] = {}
                current_key = key
            else:
                data[key] = _parse_scalar(value)
                current_key = None
        elif current_key and isinstance(data.get(current_key), dict):
            data[current_key][key] = _parse_scalar(value)
    return data


def _deep_merge(base: dict, override: dict) -> dict:
    merged = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(config_path: str | None = None) -> dict:
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    if not path.exists():
        return copy.deepcopy(DEFAULT_CONFIG)
    text = path.read_text(encoding="utf-8")
    try:
        raw = yaml.safe_load(text) if yaml is not None else _simple_yaml_load(text)
    except Exception as exc:
        raise ValueError(f"invalid config: {path}") from exc
    config = _deep_merge(DEFAULT_CONFIG, raw or {})
    _validate_config(config)
    return config


def _validate_config(config: dict) -> None:
    if config["category_half_life"].get("general", 0) <= 0:
        raise ValueError("category_half_life.general must be positive")
    for key in ("importance_k", "freq_k", "freq_bonus_max", "ewma_half_life_days", "ewma_max"):
        if float(config[key]) <= 0:
            raise ValueError(f"{key} must be positive")
    if config["weight_min"] <= 0 or config["weight_max"] < config["weight_min"]:
        raise ValueError("invalid weight bounds")


def clamp_float(value, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = minimum
    return min(maximum, max(minimum, parsed))


def clamp_int(value, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = minimum
    return min(maximum, max(minimum, parsed))


def days_since(date_str: str, today: date) -> int:
    try:
        parsed = datetime.strptime(str(date_str).strip(), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return 0
    return max(0, (today - parsed).days)


def build_metadata(fm: dict[str, str], today: date, config: dict) -> NoteMetadata:
    category = str(fm.get("category", "general")).strip() or "general"
    if category not in config["category_half_life"]:
        category = "general"

    boost_date = fm.get("last_boosted_at", "").strip().strip("\"'")
    boost_age_days = days_since(boost_date, today) if boost_date else None

    return NoteMetadata(
        initial_weight=clamp_float(fm.get("initial_weight", "1.0"), 1.0, config["weight_max"]),
        category=category,
        importance=clamp_int(fm.get("importance", "1"), 1, 5),
        days_idle=days_since(fm.get("last_activated", ""), today),
        ewma_access=clamp_float(fm.get("ewma_access", "0.0"), 0.0, config["ewma_max"]),
        last_boost=clamp_float(
            fm.get("last_boost", "1.0"),
            1.0,
            config["boost_values"]["high"],
        ),
        boost_age_days=boost_age_days,
    )


class WeightEngine:
    def __init__(self, config: dict):
        self.config = config

    def compute(self, meta: NoteMetadata) -> float:
        category_half_life = self.config["category_half_life"].get(
            meta.category,
            self.config["category_half_life"]["general"],
        )
        effective_hl = category_half_life * (
            1 + (meta.importance - 1) * self.config["importance_k"]
        )
        decay = 2 ** (-meta.days_idle / effective_hl)
        freq_bonus = min(
            1.0 + self.config["freq_k"] * math.log1p(max(0.0, meta.ewma_access)),
            self.config["freq_bonus_max"],
        )

        if meta.boost_age_days is None or meta.boost_age_days > self.config["boost_ttl_days"]:
            boost = 1.0
        else:
            boost = min(max(meta.last_boost, 1.0), self.config["boost_values"]["high"])

        raw = meta.initial_weight * decay * freq_bonus * boost
        return round(min(max(raw, self.config["weight_min"]), self.config["weight_max"]), 3)
