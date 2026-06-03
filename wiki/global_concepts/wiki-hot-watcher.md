---
type: concept
created_at: 2026-06-02
last_modified: 2026-06-03
project: global
code_symbols:
  - hot_watcher
  - hot_refresh
initial_weight: 1.0
current_weight: 1.113
last_activated: 2026-06-03
access_count: 3
---

# wiki/hot.md 自动刷新机制

## 结论

`wiki/hot.md` 是全库笔记的热度排行榜，由 `hot_watcher.sh`（fswatch 监听）+ `hot_refresh.py`（扫描重写）两个脚本协作自动维护，不通过 skill 手动触发。

## 架构

```
brain 命令回写笔记 frontmatter
    └── .md 文件变化（排除 hot.md 自身）
          └── hot_watcher.sh（fswatch 监听）检测到变化
                └── hot_refresh.py 重写 hot.md（Top 30 排行榜）
```

## hot.md 格式

```markdown
# 知识热度榜 Top 30
> 更新时间：YYYY-MM-DD HH:MM　　数据来源：全库笔记 current_weight + access_count

| # | 笔记 | 权重 | 调用次数 |
|---|------|------|----------|
| 1 | [标题](相对路径) | 1.139 | 5 |
```

排序规则：`current_weight` 降序，同权重按 `access_count` 降序。

## 启停方式

```bash
# 启动（后台运行，不开机自启）
bash /Users/za-stanlexu/Documents/member/member/scripts/hot_watcher.sh &

# 停止
kill $(pgrep -f hot_watcher.sh)

# 临时手动刷新一次（watcher 未运行时）
python3 /Users/za-stanlexu/Documents/member/member/scripts/hot_refresh.py
```

## 防死循环机制

- `hot_watcher.sh` 明确排除 `hot.md` 自身，避免刷新触发再次刷新
- 2 秒冷却窗口：同批次多文件变化合并为一次触发

## 数据来源

扫描范围：`wiki/global_concepts/` + `wiki/project_exclusives/`（全部子目录）
读取字段：每篇笔记 frontmatter 中的 `current_weight`、`access_count`、标题

## 边界

- 不开机自启，需手动启动
- 依赖 `fswatch`（brew 安装），无需 Python 第三方库
- 禁止 skill 手动写入 hot.md

## 相关概念

[[wiki-log-format]] [[brain-query]]
