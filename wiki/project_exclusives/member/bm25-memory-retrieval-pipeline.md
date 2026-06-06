---
type: concept
created_at: 2026-06-05
last_modified: 2026-06-06
project: member
aliases: [BM25检索, 记忆检索管道, bm25搜索]
code_symbols: [bm25_search.py, build_or_load_cache, clean_and_tokenize, collect_md_paths]
initial_weight: 1.0
current_weight: 1.0
last_activated: 2026-06-06
access_count: 4
status: active
superseded_by: ""
weight_schema_version: 2
category: spec
importance: 3
ewma_access: 0.0
last_boost: 1.0
last_boosted_at: ""
last_weight_migrated_at: 2026-06-06
tags:
  - memory/active
  - type/concept
  - project/member
  - category/spec
cssclasses:
  - memory-note
---

# BM25 记忆检索管道

## 结论

检索入口是 `bm25_search.py`。最终得分 = `BM25Okapi分数 × current_weight`，过滤已归档/弃用文件，输出 Top 3。

## 检索路径

```
query string
  → jieba分词 + aliases字段注入
  → BM25Okapi.get_scores()
  → FinalScore = bm25_score × current_weight
  → 过滤 status: archived/deprecated/incomplete
  → Top 3
  → context_dehydrator summary模式
  → LLM context (max 8000 tokens)
```

## 增量缓存机制

Cache 结构（pickle，存于 `_inbox/.bm25_cache.pkl`）：

```python
{
  "mtimes": {文件路径: mtime_float},
  "doc_paths": [...],
  "corpus": [[tokens], ...]
}
```

**重建条件：**
- cache 文件不存在
- 任意文件 mtime 与缓存记录不一致
- 有新文件未在缓存中

命中时直接返回，无重建开销。

## 文本预处理（clean_and_tokenize）

处理顺序不可颠倒：
1. 提取 aliases（在 frontmatter 剥离前）
2. 剥离 YAML frontmatter（锚定 `^` 行首）
3. 移除 Markdown 注释块
4. 剥离 Markdown 符号 `[[ ]] # * \``
5. 行级清理 + 连续空行压缩
6. jieba 分词，aliases 追加到 token 流末尾

## 参数说明

```bash
# 全局检索
python3 bm25_search.py "关键词"

# 项目范围限制
python3 bm25_search.py "关键词" --project member

# 仅重建缓存
python3 bm25_search.py --rebuild-cache
```

## 局限性

- 词频模型，不理解语义：查"脱水"找不到"context dehydration"。
- jieba 在专有技术术语上精度有限。
- aliases 注入是主要补偿手段。
- cache 写入无文件锁，多人/并发场景需增加 `.bm25_cache.lock`。

## 关联

- [[llm-brain-os-architecture]]
- [[context-dehydrator]]
- [[memory-weight-decay]]
