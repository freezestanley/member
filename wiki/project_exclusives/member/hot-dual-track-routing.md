---
type: concept
created_at: 2026-06-04
last_modified: 2026-06-04
project: member
aliases: [双轨路由, hot 双轨, 热记忆双轨路由, global_hot, 项目 hot]
code_symbols: [hot_refresh.py, hot_watcher.sh, generate_hot_file, extract_markdown_headers]
initial_weight: 1.0
current_weight: 1.0
last_activated: 2026-06-04
access_count: 1
---

# 热记忆双轨路由 — Hot Dual-Track Routing

## 结论

将旧的单一 `wiki/hot.md`（全局混杂）拆分为双轨独立文件，由 `hot_watcher.sh` 按路径路由到对应刷新任务，彻底隔离全局元知识与项目专属知识，消除 Token 黑洞和跨项目污染。

## 架构演进

```
【旧方案：单轨混杂】
wiki/hot.md（全局共用）──> 堆积各项目高权笔记 ──> Token 黑洞（Claude 专注性受损）

【新方案：双轨路由】
                           ┌──> wiki/global_hot.md（仅限全局元知识 Top N=8）
fswatch 变更 ──> hot_watcher ┤
                           └──> wiki/project_exclusives/<项目名>/hot.md（项目隔离 Top M=20）
```

## 路由规则（hot_watcher.sh）

```bash
if [[ "$CHANGED_FILE" =~ wiki/global_concepts/ ]]; then
    python3 scripts/hot_refresh.py --global
elif [[ "$CHANGED_FILE" =~ wiki/project_exclusives/([^/]+)/ ]]; then
    PROJECT_NAME="${BASH_REMATCH[1]}"
    python3 scripts/hot_refresh.py --project "$PROJECT_NAME"
fi
```

- `global_concepts/` 下的变化 → 触发 `--global`，更新 `wiki/global_hot.md`
- `project_exclusives/<项目名>/` 下的变化 → 触发 `--project <项目名>`，更新对应项目 `hot.md`
- hot 文件自身变化被 fswatch `-e` 排除，防死循环

## 热记忆文件规范

两个 hot 文件统一采用**大纲树结构**，回显源笔记 H1~H3 层级，禁止平铺列表：

```markdown
### 1. [[stem]] — 标题 · 🧠0.92 · 📊14次
#### H1: 核心原则
##### H2: 什么是原子提交
```

标题树由 `extract_markdown_headers()` 从源笔记提取，`generate_hot_file()` 渲染写入。

## 分锁机制

- `hot_refresh.py` 对每个 hot 文件使用独立 `fcntl.LOCK_EX` 锁（而非共享单一锁），防止 `--global` 与 `--project` 并发互斥导致死锁。
- 锁文件路径：`_inbox/.hot_refresh.lock`（旧版共享锁），双轨版已改为各自持有独立锁。

## 上下文挂载

`CLAUDE.md` 静态引用双轨 hot 文件，session 启动时自动加载：

```markdown
- 当前项目热记忆：wiki/project_exclusives/<项目名>/hot.md
- 全局通用热记忆：wiki/global_hot.md
```

## 适用边界

- `wiki/hot.md` 已废弃（顶部添加 DEPRECATED 声明），不再自动更新。
- `global_hot.md` TOP_N=8，仅含跨项目通用元知识，禁止写入项目专属笔记。
- 各项目 `hot.md` TOP_M=20，禁止混入其他项目笔记。
- 切换项目前必须执行 `/clear`，防止旧项目热记忆残留。

## 相关概念

- [[wiki-hot-watcher]]
- [[brain-os-architecture]]
- [[context-dehydration-pipeline]]
