---
name: brain-consolidate
description: 执行中央知识库记忆衰减与归档，基于脚本输出汇总结果
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

# /brain-consolidate

执行中央知识库的记忆衰减和归档，并严格基于脚本输出汇报结果。

## 执行

1. 运行：
   ```bash
   python3 /Users/za-stanlexu/Documents/member/member/scripts/memory_manager.py
   ```
2. 读取脚本输出。该脚本扫描：
   - `/Users/za-stanlexu/Documents/member/member/wiki/global_concepts/`
   - `/Users/za-stanlexu/Documents/member/member/wiki/project_exclusives/`
   低权重笔记会被移入：
   - `/Users/za-stanlexu/Documents/member/member/wiki/archive/`
3. 整理结果：
   - 列出被归档的笔记路径和最终权重
   - 汇总保留笔记数量
   - 标出异常或跳过项
4. `wiki/hot.md` 由 `hot_watcher.sh` 后台进程自动刷新，无需手动写入。
   - `memory_manager.py` 更新 frontmatter 时，watcher 检测到文件变化会自动调用 `hot_refresh.py`
   - 若 watcher 未运行，可手动执行一次：
     ```bash
     python3 /Users/za-stanlexu/Documents/member/member/scripts/hot_refresh.py
     ```
5. 如果没有归档项，明确说明”本次没有归档任何笔记”。

## 成功标准

- 实际运行了 `memory_manager.py`。
- 汇报内容完全来自脚本输出。
- 明确区分归档、保留、异常。
- hot.md 由 watcher 自动刷新（或确认已手动刷新）。

## 失败处理

- 脚本失败时，直接报告报错，不要伪造结果。
- 脚本无输出时，明确说明“未观察到可解析输出”。

## 输出模板

```markdown
归档结果：
- 已归档：<路径> | 权重=<数值>

保留汇总：<数量>
异常项：<如无可写“无”>
```

## 禁令

- 禁止手工移动文件替代脚本。
- 禁止未运行脚本就声称已整理。
- 禁止把”无输出”自动解释成”无变更”。
- 禁止手动写入 `hot.md`，由 hot_watcher.sh 或 hot_refresh.py 负责刷新。
