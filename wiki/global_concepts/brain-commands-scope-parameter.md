---
type: concept
created_at: 2026-06-03
last_modified: 2026-06-03
project: global
code_symbols: []
initial_weight: 1.0
current_weight: 1.0
last_activated: 2026-06-03
access_count: 1
---

# brain-* 命令 `--scope` 参数约定

## 结论

4个 brain 检索命令均支持 `--scope project|global` 参数，用于切换搜索范围。缺省值依据命令原始语义设定，不破坏已有行为。

## 参数规则

| 命令 | 缺省值 | `--scope project` | `--scope global` |
|---|---|---|---|
| `brain-query` | `project` | 当前项目 + global_concepts | 全库所有项目 + global_concepts |
| `brain-query-rg` | `project` | 当前项目 + global_concepts | 全库所有项目 + global_concepts |
| `brain-search` | `global` | 当前项目 + global_concepts | 全库所有项目 + global_concepts |
| `brain-search-rg` | `global` | 当前项目 + global_concepts | 全库所有项目 + global_concepts |

## 边界

- query 系（BM25/rg 精准答案）缺省 `project`，避免跨项目噪音干扰回答质量。
- search 系（资产审计/分布查看）缺省 `global`，保持原有全库扫描语义。
- `--scope project` 时，rg/BM25 禁止访问 `project_exclusives` 的其他项目子目录。
- 参数不合法时，沿用缺省值并提示用户。

## 使用示例

```bash
# query 系：加 --scope global 扩展到全库
/brain-query BM25算法 --scope global
/brain-query-rg useEffect --scope global

# search 系：加 --scope project 收窄到当前项目
/brain-search 组件规范 --scope project
/brain-search-rg token验证 --scope project
```

## 关联

- [[brain-commands-functional-differences]] — query/search 核心功能差异
- [[wiki-log-format]] — 查询日志写入规范
