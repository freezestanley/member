---
name: brain-ingest
description: 将当前对话中已经稳定且可复用的单一知识点写入中央知识库，更新索引，并执行远端同步
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
---

# /brain-ingest

把当前对话中已经稳定、可复用的单一知识点写入中央知识库，并同步到远端。

## 执行

1. 先判断当前对话是否已经形成稳定结论。没有稳定结论则停止，并明确说明“不适合入库”。
2. 获取当前项目名：
   ```bash
   basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
   ```
3. 选择写入目录：
   - 通用知识 -> `/Users/za-stanlexu/Documents/member/member/wiki/global_concepts/`
   - 项目专属知识 -> `/Users/za-stanlexu/Documents/member/member/wiki/project_exclusives/<项目名>/`
4. 只写一篇笔记，一文一议。文件名必须是稳定的名词化主题。
5. 写入完整 frontmatter：
   ```markdown
   ---
   type: concept
   created_at: YYYY-MM-DD
   last_modified: YYYY-MM-DD
   project: <global或项目名>
   code_symbols: []
   initial_weight: 1.0
   current_weight: 1.0
   last_activated: YYYY-MM-DD
   access_count: 1
   ---
   ```
6. 正文先写结论，再写边界、细节、必要示例。相关概念尽量使用 `[[概念名]]`。
7. 更新 `wiki/index.md`：
   - 读取当前 `index.md` 全文
   - 在对应分区（`global_concepts` 或 `project_exclusives/<项目名>`）追加一行：
     `- [<笔记标题>](<相对路径>) — <一句话概括>`
   - 若该项目分区不存在，先新增分区标题再追加
8. `wiki/hot.md` 由 `hot_watcher.sh` 后台进程自动刷新，无需手动写入。
   - 步骤 7 写入新笔记后，watcher 检测到文件变化会自动调用 `hot_refresh.py`
   - 若 watcher 未运行，可手动执行一次：
     ```bash
     python3 /Users/za-stanlexu/Documents/member/member/scripts/hot_refresh.py
     ```
9. 执行同步：
   ```bash
   bash /Users/za-stanlexu/Documents/member/member/scripts/vault_sync.sh
   ```
10. 汇报新增笔记路径、核心结论、同步结果。

## 成功标准

- 只新增一篇单主题笔记。
- 目录归属正确，frontmatter 完整。
- 正文可脱离当前对话独立阅读。
- 已更新 `index.md` 对应分区。
- hot.md 由 watcher 自动刷新（或确认已手动刷新）。
- 已实际执行 `vault_sync.sh`。

## 失败处理

- 无法判断归属时，默认写入项目目录，并说明判断依据。
- 同步失败时，如实报告失败阶段和报错。

## 输出模板

```markdown
已新增笔记：<绝对路径>
知识归属：<global | 项目名>
核心结论：<一句话总结>
同步结果：<成功 | 失败>
补充说明：<如无可写“无”>
```

## 禁令

- 禁止把项目知识写入 `global_concepts`。
- 禁止把通用知识写入项目目录。
- 禁止多主题合并到同一文件。
- 禁止原样搬运整段对话。
- 禁止未执行同步就声称已同步。
- 禁止跳过 `index.md` 更新步骤。
- 禁止手动写入 `hot.md`，由 hot_watcher.sh 或 hot_refresh.py 负责刷新。
