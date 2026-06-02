import os, re, math, shutil
from datetime import datetime

VAULT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCAN_DIRS = [
    os.path.join(VAULT_ROOT, "wiki", "concepts"),
    os.path.join(VAULT_ROOT, "wiki", "projects"),
]
ARCHIVE_DIR = os.path.join(VAULT_ROOT, "wiki", "archive")
HALF_LIFE_DAYS = 30
FORGET_THRESHOLD = 0.15

def calculate_weight(initial_w, last_active_str, access_count):
    last_active = datetime.strptime(last_active_str.strip(), "%Y-%m-%d")
    days_passed = max(0, (datetime.now() - last_active).days)
    decay_factor = math.pow(2, -(days_passed / HALF_LIFE_DAYS))
    frequency_bonus = 1.0 + 0.2 * math.log1p(access_count - 1)
    return round(initial_w * decay_factor * frequency_bonus, 3)

os.makedirs(ARCHIVE_DIR, exist_ok=True)

for scan_dir in SCAN_DIRS:
    if not os.path.exists(scan_dir):
        continue
    for root, _, files in os.walk(scan_dir):
        for file in files:
            if not file.endswith(".md"):
                continue
            path = os.path.join(root, file)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            fm_match = re.match(r"^---(.*?)---", content, re.DOTALL)
            if not fm_match:
                continue
            fm_text = fm_match.group(1)
            try:
                init_w = float(re.search(r"initial_weight:\s*([\d\.]+)", fm_text).group(1))
                last_act = re.search(r"last_activated:\s*([\d\-]+)", fm_text).group(1)
                count = int(re.search(r"access_count:\s*(\d+)", fm_text).group(1))
            except AttributeError:
                continue

            new_w = calculate_weight(init_w, last_act, count)
            updated = re.sub(r"current_weight:\s*[\d\.]+", f"current_weight: {new_w}", content)
            with open(path, "w", encoding="utf-8") as f:
                f.write(updated)

            if new_w < FORGET_THRESHOLD:
                dest = os.path.join(ARCHIVE_DIR, file)
                shutil.move(path, dest)
                print(f"[归档] {path} -> {dest} (weight: {new_w})")
            else:
                print(f"[保留] {file} (weight: {new_w})")
