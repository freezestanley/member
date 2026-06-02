#!/bin/bash
# scripts/palace_bridge.sh

# 🗂️ 1. 私有知识动态抓取（基于当前激活的 Git 代码库）
PROJECT_NAME=$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")
CURRENT_WING="wing_project_${PROJECT_NAME}"

echo "📥 [MemPalace] 正在从 Claude Code 历史中挖掘私有项目记忆 -> ${CURRENT_WING}"
mempalace mine ~/.claude/projects/ --wing "${CURRENT_WING}" --mode convos
mempalace sweep ~/.claude/projects/ --wing "${CURRENT_WING}" --output-dir ./_inbox/palace_raw/ --format=md

# 🤖 2. 公共知识自动分流（语义审查与搬运）
echo "🧠 [LLM-Brain Engine] 正在对 _inbox/ 的零碎剪藏与文档执行全自动路由分流..."

# 我们用一段轻量 Python 或直接让 Claude 在 Ingest 阶段读取 _inbox/。
# 规则：如果网页剪藏或文档的 Frontmatter 中包含 tags: [global, share, standard] 
# 或者由 Claude 判断属于非特定项目的通用规范，则执行以下动作：
# a. 将文件移动到 _inbox/global_shared_raw/
# b. 强制运行下行合法的官方命令，精准喂养公共记忆区：
mempalace mine ./_inbox/global_shared_raw/ --wing "wing_global_shared"


