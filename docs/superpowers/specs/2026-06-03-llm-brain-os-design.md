# LLM-Brain OS 完整技术方案

> 创建日期：2026-06-03
> 用途：内部自用留档，记录记忆仓库的分层架构、数据流转、工具职责与 Skill 映射。
> Vault 路径：`/Users/za-stanlexu/Documents/member/member`

---

## 1. 系统定位

LLM-Brain OS 是一套本地知识图谱重构系统，核心目标：

1. 把 `_inbox/` 中的原始材料转成结构化 Obsidian 笔记。
2. 把对话记忆沉淀为可检索、可链接、可衰减的 Wiki 条目。
3. 通过 Skill 层对外暴露统一的读写接口，屏蔽底层脚本细节。

---

## 2. 分层架构（5 层）

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 5  Skill / Command 层                                 │
│  brain-query · brain-ingest · brain-consolidate             │
│  brain-search · brain-search-rg · brain-query-rg            │
├─────────────────────────────────────────────────────────────┤
│  Layer 4  检索引擎层                                          │
│  BM25（bm25_search.py）· rg_body_search.py                  │
│  aliases 注入 · jieba 分词 · 缓存（_inbox/.bm25_cache.pkl）  │
├─────────────────────────────────────────────────────────────┤
│  Layer 3  知识管理层                                          │
│  memory_manager.py（权重衰减 + 归档 + 断链修复）              │
│  hot_refresh.py（Top30 热榜大纲树）                          │
│  log_append.py（查询日志顶插）                               │
│  vault_sync.sh（Git 原子化云端同步）                         │
├─────────────────────────────────────────────────────────────┤
│  Layer 2  存储层（Obsidian Vault）                            │
│  wiki/global_concepts/      通用跨项目概念                   │
│  wiki/project_exclusives/   项目专属决策                     │
│  wiki/archive/              冷冻归档区                       │
│  wiki/hot.md                Top30 热度榜（只读，自动生成）    │
│  wiki/index.md              全库目录索引                     │
│  _inbox/                    原始材料暂存区                   │
├─────────────────────────────────────────────────────────────┤
│  Layer 1  基础设施层                                          │
│  Git（版本控制 + 远端同步）                                   │
│  hot_watcher.sh（fswatch 守护进程，监听 wiki/ 变化）          │
│  utils.py（公共工具：extract_aliases）                       │
│  Frontmatter Schema（标准元数据契约）                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 数据流转（3 条主路径）

### 3.1 路径 A：知识摄入

```
对话稳定结论
  → /brain-ingest
      → 判断归属（global_concepts / project_exclusives/<项目名>）
      → 写 .md + 完整 frontmatter
      → 追加 wiki/index.md 对应分区
      → vault_sync.sh
          → git add + commit + push（仅限 BRAIN_SYNC_BRANCH）
  → hot_watcher.sh 检测文件变化
      → hot_refresh.py
          → 扫描全库 current_weight 降序
          → 重写 wiki/hot.md（Top30 大纲树格式）
```

### 3.2 路径 B：知识检索

```
/brain-query <查询词>
  → L1 自查（优先，零命令行调用）
      → 当前会话上下文 + claude-mem 即时缓冲 + 当前打开草稿
      → 命中 → 直接回答，停止向下
  → L2 降级（仅 L1 明确失败后）
      → bm25_search.py "$QUERY" --project <项目名>
          → jieba 分词 + BM25Okapi 排序
          → aliases 字段注入 token 流（extract_aliases）
          → 读取缓存 .bm25_cache.pkl（无缓存则重建）
      → 读命中 Top3 全文
      → 回写 frontmatter（last_activated、last_modified、access_count+1）
      → log_append.py（顶插查询日志，保持 ≤50 条）
      → hot_watcher.sh 检测回写变化 → hot_refresh.py → hot.md
```

### 3.3 路径 C：记忆衰减与归档

