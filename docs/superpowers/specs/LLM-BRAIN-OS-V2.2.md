---
  LLM-Brain OS — 完整技术方案报告
  
  一、项目定位

  这是一个本地优先的个人知识图谱自动化操作系统。核心命题：把 LLM 对话产生的一次性上下文，持久化为带衰减权重的可检索 Obsidian Wiki，并在后续对话中以最低 token
  成本精准召回。

  ---
  二、业务流程
  
  原始输入
   ├─ 对话 (Claude /brain-ingest)
   ├─ 规范文档 (_inbox/global_shared_raw/)
   └─ MemPalace 挖掘 (palace_bridge.sh)
            │
            ▼
      [摄入层] _inbox/palace_raw/
            │
            ▼
      [知识蒸馏] /brain-ingest skill
      原子化笔记写入 → wiki/concepts/ or wiki/project_exclusives/
            │
            ├─ 实时触发
            │      hot_watcher.sh (fswatch)
            │      └─ hot_refresh.py (双轨路由)
            │           ├─ --global → wiki/global_hot.md (TOP 8)
            │           └─ --project <name> → hot.md (TOP 20)
            │
            ├─ 用户查询
            │      /brain-query <词>
            │      ├─ bm25_search.py (BM25 × current_weight 加权)
            │      └─ rg_body_search.py (正文 + alias 精准行号)
            │              └─ context_dehydrator.py
            │                   ├─ summary模式 (BM25命中)
            │                   └─ precise模式 (rg行号命中)
            │                         └─ → 注入 LLM 上下文
            │
            └─ 定期维护
                   /brain-consolidate
                   └─ memory_manager.py
                        ├─ 权重衰减 (指数衰减 × 频率奖励)
                        ├─ 孤儿.tmp 检测 → status: incomplete
                        ├─ frontmatter 自动补全
                        └─ weight < 0.15 → 归档到 archive/
                                vault_sync.sh → Git 推送

  ---
  三、分层架构
  
  ┌──────────────────────────────────────────────────────┐
  │                   USER INTERFACE LAYER               │
  │  Claude Skill (/brain-query /brain-ingest /brain-    │
  │  consolidate)   +   Obsidian Vault UI                │
  ├──────────────────────────────────────────────────────┤
  │                   RETRIEVAL LAYER                    │
  │  bm25_search.py          rg_body_search.py           │
  │  (语义召回 + 权重排序)    (正文精准行号匹配)          │
  │              └─── context_dehydrator.py ────┘        │
  │              (脱水：frontmatter剥离/面包屑/token限制)  │
  ├──────────────────────────────────────────────────────┤
  │                   HOT MEMORY LAYER                   │
  │  hot_watcher.sh (fswatch触发)                        │
  │  └─ hot_refresh.py (双轨：global/project)            │
  │       fcntl.flock 独占锁 + tmp rename 原子写          │
  ├──────────────────────────────────────────────────────┤
  │                   KNOWLEDGE STORE                    │
  │  wiki/global_concepts/    wiki/project_exclusives/   │
  │  (frontmatter schema)     (project隔离)              │
  │  archive/  (冷冻归档，vault内，链接零死链)            │
  │  _inbox/   (原始暂存，.bm25_cache.pkl)               │
  ├──────────────────────────────────────────────────────┤
  │                   LIFECYCLE ENGINE                   │
  │  memory_manager.py                                   │
  │  weight = initial × 2^(-days/30) × (1+0.2×log(n))   │
  │  weight < 0.15 → archive_with_backlink_update()      │
  ├──────────────────────────────────────────────────────┤
  │                   SYNC / BRIDGE LAYER                │
  │  palace_bridge.sh (MemPalace → _inbox)               │
  │  vault_sync.sh   (Git 原子推送, fcntl锁等待)         │
  │  utils.py        (aliases提取公共函数)               │
  └──────────────────────────────────────────────────────┘

  ---
  四、数据处理管道
  
  4.1 写入路径（摄入）

  raw text
    → frontmatter 自动生成 (_build_frontmatter)
    → status/superseded_by 字段补全 (_ensure_status_fields)
    → 孤儿 .tmp 检测 (原子写入保障)
    → wiki/ 落盘
    → hot_watcher 触发 → hot_refresh 写 hot.md
    → bm25 cache invalidate (mtime变化自动重建)

  4.2 检索路径

  BM25 路径（语义）：
  query string
    → jieba 分词 + aliases 注入
    → BM25Okapi.get_scores()
    → FinalScore = bm25_score × current_weight
    → 过滤 status: archived/deprecated/incomplete
    → Top 3
    → context_dehydrator summary模式
    → LLM context (max 8000 tokens)

  rg 路径（精准）：
  query string
    → rg_body_search.py (剥离frontmatter后逐行regex)
    → aliases 虚拟行 lineno=0 fallback
    → 命中行号列表
    → context_dehydrator precise模式
        → _build_hierarchy_map (面包屑)
        → _find_code_block_ranges (代码块保护)
        → 截取命中段 + [Omitted] 省略标记
    → assemble_final_context (token预算分配)

  4.3 衰减公式

  w = initial_weight × 2^(-days/30) × (1 + 0.2 × log(max(1, access_count)))

  阈值：
    w < 0.15 → 归档到 archive/
    archive/ 在 vault 内 → [[stem]] 链接零死链，Obsidian 自动解析

  ---
  五、技术特性
  
  ┌────────────────┬─────────────────────────────────────────────────────────┐
  │      特性      │                        实现方式                         │
  ├────────────────┼─────────────────────────────────────────────────────────┤
  │ 原子写入       │ fcntl.flock(LOCK_EX) + .tmp 文件 rename                 │
  ├────────────────┼─────────────────────────────────────────────────────────┤
  │ BM25 增量缓存  │ pickle + mtime 对比，仅变化文件触发重建                 │
  ├────────────────┼─────────────────────────────────────────────────────────┤
  │ 双链零死链     │ archive/ 与 wiki/ 同属 Obsidian vault，stem 自动解析    │
  ├────────────────┼─────────────────────────────────────────────────────────┤
  │ 双轨热记忆路由 │ fswatch → 路径正则判断 → global/project 分流            │
  ├────────────────┼─────────────────────────────────────────────────────────┤
  │ Token 预算管理 │ len(chunk) / 3.5 估算，首文档截断而非丢弃               │
  ├────────────────┼─────────────────────────────────────────────────────────┤
  │ Git 原子同步   │ fcntl 锁等待 + rebase 保持线性历史 + --force-with-lease │
  ├────────────────┼─────────────────────────────────────────────────────────┤
  │ 别名检索增强   │ aliases 字段注入 jieba 和 rg 双路检索流                 │
  ├────────────────┼─────────────────────────────────────────────────────────┤
  │ 生命周期自动化 │ cron/watcher 触发，无需手动干预                         │
  └────────────────┴─────────────────────────────────────────────────────────┘

  ---
  六、优缺点报告
  
  优点

  1. 知识持久化闭环完整
  从 LLM 对话 → 原子笔记 → 权重衰减 → 归档，全链路自动化，无信息孤岛。

  2. 检索精度与召回平衡
  BM25（语义宽召回）+ rg（精准行号）双路并行，互为补充。context_dehydrator 精准裁剪避免向 LLM 注入噪声。

  3. 原子写入保障一致性
  fcntl.flock 防止 fswatch 并发死锁，.tmp rename 防止写入一半的脏文件被检索。

  4. Obsidian 原生兼容
  frontmatter schema 标准化，archive/ 在 vault 内，双链不断，可直接在 Obsidian 中可视化浏览。

  5. Token 成本受控
  脱水管道剥除 frontmatter（约 15-25% 体积），面包屑裁剪精准段落，8000 token 预算硬限制。

  缺点 / 风险

  1. 硬编码绝对路径
  BRAIN_DIR = "/Users/za-stanlexu/Documents/member/member" 在多处脚本重复出现。跨机器迁移需逐文件修改，无环境变量抽象层。

  2. BM25 是词频模型，无语义理解
  中文同义词、近义概念无法命中（如查"脱水"找不到"context dehydration"）。jieba 分词在专有技术术语上精度有限。

  3. weight 衰减公式简单
  指数衰减不区分"主动被引用"和"被动经过时间"，频繁写入日志类笔记会虚假提升 access_count。

  4. MemPalace 依赖外部服务
  palace_bridge.sh 调用 mempalace CLI，若该服务不可用则摄入链路中断，但已有 _inbox/ 作为缓冲。

  5. fswatch 是 macOS 专属
  hot_watcher.sh 依赖 fswatch，Linux 需替换为 inotifywait，跨平台支持未封装。

  6. Git sync 的 force-with-lease 有协作风险
  单人使用安全。若多人共用同一 vault 仓库，rebase + force-with-lease

  4. Obsidian 原生兼容
  frontmatter schema 标准化，archive/ 在 vault
  内，双链不断，可直接在 Obsidian 中可视化浏览。

  5. Token 成本受控
  脱水管道剥除 frontmatter（约 15-25%
  体积），面包屑裁剪精准段落，8000 token 预算硬限制。

  缺点 / 风险

  1. 硬编码绝对路径
  BRAIN_DIR = "/Users/za-stanlexu/Documents/member/member"
  在多处脚本重复出现。跨机器迁移需逐文件修改，无环境变量抽象层。

  2. BM25 是词频模型，无语义理解
  中文同义词、近义概念无法命中（如查"脱水"找不到"context
  dehydration"）。jieba 分词在专有技术术语上精度有限。

  3. weight 衰减公式简单
  指数衰减不区分"主动被引用"和"被动经过时间"，频繁写入日志类笔记会虚
  假提升 access_count。

  4. MemPalace 依赖外部服务
  palace_bridge.sh 调用 mempalace
  CLI，若该服务不可用则摄入链路中断，但已有 _inbox/ 作为缓冲。

  5. fswatch 是 macOS 专属
  hot_watcher.sh 依赖 fswatch，Linux 需替换为
  inotifywait，跨平台支持未封装。

  4. MemPalace 依赖外部服务
  palace_bridge.sh 调用 mempalace CLI，若该服务不可用则摄入链路中断，但已有 _inbox/ 作为缓冲。
  4. MemPalace 依赖外部服务
  palace_bridge.sh 调用 mempalace CLI，若该服务不可用则摄入链路中断，但已有 _inbox/ 作为缓冲。

  5. fswatch 是 macOS 专属
  hot_watcher.sh 依赖 fswatch，Linux 需替换为 inotifywait，跨平台支持未封装。

  6. Git sync 的 force-with-lease 有协作风险
  单人使用安全。若多人共用同一 vault 仓库，rebase + force-with-lease 可能覆盖他人提交。

  7. archive/ 归档后无反向激活路径
  笔记归档后 weight 不会自动恢复，即使后续再次被引用也不会移回活跃区（仅 status 标记变化）。

  ---
  七、当前状态（2026-06-05）

  当前分支 feat/Pipeline，主分支 feat0602。

  - 已完成：memory_manager 归档链路、bm25 增量缓存、hot_refresh 双轨路由、context_dehydrator
  token预算首文档截断、vault_sync 双锁等待、archive 一致性方案
  - 待实现（规格已设计）：V2.1 RESILIENT 方案中的 zombie 检测/强制弃用拦截、symbol/alias map
  单源索引、双路冷冻备份（.pkl + .json）