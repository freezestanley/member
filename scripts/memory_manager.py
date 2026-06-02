import os, re, math
from datetime import datetime

WIKI_DIR = "./wiki/concepts"
ARCHIVE_DIR = "./wiki/archive"
HALF_LIFE_DAYS = 30           # 30天不访问，记忆权重减半
FORGET_THRESHOLD = 0.15       # 遗忘阈值

def calculate_weight(initial_w, last_active_str, access_count):
    last_active = datetime.strptime(last_active_str.strip(), "%Y-%m-%d")
    days_passed = max(0, (datetime.now() - last_active).days)
    decay_factor = math.pow(2, -(days_passed / HALF_LIFE_DAYS))
    frequency_bonus = 1.0 + 0.2 * math.log1p(access_count - 1)
    return round(initial_w * decay_factor * frequency_bonus, 3)

for root, _, files in os.walk(WIKI_DIR):
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
        except AttributeError: continue
        
        new_w = calculate_weight(init_w, last_act, count)
        updated_fm = re.sub(r"current_weight:\s*[\d\.]+", f"current_weight: {new_w}", fm_text)
        new_content = content.replace(fm_text, updated_fm)
        
        if new_w < FORGET_THRESHOLD:
            print(f"⚠️ [冷冻归档] {file} 权重降至 {new_w}，已移出活跃区。")
            if not os.path.exists(ARCHIVE_DIR): os.makedirs(ARCHIVE_DIR)
            os.rename(path, os.path.join(ARCHIVE_DIR, file))
        else:
            with open(path, "w", encoding="utf-8") as f: f.write(new_content)

