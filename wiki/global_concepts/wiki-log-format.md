---
type: concept
created_at: 2026-06-02
last_modified: 2026-06-02
project: global
code_symbols:
  - log_append
initial_weight: 1.0
current_weight: 1.0
last_activated: 2026-06-02
access_count: 1
---

# wiki/log.md 查询日志规范

## 结论

`wiki/log.md` 是 brain 系列命令（brain-query / brain-search / brain-search-rg / brain-query-rg）的执行日志，记录每次查询的命令、词条和结果摘要。所有写入必须通过 `scripts/log_append.py`，禁止手动编辑。

## 格式

```markdown
## YYYY-MM-DD

- YYYY-MM-DD HH:MM <命令名> "<查询词>" <命中N条：一句话不超过30字概括结果>
```

示例：
```markdown
## 2026-06-02

- 2026-06-02 20:23 brain-search "OpenClaw Browser SDK 架构" 命中2条：test-openclaw-sdk项目有架构与差异对比两篇笔记
- 2026-06-02 20:27 brain-query-rg "OpenClaw Browser SDK 架构" 命中0条：dome项目私有目录不存在
```

## 上限规则

- 最多保留 **50 条**记录，超出时从最旧记录开始删除
- 空日期组（标题下无记录）自动清除
- 由 `log_append.py` 在写入时自动修剪，无需人工干预

## 写入方式

```bash
python3 /Users/za-stanlexu/Documents/member/member/scripts/log_append.py \
  "<命令名>" "<查询词>" "<结果摘要，不超过30字>"
```

## 边界

- 只记录执行日志，不记录知识内容（知识内容在笔记文件中）
- 与 `hot.md`（热度排行榜）职责不同，两者互不替代
- 日期标题按当天自动分组，最新在前

## 相关概念

[[wiki-hot-watcher]] [[brain-query]] [[brain-search]]
