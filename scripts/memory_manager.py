# scripts/memory_manager.py
import argparse
import json
import os
import re
import math
from datetime import date, datetime

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
    load_config,
)

# 🚨 锁死中央知识库的绝对路径
BRAIN_DIR = "/Users/za-stanlexu/Documents/member/member"
GLOBAL_DIR = os.path.join(BRAIN_DIR, "wiki/global_concepts")
PROJECT_DIR = os.path.join(BRAIN_DIR, "wiki/project_exclusives")
ARCHIVE_DIR = os.path.join(BRAIN_DIR, "archive")  # 与wiki/同级

HALF_LIFE_DAYS = 30
FORGET_THRESHOLD = 0.15

# 自动生成文件，不补 frontmatter，不参与衰减
_GENERATED_FILES = {"hot.md", "global_hot.md", "index.md", "log.md"}


def calculate_weight(initial_w, last_active_str, access_count):
    try:
        last_active = datetime.strptime(last_active_str.strip(), "%Y-%m-%d")
    except ValueError:
        return initial_w
    days_passed = max(0, (datetime.now() - last_active).days)
    decay_factor = math.pow(2, -(days_passed / HALF_LIFE_DAYS))
    safe_count = max(1, access_count)
    frequency_bonus = 1.0 + 0.2 * math.log(safe_count)
    return round(initial_w * decay_factor * frequency_bonus, 3)


def _build_frontmatter(path: str) -> str:
    """根据路径推断 project，用文件 mtime 作日期，生成标准 frontmatter。"""
    mtime = datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d")
    rel = os.path.relpath(path, os.path.join(BRAIN_DIR, "wiki"))
    parts = rel.replace("\\", "/").split("/")
    if parts[0] == "global_concepts":
        project = "global"
    elif parts[0] == "project_exclusives" and len(parts) >= 2:
        project = parts[1]
    else:
        project = "global"
    return (
        f"---\n"
        f"type: concept\n"
        f"created_at: {mtime}\n"
        f"last_modified: {mtime}\n"
        f"project: {project}\n"
        f"aliases: []\n"
        f"code_symbols: []\n"
        f"initial_weight: 1.0\n"
        f"current_weight: 1.0\n"
        f"last_activated: {mtime}\n"
        f"access_count: 1\n"
        f"status: active\n"
        f"superseded_by: \"\"\n"
        f"weight_schema_version: 2\n"
        f"category: general\n"
        f"importance: 1\n"
        f"ewma_access: 0.0\n"
        f"last_boost: 1.0\n"
        f"last_boosted_at: \"\"\n"
        f"last_weight_migrated_at: {mtime}\n"
        f"---\n"
    )


def _ensure_status_fields(content: str) -> tuple[str, bool]:
    """确保 frontmatter 包含 status 和 superseded_by，缺什么补什么。返回(新内容, 是否修改)。"""
    fm_match = re.match(r"^(---\s*\n)(.*?)(\n---\s*\n)", content, re.DOTALL)
    if not fm_match:
        return content, False
    fm_text = fm_match.group(2)
    changed = False
    if not re.search(r'^status:', fm_text, re.MULTILINE):
        fm_text += "\nstatus: active"
        changed = True
    if not re.search(r'^superseded_by:', fm_text, re.MULTILINE):
        fm_text += "\nsuperseded_by: \"\""
        changed = True
    if not changed:
        return content, False
    new_content = fm_match.group(1) + fm_text + fm_match.group(3) + content[fm_match.end():]
    return new_content, True


def init_ewma_from_access_count(access_count: int, config: dict) -> float:
    historical_signal = max(0.0, float(access_count) - 1.0)
    return round(min(config["ewma_migration_cap"], historical_signal), 3)


