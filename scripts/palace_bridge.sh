#!/bin/bash
# scripts/palace_bridge.sh

# 🚨 锁死你本地中央知识库的绝对路径（请将其替换为你电脑上的真实绝对路径）
BRAIN_DIR="/Users/za-stanlexu/Documents/member/member"

# 1. 动态感知当前开发项目的 Git 边界
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    PROJECT_NAME=$(basename "$(git rev-parse --show-toplevel)")
else
    PROJECT_NAME=$(basename "$(pwd)")
fi

CURRENT_WING="wing_project_${PROJECT_NAME}"
GLOBAL_WING="wing_global_shared"

echo "📥 [MemPalace] 正在从当前交互中挖掘项目专用记忆 -> ${CURRENT_WING}"
# 增量抓取当前项目的专属 Claude 交互数据进入特定 Wing [INDEX]
mempalace mine ~/.claude/projects/ --wing "${CURRENT_WING}" --mode convos
# 将当前项目的原始对话 100% 逐字稿实体化到中央知识库的暂存层 [INDEX]
mempalace sweep ~/.claude/projects/ --wing "${CURRENT_WING}" --output-dir "${BRAIN_DIR}/_inbox/palace_raw/" --format=md

# 2. 检查并强制增量灌入公共总规范投递箱（File-to-Wing Mapping）
if [ -d "${BRAIN_DIR}/_inbox/global_shared_raw" ] && [ "$(ls -A ${BRAIN_DIR}/_inbox/global_shared_raw)" ]; then
    echo "🪐 [MemPalace] 检测到公共总规范投递箱有变动，正在同步注入全局共享域 -> ${GLOBAL_WING}"
    mempalace mine "${BRAIN_DIR}/_inbox/global_shared_raw/" --wing "${GLOBAL_WING}"
fi

echo "✨ [MemPalace] 底层多租户隔离流水抽取完毕。"
