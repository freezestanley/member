# scripts/memory_manager.py
import os
import re
import math
from datetime import datetime

# 🚨 锁死中央知识库的绝对路径
BRAIN_DIR="/Users/za-stanlexu/Documents/member/member"
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

if __name__ == "__main__":
    scan_and_clean()
