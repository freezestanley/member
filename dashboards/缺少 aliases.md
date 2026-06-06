# 缺少 aliases

```dataview
TABLE project, category, current_weight, last_modified
FROM "wiki"
WHERE status = "active" AND (aliases = null OR length(aliases) = 0)
SORT last_modified DESC
```
