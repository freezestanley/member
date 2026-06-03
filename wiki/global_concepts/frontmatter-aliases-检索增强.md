---
type: concept
created_at: 2026-06-03
last_modified: 2026-06-03
project: global
aliases: [别名检索, aliases字段, 检索容错]
code_symbols: [extract_aliases, extract_aliases_as_line, clean_and_tokenize, search_body]
initial_weight: 1.0
current_weight: 1.0
last_activated: 2026-06-03
access_count: 2
---

# Frontmatter aliases 字段：检索容错增强规范

## 结论

在每篇概念笔记的 Frontmatter 中声明 `aliases` 字段，BM25 和 rg_body_search 两个检索引擎会自动提取别名并注入检索流，使缩写、俗称、全称均可命中同一篇笔记。

## 标准格式

```yaml
---
type: concept
aliases: [LLM操作系统, BrainOS]   # 行内注释会自动剥离，不影响解析
code_symbols: []
...
---
```

- 空别名写 `aliases: []`，不省略字段（保持 Schema 完整性）
- 每个别名应为检索时可能用到的不同称呼（缩写、中文全称、英文缩写等）
- 禁止把噪声词（如"概念"、"笔记"）写入 aliases

## 两个检索引擎的处理机制

### BM25（bm25_search.py）

`extract_aliases(text)` 在 `clean_and_tokenize` 剥离 Frontmatter **之前**提取 aliases 内容，将其追加到 token 流末尾参与 TF-IDF 计算。

```python
alias_text = extract_aliases(text)          # 提取 "LLM操作系统 BrainOS"
text = re.sub(r"---.*?---", "", text, ...)  # 剥离整个 Frontmatter
combined = text + " " + alias_text          # alias 注入正文 token 流
```

效果：有 aliases 的笔记在用别名检索时 BM25 得分显著高于无别名笔记。

### rg_body_search（rg_body_search.py）

`extract_aliases_as_line(text)` 提取 aliases 后作为**虚拟行**追加到正文结尾参与 re 匹配。命中别名时：

- `lineno = 0`（区别于真实正文行）
- `line = "[alias] <别名内容>"`（明确标注来源）

```python
if alias_line and compiled.search(alias_line):
    results.append({"file": path, "lineno": 0, "line": f"[alias] {alias_line}"})
```

## 适用边界

- aliases 仅对 BM25 语义检索和 rg 精确匹配生效，不影响 Obsidian 内部的全文搜索
- 别名命中不等于正文相关，调用方需判断 `lineno == 0` 时是否降低权重
- aliases 本身在 Frontmatter 中，不会出现在 Obsidian 正文渲染结果里

## 关联概念

- [[wiki-hot-watcher]] — 笔记变更检测与 hot.md 刷新
- [[wiki-log-format]] — 查询日志规范
