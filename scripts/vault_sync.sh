#!/bin/bash
# scripts/vault_sync.sh

# 🚨 锁死中央知识库的绝对路径
BRAIN_DIR="/Users/za-stanlexu/Documents/member/member"
cd "$BRAIN_DIR" || exit 1

echo "🔄 [Git Engine] 正在对中央知识图谱执行增量原子化云端同步..."

# 强制本地换行符规范与合并单元对齐
git config merge.renormalize true

git fetch origin
# 使用 rebase 策略保持全局中央分支提交史是一条干净的直线
git rebase origin/main > /dev/null 2>&1 || git rebase --skip

if [[ -n $(git status -s) ]]; then
    git add .
    git commit -m "🧠 LLM Auto-Sync: $(date '+%Y-%m-%d %H:%M:%S') (Global Central Engine)"
    git push origin main --force-with-lease
    echo "🎉 [同步成功] 中央大脑与云端私有仓库已完美对齐。"
else
    echo "✨ [同步跳过] 本地未发现新增知识树变动。"
fi
