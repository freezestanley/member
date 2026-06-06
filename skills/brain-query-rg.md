---
name: brain-query-rg
description: 先自查当前会话与草稿热记忆，仅在事实不足时用 rg 精确检索当前项目私有记忆与公共记忆，并回写命中笔记激活信息与查询日志
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

# /brain-query-rg

严格执行"非必要不求助"漏斗模型：先检查自身会话上下文与即时缓冲区；只有在自身没有相关事实时，才允许用 rg 全文匹配检索，再基于命中笔记全文回答，并回写命中笔记的激活信息。

与 `/brain-query` 的唯一区别：检索引擎从 BM25 换成 rg 精确全文匹配。适合知道确切词汇、需要精准定位的场景。

## 参数说明

- `$ARGUMENTS` 格式：`<查询词> [--scope project|global] [--dry]`
- `--scope project`（默认）：仅搜索当前项目私有记忆 + 公共记忆（global_concepts）
- `--scope global`：搜索全库所有项目私有记忆 + 公共记忆，跨项目检索
- `--dry`：关闭脱水管道，直接读取笔记原文。适用场景：
  - 笔记篇幅短（< 50 行），脱水收益可忽略
  - 需要逐字引用原文，不能接受任何格式变化
  - 调试脱水管道本身时
  - 脱水后模型反馈"内容不足"时，切换 `--dry` 对比确认
  - 缺省时默认启用脱水（适合长笔记 / 含大量代码块 / frontmatter 占比高的大文件）

## 执行

1. 如果没有查询词，先要求补充，不要运行空查询。
2. 解析 `$ARGUMENTS`：
   - 提取 `--scope` 值（project 或 global），缺省为 `project`
   - 提取 `--dry` 标志：存在则 `DEHYDRATE=false`，缺省 `DEHYDRATE=true`
   - 剩余部分作为实际查询词
3. 必须先执行第一级决策：首选命中（自身热记忆自查）。
   - 全面内省你当前的会话窗口（Chat Context Window）以及 `claude-mem` 即时缓冲区。
   - 同时检查当前已打开、正在编辑、或当前会话中已贴出的物理文件草稿内容。
   - 如果关于查询词的核心技术规范、架构决策、代码原话，已经在当前会话或当前打开的物理文件草稿中清晰存在：
     - 你必须立刻停止所有检索。
     - 直接利用当前极热工作记忆执行下一步并回答用户。
     - 不得检索中央知识库。
     - 不得为了"确认一下"而额外调用 rg 或其他搜索脚本。
4. 仅当第 3 步确认以下任一条件成立时，才允许进入第二级决策：降级召回（中央记忆仓库外求）。
   - 你对该话题一片空白、毫无线索。
   - 当前会话被 `/compact`、`/clear` 或等效操作清空。
   - 当前会话与当前打开草稿中不存在足以支撑回答的事实依据。
5. 获取当前项目名：
   ```bash
   basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
   ```
6. 根据 `--scope` 值运行 rg 检索：
   - `--scope project`（默认）：
     ```bash
     python3 /Users/za-stanlexu/Documents/member/member/scripts/rg_body_search.py \
      "<查询词>" \
       /Users/za-stanlexu/Documents/member/member/wiki/global_concepts \
       /Users/za-stanlexu/Documents/member/member/wiki/project_exclusives/<当前项目名>
     ```
   - `--scope global`：
     ```bash
     python3 /Users/za-stanlexu/Documents/member/member/scripts/rg_body_search.py \
      "<查询词>" \
       /Users/za-stanlexu/Documents/member/member/wiki/global_concepts \
       /Users/za-stanlexu/Documents/member/member/wiki/project_exclusives
     ```
7. 解析命中文件路径（去重，取前 3 个不同文件）。根目录是：
   - `/Users/za-stanlexu/Documents/member/member`
8. 读取召回内容：
   - 若 `DEHYDRATE=false`（`--dry` 模式）：直接读取命中笔记全文，不做处理。
   - 若 `DEHYDRATE=true`（默认）：
     将步骤 6 的 rg 命中结果整理为 `文件路径:行号` 格式，同一文件多个命中行合并为逗号分隔，然后：
     ```bash
     python3 /Users/za-stanlexu/Documents/member/member/scripts/context_dehydrator.py \
       --mode precise \
       --hits <文件路径1>:<行号1,行号2> <文件路径2>:<行号3> \
       --max-tokens 8000
     ```
     将脚本 stdout 作为上下文，不再读取原文全文。
   - 未获得内容前，不要回答。
