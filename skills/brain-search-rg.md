---
name: brain-search-rg
description: 先自查当前会话热记忆，仅在事实不足时用 rg 跨公共笔记、项目私有笔记与历史会话做精确资产审计，并回写命中笔记激活信息与查询日志
allowed-tools:
  - Read
  - Bash(npm *)
  - Bash(git *)
  - Bash(find *)
  - Bash(cat *)
  - basename(*)
  - Bash(python3 *)
  - Edit(/Users/za-stanlexu/Documents/member/member/*)
  - Bash(mkdir *)
  - Bash(/Users/za-stanlexu/Documents/member/member/scripts/*)
---

# /brain-search-rg

严格执行"非必要不求助"漏斗模型：先检查自身会话上下文与即时缓冲区；只有在自身没有相关事实时，才允许用 rg 全文匹配在整个中央知识库与历史会话中做跨项目检索，用来盘点某个关键词在公共规范、项目专属笔记和历史讨论中的分布。

与 `/brain-search` 的唯一区别：检索引擎从 BM25 换成 rg 精确全文匹配。适合知道确切词汇、需要审计完整出现位置的场景。

它的目标是"找资产、看分布、做审计"；如果用户要基于知识库给出精准答案，优先使用 `/brain-query-rg`。

## 执行

1. 如果没有检索词，先要求补充，不要运行空查询。
2. 必须先执行第一级决策：首选命中（自身热记忆自查）。
   - 全面内省你当前的会话窗口（Chat Context Window）以及 `claude-mem` 即时缓冲区。
   - 同时检查当前已打开、正在编辑、或当前会话中已贴出的物理文件草稿内容。
   - 如果关于 `"$ARGUMENTS"` 的跨项目资产分布、规范归属、历史结论，已经在当前会话或当前打开的物理文件草稿中清晰存在：
     - 你必须立刻停止所有检索。
     - 直接利用当前极热工作记忆执行下一步并输出结果。
     - 不得检索中央知识库。
     - 不得为了"确认一下"而额外调用 rg、搜索脚本或历史记忆工具。
3. 仅当第 2 步确认以下任一条件成立时，才允许进入第二级决策：降级召回（中央记忆仓库外求）。
   - 你对该话题一片空白、毫无线索。
   - 当前会话被 `/compact`、`/clear` 或等效操作清空。
   - 当前会话与当前打开草稿中不存在足以支撑审计报告的事实依据。
4. 先做本地 Wiki rg 全库全文检索（公共记忆 + 所有项目私有记忆）：
   ```bash
   python3 /Users/za-stanlexu/Documents/member/member/scripts/rg_body_search.py \
     "$ARGUMENTS" \
     /Users/za-stanlexu/Documents/member/member/wiki/global_concepts \
     /Users/za-stanlexu/Documents/member/member/wiki/project_exclusives
   ```
5. 再检索 MemPalace 历史记忆：
   - 先获取当前项目名：
     ```bash
     basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
     ```
   - 公共规范域：
     ```bash
     mempalace search "$ARGUMENTS" --wing "wing_global_shared" --limit 3
     ```
   - 当前项目域：
     ```bash
     mempalace search "$ARGUMENTS" --wing "wing_project_<当前项目名>" --limit 3
     ```
   - 只有当用户明确要求"跨所有项目历史会话"时，才额外执行：
     ```bash
     mempalace search "$ARGUMENTS" --limit 5
     ```
6. 合并检索结果并输出"跨项目技术资产审计报告"：
   - `公共规范沉淀`：列出 `wiki/global_concepts/` 中命中的笔记路径，并概括其主题或规则。
   - `历史项目独占实例`：按 `project_exclusives/<项目名>/` 分组列出命中文件，说明各项目里记录的是实现、约束还是踩坑。
   - `历史会话记忆`：列出 MemPalace 命中的 wing、条目标识和必要短摘录；只允许基于真实命中做精简，不得伪造原话。
   - `结论`：总结该关键词更偏"通用规范"还是"项目专属经验"，并在必要时提示下一步用 `/brain-query-rg` 深读。
7. 回写本地 Wiki 命中笔记的 frontmatter：
   - 逐个打开命中文件，不要批量跳过
   - 校验 frontmatter 是否存在
   - `last_activated`: 改为今天，`YYYY-MM-DD`
   - `last_modified`: 改为今天，`YYYY-MM-DD`
   - `access_count`: 在原值基础上加 1
   - 只改这 3 个字段，不改其他字段
   - 每改完一个文件，确认已保存
8. `wiki/hot.md` 由 `hot_watcher.sh` 后台进程自动刷新，无需手动触发。
   - 步骤 7 回写 frontmatter 后，watcher 检测到文件变化会自动调用 `hot_refresh.py`
   - 若 watcher 未运行，可手动执行一次：
     ```bash
     python3 /Users/za-stanlexu/Documents/member/member/scripts/hot_refresh.py
     ```
9. 更新 `wiki/log.md`（调用脚本，禁止手动写入）：
   ```bash
   python3 /Users/za-stanlexu/Documents/member/member/scripts/log_append.py \
     "brain-search-rg" "<查询词>" "<命中N条：一句话不超过30字概括结果>"
   ```
   脚本自动处理日期分组、顶部插入新日期、保持最多 50 条记录。
10. 如果本地 Wiki 和 MemPalace 都没有命中，明确说明"未找到相关跨项目资产"。

## 决策漏斗

### 1. 第一级：首选命中（自身热记忆自查）

- 优先检查当前会话窗口、`claude-mem`、当前已打开文件草稿。
- 只要其中任一处已经存在可直接支撑审计结论的事实，就直接执行下一步并输出结果。
- 一旦命中，必须停止所有检索。

### 2. 第二级：降级召回（中央记忆仓库外求）

- 只有在第一级明确失败后，才允许调用 rg 检索与 MemPalace 检索。
- 第二级的目标是补足缺失事实，不是重复验证当前会话里已经明确存在的内容。

## 成功标准

- 已先完成第一级自查，并且仅在自查失败后才进入第二级。
- 若第一级已命中，则 0 次 rg 检索、0 次 MemPalace 检索。
- 实际运行了 rg 检索命令。
- 实际运行了至少公共规范域和当前项目域的 MemPalace 检索。
- 汇报内容可追溯到真实命中结果。
- 明确区分公共规范、项目专属和历史会话三类来源。
- 已回写所有命中本地 Wiki 笔记的 frontmatter（access_count+1, last_activated 更新）。
- hot.md 由 watcher 自动刷新（或确认已手动刷新）。
- 已在 `log.md` 追加本次检索日志。

## 失败处理

- 如果第一级已命中但仍试图继续搜索，视为违反流程，必须中止并回退到直接输出。
- 当前项目名无法判断时，跳过当前项目 wing 检索，并说明原因。
- `mempalace` 不可用或检索失败时，如实报告失败阶段，不要伪造历史结果。
- 本地 Wiki 有命中但 MemPalace 无命中时，明确说明"仅找到文档资产，未找到历史会话记忆"。

## 输出模板

```markdown
跨项目技术资产审计报告

公共规范沉淀：
- <笔记路径>：<一句话概括>

历史项目独占实例：
- <项目名>：<文件路径> | <实现 / 约束 / 踩坑>

历史会话记忆：
- <wing 或条目标识>：<短摘录或主题概括>

结论：<该关键词的归属判断与建议动作>
补充说明：<如无可写"无">
```

如果命中第一级而未检索中央知识库，使用以下模板：

```markdown
跨项目技术资产审计报告

公共规范沉淀：
- 当前会话上下文中已有相关结论

历史项目独占实例：
- 当前打开的物理文件草稿（如适用）

历史会话记忆：
- 未检索

结论：<基于当前会话上下文/当前草稿的归属判断与建议动作>
补充说明：命中第一级"自身热记忆自查"，按规则停止外部求助
```

## 禁令

- 禁止跳过第一级自查，直接搜索中央知识库或历史会话。
- 禁止在当前会话或当前草稿已存在明确事实时，仍调用任何检索命令。
- 禁止把中央知识库或 MemPalace 当作默认入口；它们只能是第一级失败后的降级路径。
- 禁止使用硬编码占位路径，如 `/Users/你的用户名/...`。
- 禁止把 `/brain-search-rg` 当作 `/brain-query-rg` 的替代品直接输出确定性结论。
- 禁止在没有真实 MemPalace 命中的情况下编造"历史原话"。
- 禁止只贴原始搜索结果，不做分组和归类。
- 禁止手动写入 `hot.md`，由 hot_watcher.sh 或 hot_refresh.py 负责刷新。
- 禁止跳过 `log.md` 写入步骤，无论命中与否都必须记录。