def migrate_weight_fields(fm: dict[str, str], today: date, config: dict) -> tuple[dict[str, str], bool]:
    version = str(fm.get("weight_schema_version", "")).strip().strip("\"'")
    was_migrated = version != "2"
    access_count = clamp_int(fm.get("access_count", "1"), 0, 1_000_000_000)
    ewma = fm.get("ewma_access")
    if ewma is None or was_migrated:
        ewma = str(init_ewma_from_access_count(access_count, config))

    updates = {
        "weight_schema_version": "2",
        "category": fm.get("category", "general") or "general",
        "importance": str(clamp_int(fm.get("importance", "1"), 1, 5)),
        "ewma_access": str(clamp_float(ewma, 0.0, config["ewma_max"])),
        "last_boost": str(clamp_float(fm.get("last_boost", "1.0"), 1.0, config["boost_values"]["high"])),
        "last_boosted_at": fm.get("last_boosted_at", '""') or '""',
        "last_weight_migrated_at": fm.get("last_weight_migrated_at", today.isoformat()) or today.isoformat(),
    }
    if was_migrated:
        updates["last_weight_migrated_at"] = today.isoformat()
    return updates, was_migrated


def calculate_weight_v2(fm: dict[str, str], today: date, config: dict) -> float:
    meta = build_metadata(fm, today, config)
    return WeightEngine(config).compute(meta)


def archive_with_backlink_update(
    note_path: str,
    archive_dir: str,
    scan_root: str,
    content: str | None = None,
):
    """
    将 note_path 物理移入 archive/，保留相对 wiki/ 的完整子目录层级。
    移动前写 status: archived 到原文件 frontmatter。
    双链不改写（archive/ 在 Obsidian vault 内，[[stem]] 自动解析，零死链）。
    scan_root 即 wiki 根目录，relpath 基于此计算归档子路径。
    """
    wiki_root = scan_root
    rel_path = os.path.relpath(note_path, wiki_root)
    archive_path = os.path.join(archive_dir, rel_path)
    if os.path.exists(archive_path):
        raise FileExistsError(archive_path)

    os.makedirs(os.path.dirname(archive_path), exist_ok=True)
    if content is None:
        with open(note_path, "r", encoding="utf-8") as f:
            content = f.read()

    content, _ = _ensure_status_fields(content)
    content = upsert_frontmatter_fields(content, {"status": "archived"})
    atomic_write_text(note_path, content, note_path + ".lock")
    os.replace(note_path, archive_path)
    print(f"   ↳ [归档] {rel_path} → archive/{rel_path}")


def _empty_summary() -> dict:
    return {
        "scanned": 0,
        "migrated": 0,
        "updated": 0,
        "archived": 0,
        "archive_conflicts": 0,
        "archive_candidates_after_grace": 0,
        "skipped": 0,
        "incomplete": 0,
    }


