#!/usr/bin/env bash
# hot_watcher.sh — 监听 wiki/ 目录中 .md 文件变化，自动触发 hot_refresh.py
# 排除 hot.md 自身（避免刷新循环）
#
# 用法：
#   bash hot_watcher.sh          # 前台运行
#   bash hot_watcher.sh &        # 后台运行

WIKI_DIR="$(cd "$(dirname "$0")/../wiki" && pwd)"
SCRIPT="$(cd "$(dirname "$0")" && pwd)/hot_refresh.py"
HOT_MD="$WIKI_DIR/hot.md"
COOLDOWN=2   # 秒：同一批变化合并触发，防止短时间内多次刷新
LOCKFILE="/Users/za-stanlexu/Documents/member/member/_inbox/.hot_refresh.lock"
CACHE_SCRIPT="$(cd "$(dirname "$0")" && pwd)/bm25_search.py"

echo "[hot_watcher] 启动监听：$WIKI_DIR"
echo "[hot_watcher] 排除：$HOT_MD"

last_trigger=0

fswatch -r -e ".*" -i "\.md$" "$WIKI_DIR" | while read -r changed_file; do
    # 排除 hot.md 自身，避免刷新死循环
    if [ "$changed_file" = "$HOT_MD" ]; then
        continue
    fi

    now=$(date +%s)
    diff=$(( now - last_trigger ))

    if [ "$diff" -ge "$COOLDOWN" ]; then
        last_trigger=$now
        echo "[hot_watcher] 检测到变化：$changed_file → 刷新 hot.md + BM25 cache"
        flock -n "$LOCKFILE" bash -c "
            python3 '$SCRIPT'
            python3 '$CACHE_SCRIPT' --rebuild-cache
        " &
    fi
done