9. 仅基于已读笔记回答：
   - 优先使用笔记中的结论、约束、定义、经验
   - 如果多篇笔记冲突，明确指出冲突
   - 如果内容不足，明确说明不足
10. 激活每个命中文件：
   - 逐个处理命中文件，不要批量跳过
   - 路径必须使用命中文件绝对路径
   - 对每个文件执行：
     ```bash
     python3 /Users/za-stanlexu/Documents/member/member/scripts/activation_writer.py \
       --path "<命中文件绝对路径>" \
       --context "<原始查询词>"
     ```
   - 如果查询语境明确包含高优先级意图，可追加 `--boost 1.4`
   - 记录 stdout JSON 中的 `current_weight`、`ewma_access`、`last_boost`
   - 激活失败时报告部分失败，不要手动编辑 frontmatter
11. `wiki/hot.md` 由 `hot_watcher.sh` 后台进程自动刷新，无需手动触发。
   - 步骤 10 回写 frontmatter 后，watcher 检测到文件变化会自动调用 `hot_refresh.py`
   - 若 watcher 未运行，只报告热榜可能延迟刷新，不要手动写 `hot.md`
12. 更新 `wiki/log.md`（调用脚本，禁止手动写入）：
   ```bash
   python3 /Users/za-stanlexu/Documents/member/member/scripts/log_append.py \
     "brain-query-rg" "<查询词>" "<命中N条：一句话不超过30字概括结果>"
   ```
   脚本自动处理日期分组、顶部插入新日期、保持最多 50 条记录。
13. 输出最终答复；必要时补充本次依据了哪些笔记。

## 决策漏斗

### 1. 第一级：首选命中（自身热记忆自查）

- 优先检查当前会话窗口、`claude-mem`、当前已打开文件草稿。
- 只要其中任一处已经存在可直接支撑回答的事实，就直接执行下一步并回答。
- 一旦命中，必须停止所有检索。

### 2. 第二级：降级召回（中央记忆仓库外求）

- 只有在第一级明确失败后，才允许调用 rg 检索。
- 第二级的目标是补足缺失事实，不是重复验证当前会话里已经明确存在的内容。

## 成功标准

- 已先完成第一级自查，并且仅在自查失败后才进入第二级。
- 若第一级已命中，则 0 次 rg 检索、0 次中央知识库检索。
- 实际运行了 rg 检索命令。
- 回答前已读完命中文件全文。
- 回答可追溯到命中文件。
- 已通过 `activation_writer.py` 激活命中文件。
- hot.md 由 watcher 自动刷新。
- 已在 `log.md` 追加本次查询日志。

## 失败处理

- 如果第一级已命中但仍试图继续搜索，视为违反流程，必须中止并回退到直接回答。
- 检索结果为空时，明确说明未找到相关知识。
- 某个命中文件无法读取或 frontmatter 缺失时，说明异常，并标出可信度边界。
- 当前项目名无法判断时，跳过项目私有目录检索，仅检索 `global_concepts`，并说明原因。

## 输出模板

```markdown
回答：<基于命中文件的答案>

依据笔记：
- <文件路径1>
- <文件路径2>
- <文件路径3>

回写结果：<已更新 | 部分失败 | 未更新>
激活摘要：<current_weight=N, ewma_access=N, boost=N>
补充说明：<如无可写"无">
脱水状态：<已启用 | 已关闭（--dry 模式）>
```

如果命中第一级而未检索中央知识库，使用以下模板：

```markdown
回答：<基于当前会话上下文/当前草稿的答案>

依据来源：
- 当前会话上下文
- 当前打开的物理文件草稿（如适用）

检索状态：未检索中央知识库
补充说明：命中第一级"自身热记忆自查"，按规则停止外部求助
```

## 禁令

- 禁止跳过第一级自查，直接搜索中央知识库。
- 禁止在当前会话或当前草稿已存在明确事实时，仍调用任何检索命令。
- 禁止把中央知识库当作默认入口；它只能是第一级失败后的降级路径。
- `--scope project` 时，禁止检索 `project_exclusives` 的其他项目子目录（只查当前项目）。
- 禁止在未读完命中文件前回答。
- 禁止把未命中的文件当作本次依据。
- 禁止结果为空时仍声称找到了相关知识。
- 禁止手动写入 `hot.md`，由 hot_watcher.sh 或 hot_refresh.py 负责刷新。
- 禁止跳过 `log.md` 写入步骤，无论命中与否都必须记录。
