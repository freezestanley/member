# scripts/memory_manager.py
import os
import re
import math
from datetime import datetime

# 🚨 锁死中央知识库的绝对路径
BRAIN_DIR = "/Users/za-stanlexu/Documents/member/member"
GLOBAL_DIR = os.path.join(BRAIN_DIR, "wiki/global_concepts")
PROJECT_DIR = os.path.join(BRAIN_DIR, "wiki/project_exclusives")
ARCHIVE_DIR = os.path.join(BRAIN_DIR, "wiki/archive")

HALF_LIFE_DAYS = 30           # 记忆半衰期（30天不访问，权重打对折）
FORGET_THRESHOLD = 0.15       # 淘汰死线

def calculate_weight(initial_w, last_active_str, access_count):
    try:
        last_active = datetime.strptime(last_active_str.strip(), "%Y-%m-%d")
    except ValueError:
        return initial_w
    days_passed = max(0, (datetime.now() - last_active).days)
    decay_factor = math.pow(2, -(days_passed / HALF_LIFE_DAYS))
    # 频率反向强化
    safe_count = max(1, access_count)          # 防御 access_count=0 的极端情况
    frequency_bonus = 1.0 + 0.2 * math.log(safe_count)
    return round(initial_w * decay_factor * frequency_bonus, 3)

def archive_with_backlink_update(note_path: str, archive_dir: str, scan_root: str):
    """
    将 note_path 物理移入 archive_dir，并在 scan_root 全库中
    将所有 [[<note_stem>]] 替换为 ~~[[<note_stem>]]~~（已归档标注）。
    顺序：先全库替换双链，再移动文件（顺序不能反：移动后路径就找不到了）。
    """
    note_stem = os.path.splitext(os.path.basename(note_path))[0]
    old_link = f"[[{note_stem}]]"
    new_link = f"~~[[{note_stem}]]~~"

    for root, _, files in os.walk(scan_root):
        for fname in files:
            if not fname.endswith(".md"):
                continue
            fp = os.path.join(root, fname)
            if fp == note_path:
                continue  # 跳过被归档文件自身
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    content = f.read()
                if old_link in content:
                    updated = content.replace(old_link, new_link)
                    with open(fp, "w", encoding="utf-8") as f:
                        f.write(updated)
                    print(f"   ↳ [断链修复] {fname}: {old_link} → {new_link}")
            except Exception as e:
                print(f"   ↳ [断链修复失败] {fname}: {e}")

    if not os.path.exists(archive_dir):
        os.makedirs(archive_dir)
    os.rename(note_path, os.path.join(archive_dir, os.path.basename(note_path)))


def scan_and_clean():
    target_dirs = [GLOBAL_DIR, PROJECT_DIR]
    for target_dir in target_dirs:
        if not os.path.exists(target_dir): continue
        for root, _, files in os.walk(target_dir):
            for file in files:
                if not file.endswith(".md"): continue
                path = os.path.join(root, file)
                
                with open(path, "r", encoding="utf-8") as f: content = f.read()
                fm_match = re.match(r"^---(.*?)---", content, re.DOTALL)
                if not fm_match: continue
                fm_text = fm_match.group(1)
                
                try:
                    init_w = float(re.search(r"initial_weight:\s*([\d\.]+)", fm_text).group(1))
                    last_act = re.search(r"last_activated:\s*([\d\-]+)", fm_text).group(1)
                    count = int(re.search(r"access_count:\s*(\d+)", fm_text).group(1))
                except (AttributeError, ValueError):
                    continue # 格式不合规或未初始化，跳过
                
                new_w = calculate_weight(init_w, last_act, count)
                updated_fm = re.sub(r"current_weight:\s*[\d\.]+", f"current_weight: {new_w}", fm_text)
                new_content = content.replace(fm_text, updated_fm)
                
                if new_w < FORGET_THRESHOLD:
                    print(f"⚠️ [冷冻归档] 检测到过时边缘知识: {file} (当前权重: {new_w}) -> 物理移入冷冻区。")
                    archive_with_backlink_update(path, ARCHIVE_DIR, os.path.join(BRAIN_DIR, "wiki"))
                else:
                    with open(path, "w", encoding="utf-8") as f: f.write(new_content)

def render_global_indices():
    """重写 wiki/index.md，去除时间戳以避免 Git commit churn。
    hot.md 由 hot_refresh.py 独立维护（大纲树格式），此函数不再写入。
    """
    print("🎨 [Engine] 刷新中央目录索引 wiki/index.md ...")

    global_notes = []
    project_notes_map = {}

    # 1. 扫描公共通用概念区
    if os.path.exists(GLOBAL_DIR):
        for _, _, files in os.walk(GLOBAL_DIR):
            for file in files:
                if file.endswith(".md"):
                    global_notes.append(file.replace(".md", ""))

    # 2. 扫描项目独占概念区
    if os.path.exists(PROJECT_DIR):
        for item in os.listdir(PROJECT_DIR):
            item_path = os.path.join(PROJECT_DIR, item)
            if os.path.isdir(item_path):
                project_notes_map[item] = []
                for _, _, files in os.walk(item_path):
                    for file in files:
                        if file.endswith(".md"):
                            project_notes_map[item].append(file.replace(".md", ""))

    # 全量重写 wiki/index.md（无时间戳，内容不变则 git diff 为空）
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
