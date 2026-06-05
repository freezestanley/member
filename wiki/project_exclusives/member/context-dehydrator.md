---
type: concept
created_at: 2026-06-05
last_modified: 2026-06-05
project: member
aliases: [上下文脱水, 脱水管道, dehydrator, context裁剪]
code_symbols: [context_dehydrator.py, dehydrate_context, assemble_final_context, _summary_mode, _build_hierarchy_map, _find_code_block_ranges]
initial_weight: 1.0
current_weight: 1.0
last_activated: 2026-06-05
access_count: 1
status: active
superseded_by: ""
---

# 上下文脱水管道（context_dehydrator）

## 结论

`context_dehydrator.py` 负责把检索结果裁剪为低噪声、带面包屑的 LLM 可用上下文。两种模式根据命中来源自动切换，token 预算超出时首文档截断而非丢弃。

## 两种模式

### summary 模式（BM25路径）
- 触发条件：`hit_lines=[]` 或 `hit_lines=[0]`（alias命中）
- 逻辑：剥离 frontmatter + HTML注释 + 死空格，保留完整正文
- 原因：BM25只知道"哪篇文档相关"，不知道哪行，完整正文最安全

### precise 模式（rg路径）
- 触发条件：`hit_lines=[n]`，n 为1-based行号
- 逻辑：
  1. `_build_hierarchy_map` 扫描全文，建立每行的H1/H2/H3层级快照
  2. `_find_code_block_ranges` 识别代码块范围（代码块整块保留）
  3. 普通段落：向上找最近标题为起点，向下找下一标题前为终点
  4. 输出带面包屑 `[📍 Context Scope: stem ➔ H1 ➔ H2]`
  5. 省略段落标记 `// ... [Omitted] ...`

## token 预算分配（assemble_final_context）

```python
# token估算：len(text) / 3.5（中英混合）
# 按score降序排列
# 超出预算时：
#   - 首文档：截断到剩余配额，追加 [截断提示]，保证有内容返回
#   - 后续文档：追加警告行，break
```

**关键约束**：首文档超预算时截断不丢弃，确保 LLM 至少获得最相关文档的部分内容。

## 双链保护

```python
_protect_links(text)   # [[stem]] → __BRAIN_LINK_n__ 占位符
_restore_links(text)   # 还原，防止裁剪打碎双链
```

## CLI 用法

```bash
# summary模式
python3 context_dehydrator.py --mode summary --files file1.md --max-tokens 8000

# precise模式
python3 context_dehydrator.py --mode precise --hits file1.md:3,7 file2.md:12 --max-tokens 8000
```

## 关联

- [[llm-brain-os-architecture]]
- [[bm25-memory-retrieval-pipeline]]
