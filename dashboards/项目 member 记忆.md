# 项目 member 记忆

```dataview
TABLE category, current_weight, access_count, last_activated
FROM "wiki/project_exclusives/member"
WHERE status = "active"
SORT current_weight DESC
```
