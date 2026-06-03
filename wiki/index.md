# Wiki 索引

## global_concepts（跨项目通用）

- [团队通用编码规范](global_concepts/team-coding-standards.md) — 语言规范（全程中文）、图标库规范（禁用 ant-design/icons，用 lucide-react）
- [wiki/log.md 查询日志规范](global_concepts/wiki-log-format.md) — brain 系列命令查询日志格式、50条上限、log_append.py 写入规范
- [wiki/hot.md 自动刷新机制](global_concepts/wiki-hot-watcher.md) — fswatch+hot_refresh.py 自动维护热度排行榜，无需 skill 手动触发
- [Frontmatter aliases 字段：检索容错增强规范](global_concepts/frontmatter-aliases-检索增强.md) — aliases 字段在 BM25 和 rg 中的注入机制，防止缩写搜不到
