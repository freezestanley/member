#!/bin/bash
# scripts/vault_sync.sh
VAULT_DIR="$(cd "$(dirname "${BASH_SOURCE}")/.." && pwd)"
cd "$VAULT_DIR" || exit
echo "🔄 启动 Git 增量原子化合并..."
git config merge.renormalize true
git fetch origin
git rebase origin/main > /dev/null 2>&1 || git rebase --skip
if [[ -n $(git status -s) ]]; then
    git add .
    git commit -m "🧠 LLM Auto-Sync: $(date '+%Y-%m-%d %H:%M:%S') (Claude Engine)"
fi
git push origin main --force-with-lease
echo "🎉 云端同步完成。"

