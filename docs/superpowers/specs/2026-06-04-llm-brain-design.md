---
  LLM-Brain OS 完整技术方案（代码视角，2026-06-04）
  
  一、目录结构与职责边界

  member/
  ├── _inbox/
  │   ├── .bm25_cache.pkl         ← bm25_search.py 独占写入
  │   └── .hot_refresh.lock       ← fcntl 互斥锁文件（hot_refresh.py / vault_sync.sh 共用）
  ├── wiki/
  │   ├── global_concepts/        ← 跨项目通用概念笔记
  │   ├── project_exclusives/
  │   │   └── <项目名>/          ← 项目专属笔记（例：member/、test-openclaw-sdk/）
  │   ├── archive/                ← 权重 < 0.15 冷冻归档区
  │   ├── hot.md                  ← hot_refresh.py 独占写入，禁止手动触碰
  │   ├── index.md                ← memory_manager.py 独占重写
  │   └── log.md                  ← log_append.py 独占写入
  └── scripts/
      ├── utils.py                ← extract_aliases() 公共工具
      ├── bm25_search.py          ← 检索引擎（BM25Okapi + jieba + aliases + mtime缓存）
      ├── rg_body_search.py       ← 正文正则检索（aliases虚拟行注入）
      ├── memory_manager.py       ← 衰减计算 + 归档 + index.md重写
      ├── hot_refresh.py          ← Top 30 热度榜重写（fcntl文件锁防并发）
      ├── log_append.py           ← log.md 追加（日期分组，最多50条）
      ├── hot_watcher.sh          ← fswatch 守护进程（cooldown=2s，变化触发双刷新）
      ├── vault_sync.sh           ← Git 原子同步（fail-close + 锁等待）
      └── palace_bridge.sh        ← MemPalace 对话原始材料解压

  ---
  二、五层架构
  
  ┌──────┬────────────┬────────────────────────────────────────────────────────────────────────────────────────┐
  │ 层级 │    名称    │                                          实体                                          │
  ├──────┼────────────┼────────────────────────────────────────────────────────────────────────────────────────┤
  │ L5   │ Skill 层   │ brain-query brain-ingest brain-consolidate brain-search brain-search-rg brain-query-rg │
  ├──────┼────────────┼────────────────────────────────────────────────────────────────────────────────────────┤
  │ L4   │ 检索引擎层 │ bm25_search.py（主）rg_body_search.py（辅）                                            │
  ├──────┼────────────┼────────────────────────────────────────────────────────────────────────────────────────┤
  │ L3   │ 知识管理层 │ memory_manager.py hot_refresh.py log_append.py vault_sync.sh                           │
  ├──────┼────────────┼────────────────────────────────────────────────────────────────────────────────────────┤
  │ L2   │ 存储层     │ wiki/global_concepts/ wiki/project_exclusives/ wiki/archive/ hot.md index.md log.md    │
  ├──────┼────────────┼────────────────────────────────────────────────────────────────────────────────────────┤
  │ L1   │ 基础设施层 │ utils.py hot_watcher.sh（fswatch守护）Git / fcntl 文件锁                               │
  └──────┴────────────┴────────────────────────────────────────────────────────────────────────────────────────┘

  ---
  三、三条主数据流（代码级）
  
  3.1 检索流（brain-query）

  brain-query skill
    → L1自查（会话热记忆）
    → 失败后：bm25_search.py "<词>" --project <name>
        ├─ build_or_load_cache()  检查每个 .md 的 mtime
        │   ├─ 命中：直接返回 pickle 缓存
        │   └─ 未命中：clean_and_tokenize() → 重建 → 写 .bm25_cache.pkl
        ├─ extract_aliases() 注入 token 流（utils.py，剥离FM前调用）
        ├─ BM25Okapi.get_scores() × current_weight → 加权排序
        └─ 输出 Top 3 相对路径
    → Skill 读全文 → 回写3字段（last_activated/last_modified/access_count+1）
    → log_append.py "<cmd>" "<词>" "<摘要>"
    → hot_watcher.sh 检测FM变化 → hot_refresh.py（自动）

  关键代码细节：
  - bm25_search.py 的 --project 参数将 search_dirs 限定为 [GLOBAL_DIR, project_exclusive_dir]，但 cache 始终全库构建，再通过 allowed_prefixes 过滤结果（缓存不分
  project，避免多 project 污染彼此缓存）
  - final_score = doc_scores[idx] * current_weight：原始 BM25 分乘以记忆权重，实现"热门知识优先"

  3.2 摄入流（brain-ingest）

  brain-ingest skill
    → 提炼对话结论 → 写 .md（含 Frontmatter Schema）
    → 更新 wiki/index.md（memory_manager.py render_global_indices()）
    → vault_sync.sh（可选：自动 commit+push）
    → hot_watcher.sh → hot_refresh.py（自动）

  3.3 衰减流（brain-consolidate）

  3.1 检索流（brain-query）

  brain-query skill
    → L1自查（会话热记忆）
    → 失败后：bm25_search.py "<词>" --project <name>
        ├─ build_or_load_cache()  检查每个 .md 的 mtime
        │   ├─ 命中：直接返回 pickle 缓存
        │   └─ 未命中：clean_and_tokenize() → 重建 → 写 .bm25_cache.pkl
        ├─ extract_aliases() 注入 token 流（utils.py，剥离FM前调用）
        ├─ BM25Okapi.get_scores() × current_weight → 加权排序
        └─ 输出 Top 3 相对路径
    → Skill 读全文 → 回写3字段（last_activated/last_modified/access_count+1）
    → log_append.py "<cmd>" "<词>" "<摘要>"
    → hot_watcher.sh 检测FM变化 → hot_refresh.py（自动）

  关键代码细节：
  - bm25_search.py 的 --project 参数将 search_dirs 限定为 [GLOBAL_DIR, project_exclusive_dir]，但 cache 始终全库构建，再通过 allowed_prefixes 过滤结果（缓存不分
  project，避免多 project 污染彼此缓存）
  - final_score = doc_scores[idx] * current_weight：原始 BM25 分乘以记忆权重，实现"热门知识优先"

  3.2 摄入流（brain-ingest）

  brain-ingest skill
    → 提炼对话结论 → 写 .md（含 Frontmatter Schema）
    → 更新 wiki/index.md（memory_manager.py render_global_indices()）
    → vault_sync.sh（可选：自动 commit+push）
    → hot_watcher.sh → hot_refresh.py（自动）

  3.3 衰减流（brain-consolidate）

  brain-consolidate skill
    → memory_manager.py scan_and_clean()
        对每篇 .md：
          new_w = initial_w × 2^(−days/30) × (1 + 0.2×ln(max(1, access_count)))
          if new_w < 0.15:
            archive_with_backlink_update(path, ARCHIVE_DIR, wiki_root)
              ① 全库扫 [[note_stem]] → ~~[[note_stem]]~~（先改链）
              ② os.rename(path → archive/)  （后移文件）
          else:
            回写 current_weight 到 frontmatter
    → render_global_indices() 重写 index.md（无时间戳，减少 git diff churn）

  ---
  四、关键机制与代码约束

  4.1 BM25缓存（_inbox/.bm25_cache.pkl）

  缓存结构：{"mtimes": {...}, "doc_paths": [...], "corpus": [[tokens], ...]}

  重建条件：路径集合变化 OR 任意文件 mtime 不一致。hot_watcher.sh 变化后触发 --rebuild-cache 强刷。

  4.2 aliases 双路注入

  utils.py 的 extract_aliases(text) 必须在 FM 剥离前调用。注入路径：

  - bm25_search.py：append 到 combined = text + " " + alias_text，进 jieba 分词流
  - rg_body_search.py：作为虚拟行 [alias] ... 追加，lineno=0 标记

  4.3 hot.md 并发锁

  hot_refresh.py 用 fcntl.flock(LOCK_EX | LOCK_NB)。vault_sync.sh 通过 Python 内联脚本探测 flock(LOCK_EX | LOCK_NB) 是否可获取，等待最多10秒。两者共用同一个
  _inbox/.hot_refresh.lock 文件（锁文件不删除，持久化标记）。

  4.4 vault_sync fail-close

  SYNC_BRANCH="${BRAIN_SYNC_BRANCH:-main}"
  # 当前分支 ≠ SYNC_BRANCH → exit 1（拒绝推送）

  允许通过环境变量覆盖，例如 BRAIN_SYNC_BRANCH=feat0602 bash vault_sync.sh。

  4.5 归档顺序锁定

  archive_with_backlink_update() 强制顺序：先全库替换 [[stem]] → ~~[[stem]]~~，再 os.rename()。顺序颠倒会导致移动后找不到文件路径，产生断链。

  4.6 衰减公式防御

  safe_count = max(1, access_count) 防止 ln(0) 报错。

  ---
  五、唯一写入权表（写权边界）
  
  ┌────────────────────────┬─────────────────────────────────┐
  │     目标文件/目录      │          唯一写入脚本           │
  ├────────────────────────┼─────────────────────────────────┤
  │ _inbox/.bm25_cache.pkl │ bm25_search.py                  │
  ├────────────────────────┼─────────────────────────────────┤
  │ wiki/hot.md            │ hot_refresh.py                  │
  ├────────────────────────┼─────────────────────────────────┤
  │ wiki/log.md            │ log_append.py                   │
  ├────────────────────────┼─────────────────────────────────┤
  │ wiki/index.md          │ memory_manager.py               │
  ├────────────────────────┼─────────────────────────────────┤
  │ current_weight 字段    │ memory_manager.py               │
  ├────────────────────────┼─────────────────────────────────┤
  │ wiki/archive/          │ memory_manager.py               │
  ├────────────────────────┼─────────────────────────────────┤
  │ remote Git             │ vault_sync.sh（限 SYNC_BRANCH） │
  └────────────────────────┴─────────────────────────────────┘

  last_activated / last_modified / access_count 由 brain-query skill 在 Skill 层直接回写（不经过脚本）。

  ---
  六、当前代码与旧文档的实质差异
  
  ┌─────────────────────────┬────────────────────────────────────────────────┬──────────────────────────────────────────────────────────────────────────┐
  │         差异点          │                   旧文档描述                   │                                 代码实际                                 │
  ├─────────────────────────┼────────────────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤
  │ 目录命名                │ wiki/global_concepts/ wiki/project_exclusives/ │ 与代码一致                                                               │
  ├─────────────────────────┼────────────────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤
  │ hot.md 格式             │ 简单列表                                       │ 大纲树（### N. [[stem]] — title · 🧠 weight · 📊 N次，含 H1-H3 outline） │
  ├─────────────────────────┼────────────────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤
  │ index.md 时间戳         │ 含时间戳                                       │ 无时间戳（减少 git diff churn，render_global_indices() 注释明确说明）    │
  ├─────────────────────────┼────────────────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤
  │ hot_watcher.sh 触发动作 │ 仅触发 hot_refresh.py                          │ 同时触发 bm25_search.py --rebuild-cache（两步串行）                      │
  ├─────────────────────────┼────────────────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤
  │ vault_sync.sh 分支检测  │ 硬编码 main                                    │ 读 BRAIN_SYNC_BRANCH 环境变量，默认 main                                 │
  ├─────────────────────────┼────────────────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤
  │ 缓存范围                │ 按 project 分缓存                              │ 全库建缓存，search_dirs 过滤结果（cache 不分 project）                   │
  └─────────────────────────┴────────────────────────────────────────────────┴──────────────────────────────────────────────────────────────────────────┘

  ---