def scan_and_clean(
    config_path: str | None = None,
    today: date | None = None,
    dry_run: bool = False,
) -> dict:
    config = load_config(config_path)
    today = today or date.today()
    summary = _empty_summary()
    target_dirs = [GLOBAL_DIR, PROJECT_DIR]
    for target_dir in target_dirs:
        if not os.path.exists(target_dir):
            continue
        for root, _, files in os.walk(target_dir):
            for file in files:
                if not file.endswith(".md"):
                    continue
                if file in _GENERATED_FILES:
                    continue

                path = os.path.join(root, file)
                summary["scanned"] += 1

                # 孤儿 .tmp 检测：同名 .tmp 存在说明写入未完成
                tmp_path = path + ".tmp"
                if os.path.exists(tmp_path):
                    summary["incomplete"] += 1
                    if dry_run:
                        continue
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            content = f.read()
                        content, _ = _ensure_status_fields(content)
                        content = upsert_frontmatter_fields(content, {"status": "incomplete"})
                        atomic_write_text(path, content, path + ".lock")
                        print(f"⚠️ [未完成事务] {file} 发现孤儿 .tmp，已标记 status: incomplete")
                    except Exception as e:
                        print(f"   ↳ [incomplete标记失败] {file}: {e}")
                    continue

                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()

                # 无 frontmatter：自动补全
                try:
                    _, fm_text, _ = split_frontmatter(content)
                except ValueError:
                    summary["updated"] += 1
                    new_content = _build_frontmatter(path) + content
                    if not dry_run:
                        atomic_write_text(path, new_content, path + ".lock")
                        print(f"✅ [frontmatter补全] {file}")
                    continue

                # 确保 status/superseded_by 字段存在
                content, patched = _ensure_status_fields(content)
                if patched:
                    summary["updated"] += 1
                    if not dry_run:
                        atomic_write_text(path, content, path + ".lock")
                try:
                    _, fm_text, _ = split_frontmatter(content)
                except ValueError:
                    summary["skipped"] += 1
                    continue

                fm = parse_frontmatter_text(fm_text)
                status = normalize_status(fm.get("status"))
                if status in {"archived", "deprecated", "incomplete"}:
                    summary["skipped"] += 1
                    continue

                migration_updates, was_migrated = migrate_weight_fields(fm, today, config)
                if was_migrated:
                    summary["migrated"] += 1
                migrated_fm = {**fm, **migration_updates}
                new_w = calculate_weight_v2(migrated_fm, today, config)
                updates = {**migration_updates, "current_weight": str(new_w)}
                new_content = upsert_frontmatter_fields(content, updates)
                changed = new_content != content

                if was_migrated:
                    if new_w < config["forget_threshold"]:
                        summary["archive_candidates_after_grace"] += 1
                    if changed:
                        summary["updated"] += 1
                        if not dry_run:
                            atomic_write_text(path, new_content, path + ".lock")
                    continue

                if new_w < config["forget_threshold"]:
                    summary["archived"] += 1
                    if not dry_run:
                        try:
                            print(f"⚠️ [冷冻归档] {file} (权重: {new_w}) -> 移入 archive/")
                            archive_with_backlink_update(
                                path,
                                ARCHIVE_DIR,
                                os.path.join(BRAIN_DIR, "wiki"),
                                content=new_content,
                            )
                        except FileExistsError:
                            summary["archived"] -= 1
                            summary["archive_conflicts"] += 1
                else:
                    if changed:
                        summary["updated"] += 1
                        if not dry_run:
                            atomic_write_text(path, new_content, path + ".lock")
    return summary


def render_global_indices():
    """重写 wiki/index.md，去除时间戳以避免 Git commit churn。"""
    print("🎨 [Engine] 刷新中央目录索引 wiki/index.md ...")

    global_notes = []
    project_notes_map = {}

    if os.path.exists(GLOBAL_DIR):
        for _, _, files in os.walk(GLOBAL_DIR):
            for file in files:
                if file.endswith(".md") and file not in _GENERATED_FILES:
                    global_notes.append(file.replace(".md", ""))

    if os.path.exists(PROJECT_DIR):
        for item in os.listdir(PROJECT_DIR):
            item_path = os.path.join(PROJECT_DIR, item)
            if os.path.isdir(item_path):
                project_notes_map[item] = []
                for _, _, files in os.walk(item_path):
                    for file in files:
                        if file.endswith(".md") and file not in _GENERATED_FILES:
                            project_notes_map[item].append(file.replace(".md", ""))

    index_path = os.path.join(BRAIN_DIR, "wiki/index.md")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write("# 🗺️ Central Index ── 中央知识网络全局全景主索引\n\n")
        f.write("## 🪐 一、 行业通用技术概念与开发总规范\n")
        if global_notes:
            for note in sorted(global_notes):
                f.write(f"- [[{note}]]\n")
        else:
            f.write("- *(暂无通用公共规范)*\n")

        f.write("\n## 🚜 二、 项目特异性独占研发逻辑与业务概念\n")
        if project_notes_map:
            for proj, notes in sorted(project_notes_map.items()):
                if notes:
                    f.write(f"\n### 📂 项目仓库：`{proj}`\n")
                    for note in sorted(notes):
                        f.write(f"- [[{note}]]\n")
        else:
            f.write("- *(暂无隔离项目资产)*\n")


def parse_today(value: str | None) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("--today must be YYYY-MM-DD") from exc


def _cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--config")
    parser.add_argument("--today")
    args = parser.parse_args(argv)

    try:
        summary = scan_and_clean(
            config_path=args.config,
            today=parse_today(args.today),
            dry_run=args.dry_run,
        )
    except ValueError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2

    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    if not args.dry_run:
        render_global_indices()
        print("🎉 [Engine] 机械索引刷新完毕，交还大模型控制权。")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
