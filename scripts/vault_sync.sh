#!/bin/bash
# scripts/vault_sync.sh

# 🚨 锁死中央知识库的绝对路径
BRAIN_DIR="/Users/za-stanlexu/Documents/member/member"
cd "$BRAIN_DIR" || exit 1

echo "🔄 [Git Engine] 正在对中央知识图谱执行增量原子化云端同步..."

# 强制本地换行符规范与合并单元对齐
git config merge.renormalize true

# 确定规范发布分支（必须显式配置，不从 HEAD 推断）
# 优先读 BRAIN_SYNC_BRANCH 环境变量；未设置时默认 main
SYNC_BRANCH="${BRAIN_SYNC_BRANCH:-main}"

CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
if [ -z "$CURRENT_BRANCH" ] || [ "$CURRENT_BRANCH" = "HEAD" ]; then
    echo "⚠️ [同步中止] 无法确定当前分支（可能处于 detached HEAD）。"
    exit 1
fi

# fail-close：当前分支必须与规范发布分支一致，否则拒绝推送
if [ "$CURRENT_BRANCH" != "$SYNC_BRANCH" ]; then
    echo "⛔ [同步拒绝] 当前分支 '$CURRENT_BRANCH' 不是规范发布分支 '$SYNC_BRANCH'。"
    echo "   知识笔记必须合并到 '$SYNC_BRANCH' 后才能发布，或显式设置 BRAIN_SYNC_BRANCH 环境变量覆盖。"
    echo "   示例：BRAIN_SYNC_BRANCH=feat0602 bash vault_sync.sh"
    exit 1
fi
echo "🌿 [同步分支] $SYNC_BRANCH（当前分支匹配，允许发布）"

WRITE_LOCK="${BRAIN_DIR}/_inbox/.hot_refresh.lock"
MAX_WAIT=10
waited=0

# 等待 hot_refresh.py 写入锁释放（最多 10 秒）
# 用 Python fcntl 探测实际锁持有状态（macOS 兼容，不依赖 GNU flock 命令）
# 注意：heredoc 不使用单引号，使 $WRITE_LOCK 能被 Shell 展开后作为 argv[1] 传入
lock_is_held() {
    python3 - "$WRITE_LOCK" <<PYEOF
import fcntl, sys, os
lock_path = sys.argv[1]
if not os.path.exists(lock_path):
    sys.exit(1)   # 文件不存在 → 无锁 → exit 1（不阻塞）
try:
    # 用 "r+" 打开已有文件，避免 "w" 模式隐式创建或截断
    with open(lock_path, "r+") as f:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(f, fcntl.LOCK_UN)
    sys.exit(1)   # 获锁成功 → 没有进程持有锁 → exit 1（不阻塞）
except (BlockingIOError, OSError):
    sys.exit(0)   # 获锁失败 → 有进程持有锁 → exit 0（阻塞中）
PYEOF
}

while lock_is_held && [ "$waited" -lt "$MAX_WAIT" ]; do
    echo "⏳ [同步等待] hot_refresh.py 正在写入，等待 ${waited}s / ${MAX_WAIT}s..."
    sleep 1
    waited=$(( waited + 1 ))
done

if lock_is_held; then
    echo "⚠️ [同步中止] 写入锁持续超过 ${MAX_WAIT} 秒，本次同步跳过，请手动检查。"
    exit 1
fi

git fetch origin
# 使用 rebase 策略保持全局中央分支提交史是一条干净的直线
git rebase "origin/$SYNC_BRANCH" > /dev/null 2>&1 || git rebase --skip

if [[ -n $(git status -s) ]]; then
    git add .
    git commit -m "🧠 LLM Auto-Sync: $(date '+%Y-%m-%d %H:%M:%S') (Global Central Engine)"
    git push origin "$SYNC_BRANCH" --force-with-lease
    echo "🎉 [同步成功] 中央大脑与云端私有仓库已完美对齐。"
else
    echo "✨ [同步跳过] 本地未发现新增知识树变动。"
fi
