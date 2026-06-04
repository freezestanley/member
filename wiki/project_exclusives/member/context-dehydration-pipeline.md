---
type: concept
created_at: 2026-06-04
last_modified: 2026-06-04
project: member
aliases: [脱水管道, Context Dehydration Pipeline, 上下文脱水, Token 脱水堤坝]
code_symbols: [dehydrate_context, assemble_final_context, _build_hierarchy_map, context_dehydrator]
initial_weight: 1.0
current_weight: 1.0
last_activated: 2026-06-04
access_count: 1
---

# Context Dehydration Pipeline — LLM-Brain OS 上下文脱水管道

## 结论

在 L4 检索层（输出端）与 L5 Skill 层（输入端）之间插入 `context_dehydrator.py` 过滤管道，在内存中对召回的原始 Markdown 进行降噪、裁剪和压缩，使注入 Claude 上下文的 Token 量降低 60%+ 且不损失语义完整性。数据流不修改 `.md` 源文件。

## 生态位

```
[L4: bm25_search / rg_body_search 召回原始 MD 列表及命中行号]
                       │
                       ▼
    ┌──────────────────────────────────────┐
    │   L4.5  context_dehydrator.py        │
    ├──────────────────────────────────────┤
    │  1. 占位符转换：保护 [[stem]] 双链   │
    │  2. 结构树裁剪：大纲树感知提取       │
    │  3. 面包屑注入：H1>H2>H3 路径挂载   │
    │  4. Python 压榨：提取函数签名        │
    │  5. 占位符还原：恢复 [[stem]] 网络   │
    └──────────────────────────────────────┘
                       │
                       ▼
    [L5: Skill 拼装高含金量纯净上下文 → Claude API]
```

## 核心痛点（设计动因）

1. **字符水分**：原始笔记含 YAML frontmatter、HTML 注释、行尾空格、运行日志，直接烧穿上下文预算。
2. **盲目 Chunk 知识断裂**：按行数固定截断会切断跨段落上下文依赖，引发大模型幻觉。
3. **全局语义丢失（迷失在中间）**：丢失父标题层级后 Claude 无法定位 Chunk 所属模块。

## 五步管道详解

### 步骤 1：双链占位符保护（实体防御）
将 `[[stem]]` 替换为 `__BRAIN_LINK_XXX__` 占位符，防止后续压缩步骤打碎双链符号。压缩完成后恢复。

### 步骤 2：大纲树感知裁剪（结构防御）
- **代码块保护**：命中行若属于 ` ``` ` 代码块内部，必须完整保留整个代码块区间。
- **大纲块保护**：以命中行最近的 `###` 标题为起点，到下一同级或高级标题为终点，视为不可分割知识段落。

### 步骤 3：面包屑语义注入
从 H1、H2 标题中抽取路径，以下方格式注入 Chunk 顶部（<20字节，零噪音）：
```
[📍 Context Scope: Root > H1 > H2]
```

### 步骤 4：Python 压榨（条件路由）
- `< 5KB` 纯卡片笔记：仅做正则去噪（去 frontmatter、HTML 注释、行尾空格）。
- `≥ 5KB` 含代码块：调用 `_python_clean` 提取函数签名，剔除函数具体实现体。
- 注：原设计使用 `rtk`（Rust Token Killer），实现时已降级为纯 Python 实现，不引入外部二进制依赖。

### 步骤 5：双链还原
将占位符 `__BRAIN_LINK_XXX__` 替换回 `[[stem]]`，保证双链拓扑语义完好。

## 关键函数签名

```python
def dehydrate_context(raw_md: str, hit_lines: list[int], file_stem: str) -> str
def assemble_final_context(recalled_results: list[dict], max_total_tokens: int) -> str
def _build_hierarchy_map(lines: list[str]) -> list[dict]
```

- `dehydrate_context`：单文档脱水入口，rg 精准路径调用。
- `assemble_final_context`：多文档汇总，按 token 预算分配，超预算文档做截断降级（不丢弃首文档）。
- `_build_hierarchy_map`：逐行扫描标题层级，构建大纲路径快照。

## 集成点

四个 brain 命令（`brain-query`、`brain-query-rg`、`brain-search`、`brain-search-rg`）均在 `--dry` 开关下通过 CLI 调用 `context_dehydrator.py`，测试全覆盖。

## 适用边界

- 仅作用于内存管道，不写回 `.md` 源文件。
- BM25 路径（无命中行号）使用 summary 模式（全文脱水）；rg 路径（有命中行号）使用 precise 模式（感知裁剪）。
- `lineno=0` 时（alias 命中）自动 fallback 到 summary 模式。
- 超预算时首文档截断降级，不丢弃（见 `assemble_final_context` 修复）。

## 相关概念

- [[brain-os-architecture]]
- [[brain-commands-scope-parameter]]
- [[wiki-hot-watcher]]