```
/brain-consolidate（手动触发，建议每周或知识库明显膨胀时）
  → memory_manager.py
      → 扫描 global_concepts/ + project_exclusives/
      → 对每篇笔记计算：
          current_weight = initial_weight
                         × 2^(−days_since_activated / 30)
                         × (1 + 0.2 × ln(max(1, access_count)))
      → current_weight < 0.15 → archive_with_backlink_update()
          → 全库替换 [[笔记名]] → ~~[[笔记名]]~~（断链标注）
          → 物理移动文件到 wiki/archive/
      → 更新存活笔记的 current_weight 字段
  → hot_watcher.sh 检测变化 → hot_refresh.py → hot.md
```

---

## 4. 核心工具与脚本职责

| 脚本/文件 | 层级 | 职责 | 唯一写入权 |
|-----------|------|------|------------|
| `memory_manager.py` | L3 | 权重衰减 + 归档 + 断链修复 | `current_weight`、归档移动 |
| `bm25_search.py` | L4 | BM25 检索 + aliases 注入 + 缓存管理 | `_inbox/.bm25_cache.pkl` |
| `rg_body_search.py` | L4 | ripgrep 正则全文检索（备用路径） | — |
| `hot_refresh.py` | L3 | 生成 Top30 大纲树，重写 hot.md | `wiki/hot.md` |
| `hot_watcher.sh` | L1 | fswatch 守护，检测 wiki/ 变化触发 hot_refresh | 进程管理 |
| `log_append.py` | L3 | 查询日志顶插 + ≤50 条上限维护 | `wiki/log.md` |
| `vault_sync.sh` | L3 | git add + commit + push，锁分支校验，fcntl 锁等待 | remote |
| `utils.py` | L1 | `extract_aliases()` / `extract_aliases_as_line()` 公共工具 | — |

---

## 5. Frontmatter Schema

所有 `wiki/global_concepts/` 和 `wiki/project_exclusives/` 下的笔记必须携带：

```yaml
---
type: concept
created_at: YYYY-MM-DD
last_modified: YYYY-MM-DD        # 内容更新时改
project: global | <项目名>
aliases: []                      # 别名/缩写，BM25 + rg 两路注入
code_symbols: []                 # 关联函数、类、模块名
initial_weight: 1.0              # 人工设定，范围 0.1~1.0，不自动更改
current_weight: 1.0              # memory_manager.py 维护
last_activated: YYYY-MM-DD      # brain-query 命中时回写
access_count: 1                  # brain-query 命中时 +1
---
```

字段更新职责：

| 字段 | 更新触发 | 更新者 |
|------|----------|--------|
| `last_modified` | 内容更新 | brain-ingest / 手动 |
| `last_activated` | 被检索命中 | brain-query skill |
| `access_count` | 被检索命中 | brain-query skill |
| `current_weight` | 每次 consolidate | memory_manager.py |

---

## 6. Skill 层映射

| Skill | 触发时机 | 核心调用链 | 是否回写 frontmatter |
|-------|----------|------------|----------------------|
| `brain-query` | 需要历史决策/跨项目知识 | L1 自查 → bm25_search.py → 读全文 → 回写 | 是 |
| `brain-query-rg` | BM25 不命中时备用 | rg_body_search.py → 读全文 → 回写 | 是 |
| `brain-ingest` | 对话形成稳定结论后 | 写 .md → index.md → vault_sync.sh | 否（新建） |
| `brain-consolidate` | 每周 / 知识库膨胀时 | memory_manager.py | 是（批量） |
| `brain-search` | 纯关键词快速检索 | bm25_search.py（仅返回路径，不读全文） | 否 |
| `brain-search-rg` | rg 路径快速检索 | rg_body_search.py（仅返回路径） | 否 |

`brain-query` vs `brain-search` 的根本区别：前者有回写义务（激活计数），后者纯只读。

---

## 7. 目录结构速查

