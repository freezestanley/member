# scripts/memory_manager.py
import os
import re
import math
from datetime import datetime

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


def archive_with_backlink_update(note_path: str, archive_dir: str, scan_root: str):
    """
    将 note_path 物理移入 archive/，保留相对 wiki/ 的完整子目录层级。
    移动前写 status: archived 到原文件 frontmatter。
    双链不改写（archive/ 在 Obsidian vault 内，[[stem]] 自动解析，零死链）。
    scan_root 即 wiki 根目录，relpath 基于此计算归档子路径。
    """
    wiki_root = scan_root
    rel_path = os.path.relpath(note_path, wiki_root)
    archive_path = os.path.join(archive_dir, rel_path)
    os.makedirs(os.path.dirname(archive_path), exist_ok=True)

    try:
        with open(note_path, "r", encoding="utf-8") as f:
            content = f.read()
        content = re.sub(r'^status:\s*\S+', 'status: archived', content, flags=re.MULTILINE)
        if not re.search(r'^status:', content, re.MULTILINE):
            content, _ = _ensure_status_fields(content)
            content = re.sub(r'^status:\s*\S+', 'status: archived', content, flags=re.MULTILINE)
        with open(note_path, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        print(f"   ↳ [归档status写入失败] {note_path}: {e}")

    os.rename(note_path, archive_path)
    print(f"   ↳ [归档] {rel_path} → archive/{rel_path}")


def scan_and_clean():
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

                # 孤儿 .tmp 检测：同名 .tmp 存在说明写入未完成
                tmp_path = path + ".tmp"
                if os.path.exists(tmp_path):
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            content = f.read()
                        content = re.sub(r'^status:\s*\S+', 'status: incomplete', content, flags=re.MULTILINE)
                        with open(path, "w", encoding="utf-8") as f:
                            f.write(content)
                        print(f"⚠️ [未完成事务] {file} 发现孤儿 .tmp，已标记 status: incomplete")
                    except Exception as e:
                        print(f"   ↳ [incomplete标记失败] {file}: {e}")
                    continue

                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()

                fm_match = re.match(r"^---(.*?)---", content, re.DOTALL)

                # 无 frontmatter：自动补全
                if not fm_match:
                    new_content = _build_frontmatter(path) + content
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(new_content)
                    print(f"✅ [frontmatter补全] {file}")
                    fm_match = re.match(r"^---(.*?)---", new_content, re.DOTALL)
                    content = new_content

                fm_text = fm_match.group(1)

                # 确保 status/superseded_by 字段存在
                content, patched = _ensure_status_fields(content)
                if patched:
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(content)
                    fm_match = re.match(r"^---(.*?)---", content, re.DOTALL)
                    fm_text = fm_match.group(1)

                try:
                    init_w = float(re.search(r"initial_weight:\s*([\d\.]+)", fm_text).group(1))
                    last_act = re.search(r"last_activated:\s*([\d\-]+)", fm_text).group(1)
                    count = int(re.search(r"access_count:\s*(\d+)", fm_text).group(1))
                except (AttributeError, ValueError):
                    continue

                new_w = calculate_weight(init_w, last_act, count)
                updated_fm = re.sub(r"current_weight:\s*[\d\.]+", f"current_weight: {new_w}", fm_text)
                new_content = content.replace(fm_text, updated_fm)

                if new_w < FORGET_THRESHOLD:
                    print(f"⚠️ [冷冻归档] {file} (权重: {new_w}) -> 移入 archive/")
                    archive_with_backlink_update(path, ARCHIVE_DIR, os.path.join(BRAIN_DIR, "wiki"))
                else:
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(new_content)


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


if __name__ == "__main__":
    scan_and_clean()
    render_global_indices()
    print("🎉 [Engine] 机械索引刷新完毕，交还大模型控制权。")
