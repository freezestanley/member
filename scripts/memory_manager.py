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
    frequency_bonus = 1.0 + 0.2 * math.log1p(max(0, access_count - 1))
    return round(initial_w * decay_factor * frequency_bonus, 3)

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
                    if not os.path.exists(ARCHIVE_DIR): os.makedirs(ARCHIVE_DIR)
                    os.rename(path, os.path.join(ARCHIVE_DIR, file))
                else:
                    with open(path, "w", encoding="utf-8") as f: f.write(new_content)

def render_global_indices():
    """🚀 Python 纯逻辑：只重写 index.md 和 hot.md，彻底剥离时间戳以斩断 Git 冗余提交 [INDEX]"""
    print("🎨 [Engine] Python 正在毫秒级刷新中央目录树与热点图谱...")
    
    global_notes = []
    project_notes_map = {}
    all_notes_stats = []
    
    # 1. 扫描公共通用概念区
    if os.path.exists(GLOBAL_DIR):
        for root, _, files in os.walk(GLOBAL_DIR):
            for file in files:
                if file.endswith(".md"):
                    note_name = file.replace(".md", "")
                    global_notes.append(note_name)
                    # 提取统计数据
                    path = os.path.join(root, file)
                    with open(path, "r", encoding="utf-8") as f: content = f.read()
                    w_match = re.search(r"current_weight:\s*([\d\.]+)", content)
                    c_match = re.search(r"access_count:\s*(\d+)", content)
                    if w_match and c_match:
                        all_notes_stats.append((float(w_match.group(1)), int(c_match.group(1)), note_name))

    # 2. 扫描项目独占概念区 (支持按 Git 项目文件夹层级归类)
    if os.path.exists(PROJECT_DIR):
        for item in os.listdir(PROJECT_DIR):
            item_path = os.path.join(PROJECT_DIR, item)
            if os.path.isdir(item_path):
                project_notes_map[item] = []
                for root, _, files in os.walk(item_path):
                    for file in files:
                        if file.endswith(".md"):
                            note_name = file.replace(".md", "")
                            project_notes_map[item].append(note_name)
                            # 提取统计数据
                            path = os.path.join(root, file)
                            with open(path, "r", encoding="utf-8") as f: content = f.read()
                            w_match = re.search(r"current_weight:\s*([\d\.]+)", content)
                            c_match = re.search(r"access_count:\s*(\d+)", content)
                            if w_match and c_match:
                                all_notes_stats.append((float(w_match.group(1)), int(c_match.group(1)), note_name))

    # 📝 核心刷新一：全量机械重写 wiki/index.md (去除时间戳，解决 Commit Churn) [INDEX]
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

    # 📝 核心刷新二：计算权重并重写 wiki/hot.md ( Top 10 红球雷达图 ) [INDEX]
    all_notes_stats.sort(key=lambda x: x[0], reverse=True)
    hot_path = os.path.join(BRAIN_DIR, "wiki/hot.md")
    with open(hot_path, "w", encoding="utf-8") as f:
        f.write("# 🔥 LLM-Brain OS 高频热点活动图谱\n\n")
        f.write("## 🔴 当前中央黄金记忆区 (Top 10 High-Weight Notes)\n")
        f.write("以下节点因近期高频交互或刚完成语义重构，在 Obsidian 关系图谱中呈现硕大的鲜红色：\n\n")
        for w, c, name in all_notes_stats[:10]:
            f.write(f"- [[{name}]] ─── (🧠 当前权重: `{w}` | 📊 累计调用: `{c}` 次)\n")

if __name__ == "__main__":
    scan_and_clean()
    render_global_indices()
    print("🎉 [Engine] 机械索引刷新完毕，交还大模型控制权。")