```
/Users/za-stanlexu/Documents/member/member/
├── _inbox/
│   ├── global_shared_raw/        跨项目公共规范原始材料
│   ├── palace_raw/               palace_bridge.sh 解压出的对话原始材料
│   └── .bm25_cache.pkl           BM25 索引缓存（gitignored）
├── scripts/
│   ├── utils.py                  公共工具
│   ├── bm25_search.py            BM25 检索引擎
│   ├── rg_body_search.py         rg 检索引擎
│   ├── memory_manager.py         权重衰减 + 归档
│   ├── hot_refresh.py            hot.md 生成器
│   ├── hot_watcher.sh            fswatch 守护进程
│   ├── log_append.py             查询日志写入
│   └── vault_sync.sh             Git 原子同步
├── skills/
│   ├── brain-query.md
│   ├── brain-query-rg.md
│   ├── brain-ingest.md
│   ├── brain-consolidate.md
│   ├── brain-search.md
│   └── brain-search-rg.md
└── wiki/
    ├── global_concepts/          通用概念笔记
    ├── project_exclusives/       项目专属笔记（按子目录分项目）
    ├── archive/                  冷冻归档
    ├── hot.md                    Top30 热度榜（只读，watcher 维护）
    ├── index.md                  全库目录索引
    └── log.md                    查询日志（≤50 条）
```

---

## 8. 关键约束与禁令

| 禁令 | 原因 |
|------|------|
| 禁止任何脚本/Skill 手动写入 `hot.md` | 唯一写入权属于 `hot_refresh.py`，防止格式冲突 |
| 禁止 `vault_sync.sh` 推送非 `BRAIN_SYNC_BRANCH` 分支 | fail-close 保护，防止知识笔记发布到错误分支 |
| 禁止绕过 `bm25_search.py` 直接 Grep 全库 | 破坏权重排序机制，BM25 分数失效 |
| 禁止把项目专属知识写入 `global_concepts/` | 污染全局共享层，误导跨项目检索 |
| `archive_with_backlink_update()` 必须先改双链再移文件 | 顺序锁定：移动后路径丢失，无法扫描 |
| 禁止 `brain-query` 在 L1 命中后继续检索 | L1 命中即停，避免无效消耗和误触回写 |
| 禁止 `brain-ingest` 合并多主题到同一文件 | 一文一议，保证原子化和检索精度 |

---

## 9. 守护进程管理

**hot_watcher.sh**（后台运行，不开机自启）

```bash
# 启动
nohup bash /Users/za-stanlexu/Documents/member/member/scripts/hot_watcher.sh \
  > /tmp/hot_watcher.log 2>&1 &

# 停止
pkill -f hot_watcher.sh

# 手动触发一次（watcher 未运行时）
python3 /Users/za-stanlexu/Documents/member/member/scripts/hot_refresh.py
```

watcher 内置防死循环机制：用 `fcntl` 文件锁（`_inbox/.hot_refresh.lock`）防止多进程同时写 `hot.md`；`vault_sync.sh` 在 push 前用同一锁机制等待写入完成（最多 10 秒）。

---

## 10. 已知边界与风险

| 风险点 | 现状 | 缓解措施 |
|--------|------|----------|
| 冷启动：`access_count=0` 导致 `ln(0)` 崩溃 | 已修复：`max(1, access_count)` | 单元测试覆盖 |
| BM25 缓存失效：文件增删后缓存不自动更新 | 已处理：文件列表 hash 变化时重建 | — |
| 并发冲突：多进程同时写 hot.md | 已修复：fcntl 文件锁 | — |
| 双链断链：归档后链接变成死链 | 已修复：`archive_with_backlink_update` | — |
| vault_sync 分支硬编码 | 已修复：动态读 `BRAIN_SYNC_BRANCH` 环境变量 | — |
| aliases 字段缺失导致缩写搜不到 | 已实现：`extract_aliases` 注入 token 流 | 规范要求每篇笔记填写 aliases |
