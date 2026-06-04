---
type: concept
created_at: 2026-06-04
last_modified: 2026-06-04
project: member
aliases: [BM25 缓存, bm25 cache, BM25 持久化索引, bm25_cache.pkl]
code_symbols: [bm25_search.py, build_or_load_cache, BM25Okapi, jieba]
initial_weight: 1.0
current_weight: 1.0
last_activated: 2026-06-04
access_count: 1
---

# BM25 持久化 Cache 索引

## 结论

`bm25_search.py` 将 BM25 索引序列化到 `_inbox/.bm25_cache.pkl`，通过 mtime 增量比对决定是否重建，将千篇笔记场景下的每次检索耗时从线性增长降至毫秒级。

## 问题根因

每次 `/brain-query` 都对全库执行 `jieba` 分词 + `BM25Okapi` 实例化，笔记超过 1000 篇时耗时线性增长，成为检索流的性能瓶颈。

## 缓存机制设计

### 数据结构
`_inbox/.bm25_cache.pkl` 中存储：
- `doc_paths`：所有笔记路径列表
- `corpus`：已 tokenize 的词条列表
- `mtime_map`：每个文件的最后修改时间（`{path: mtime}`）

### 重建策略
```python
def build_or_load_cache() -> BM25Okapi:
    if cache_exists:
        for path in all_md_files:
            if current_mtime(path) != cached_mtime(path):
                rebuild_full_cache()
                return new_index
        return cached_index
    else:
        build_full_cache()
```
任意文件 mtime 有变动 → 全量重建索引。文件全未变动 → 直接返回反序列化的缓存对象。

### 触发重建
`hot_watcher.sh` 检测到 `.md` 文件变化时，优先执行：
```bash
python3 scripts/bm25_search.py --rebuild-cache
```
再路由触发 hot_refresh。

## 关键约束

- 缓存文件路径 `CACHE_PATH = "_inbox/.bm25_cache.pkl"` 在脚本内作为绝对路径锁死，不由调用方传参。
- `build_or_load_cache()` 必须在 `jieba` 分词前调用 `extract_aliases()`，确保 aliases 注入 token 流（`utils.py`）。
- 并发写 cache 时不加锁（cache 写入是幂等操作，多进程同时重建最多导致覆盖写，无数据损坏风险）。

## 适用边界

- 适用于 `bm25_search.py` 的全库检索路径（BM25 主检索）。
- `rg_body_search.py`（正文正则检索）不使用此缓存，实时扫描。
- cache 文件损坏时自动降级为全量重建，不崩溃。

## 相关概念

- [[brain-os-architecture]]
- [[frontmatter-aliases-检索增强]]
- [[context-dehydration-pipeline]]
