from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from frontmatter_utils import (
    atomic_write_text,
    normalize_status,
    parse_frontmatter_text,
    split_frontmatter,
    upsert_frontmatter_fields,
)
from weight_engine import (
    WeightEngine,
    build_metadata,
    clamp_float,
    clamp_int,
    days_since,
    load_config,
)


BRAIN_DIR = Path("/Users/za-stanlexu/Documents/member/member")
WIKI_ROOT = BRAIN_DIR / "wiki"
GLOBAL_DIR = WIKI_ROOT / "global_concepts"
PROJECT_DIR = WIKI_ROOT / "project_exclusives"
GENERATED_FILES = {"hot.md", "global_hot.md", "index.md", "log.md"}


class ActivationError(Exception):
    def __init__(self, message: str, exit_code: int):
        super().__init__(message)
        self.exit_code = exit_code


def infer_boost(context: str, config: dict, manual_boost: float | None = None) -> float:
    if manual_boost is not None:
        return clamp_float(manual_boost, 1.0, config["boost_values"]["high"])
    for level in ("high", "medium"):
        for keyword in config["boost_keywords"].get(level, []):
            if keyword in context:
                return float(config["boost_values"][level])
    return float(config["boost_values"]["default"])


def update_ewma(prev_ewma: float, days_since_activation: int, config: dict) -> float:
    decayed = prev_ewma * 2 ** (-days_since_activation / config["ewma_half_life_days"])
    return round(min(config["ewma_max"], decayed + 1.0), 3)


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _validate_active_path(note_path: str) -> Path:
    raw = Path(note_path)
    if raw.name in GENERATED_FILES or raw.suffix != ".md":
        raise ActivationError("file is not activatable", 3)
    if not raw.exists():
        raise ActivationError("file does not exist", 3)
    resolved = raw.resolve()
    allowed_roots = [GLOBAL_DIR.resolve(), PROJECT_DIR.resolve()]
    if not any(_is_relative_to(resolved, root) for root in allowed_roots):
        raise ActivationError("file is outside active wiki", 3)
    return resolved


def _schema_updates(fm: dict[str, str], today: date, config: dict) -> dict[str, str]:
    access_count = clamp_int(fm.get("access_count", "1"), 0, 1_000_000_000)
    historical_signal = max(0.0, float(access_count) - 1.0)
    ewma = fm.get("ewma_access")
    if ewma is None:
        ewma = str(round(min(config["ewma_migration_cap"], historical_signal), 3))
    return {
        "weight_schema_version": "2",
        "category": fm.get("category", "general") or "general",
        "importance": str(clamp_int(fm.get("importance", "1"), 1, 5)),
        "ewma_access": str(clamp_float(ewma, 0.0, config["ewma_max"])),
        "last_boost": str(clamp_float(fm.get("last_boost", "1.0"), 1.0, config["boost_values"]["high"])),
        "last_boosted_at": fm.get("last_boosted_at", '""') or '""',
        "last_weight_migrated_at": fm.get("last_weight_migrated_at", today.isoformat()) or today.isoformat(),
        "status": "active",
    }


def activate_note(
    note_path: str,
    config: dict,
    query_context: str = "",
    manual_boost: float | None = None,
    today: date | None = None,
) -> dict:
    today = today or date.today()
    path = _validate_active_path(note_path)
    content = path.read_text(encoding="utf-8")
    try:
        _, fm_text, _ = split_frontmatter(content)
    except ValueError as exc:
        raise ActivationError("frontmatter missing", 4) from exc

    fm = parse_frontmatter_text(fm_text)
    status = normalize_status(fm.get("status"))
    if status in {"archived", "deprecated", "incomplete"}:
        raise ActivationError(f"cannot activate status: {status}", 3)

    updates = _schema_updates(fm, today, config)
    fm_for_update = {**fm, **updates}
    previous_ewma = clamp_float(fm_for_update.get("ewma_access", "0.0"), 0.0, config["ewma_max"])
    days_idle = days_since(fm.get("last_activated", ""), today)
    access_count = clamp_int(fm.get("access_count", "1"), 0, 1_000_000_000) + 1
    boost = infer_boost(query_context, config, manual_boost)

    updates.update(
        {
            "last_activated": today.isoformat(),
            "last_modified": today.isoformat(),
            "access_count": str(access_count),
            "ewma_access": str(update_ewma(previous_ewma, days_idle, config)),
            "last_boost": str(boost),
            "last_boosted_at": today.isoformat() if boost > 1.0 else '""',
        }
    )
    computed_fm = {**fm, **updates}
    weight = WeightEngine(config).compute(build_metadata(computed_fm, today, config))
    updates["current_weight"] = str(weight)

    new_content = upsert_frontmatter_fields(content, updates)
    atomic_write_text(str(path), new_content, str(path.with_name(path.name + ".lock")))
    return {
        "ok": True,
        "path": str(path),
        "access_count": access_count,
        "ewma_access": float(updates["ewma_access"]),
        "last_boost": boost,
        "current_weight": weight,
    }


def _parse_today(value: str | None) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ActivationError("invalid --today", 2) from exc


def _cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", required=True)
    parser.add_argument("--context", default="")
    parser.add_argument("--boost", type=float)
    parser.add_argument("--config")
    parser.add_argument("--today")
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        result = activate_note(
            args.path,
            config,
            query_context=args.context,
            manual_boost=args.boost,
            today=_parse_today(args.today),
        )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except ValueError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2
    except ActivationError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(_cli())
