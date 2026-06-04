#!/usr/bin/env bash
# hot_watcher.sh — 双轨路由版
# 监听 wiki/ 目录 .md 变化，按路径定向触发 --global 或 --project
#
# 用法：
#   bash hot_watcher.sh          # 前台
#   bash hot_watcher.sh &        # 后台

WIKI_DIR="$(cd "$(dirname "$0")/../wiki" && pwd)"
SCRIPT="$(cd "$(dirname "$0")" && pwd)/hot_refresh.py"
CACHE_SCRIPT="$(cd "$(dirname "$0")" && pwd)/bm25_search.py"
COOLDOWN=2
INBOX_DIR="$(cd "$(dirname "$0")/../_inbox" && pwd)"

# 排除 hot.md 自身（global_hot.md 和各项目 hot.md）
EXCLUDE_PATTERN="hot\.md$"

echo "[hot_watcher] 启动双轨路由监听：$WIKI_DIR"

last_trigger=0

fswatch -r -e ".*" -i "\.md$" "$WIKI_DIR" | while read -r changed_file; do
    # 排除 hot 文件自身，避免刷新死循环
    if [[ "$changed_file" =~ $EXCLUDE_PATTERN ]]; then
        continue
    fi

    now=$(date +%s)
    diff=$(( now - last_trigger ))
    if [ "$diff" -lt "$COOLDOWN" ]; then
        continue
    fi
    last_trigger=$now

    echo "[hot_watcher] 变更：$changed_file"

    # 路由剪裁
    if [[ "$changed_file" =~ wiki/global_concepts/ ]]; then
        echo "[hot_watcher] → 全局热记忆刷新"
        python3 "$SCRIPT" --global &

    elif [[ "$changed_file" =~ wiki/project_exclusives/([^/]+)/ ]]; then
        PROJECT_NAME="${BASH_REMATCH[1]}"
        echo "[hot_watcher] → 项目 [$PROJECT_NAME] 热记忆刷新"
        python3 "$SCRIPT" --project "$PROJECT_NAME" &
    else
        echo "[hot_watcher] 路径不匹配已知路由，跳过：$changed_file"
        continue
    fi

    # BM25 缓存重建（全局，异步）
    python3 "$CACHE_SCRIPT" --rebuild-cache &

done
