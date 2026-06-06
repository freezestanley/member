# 知识热度榜 Top 20 — 项目 member
> 更新时间：2026-06-06 10:44　　数据来源：current_weight + access_count
> [!WARNING]
> 本文件由 `hot_refresh.py` 自动生成，禁止手动编辑。

### 1. [[hot-memory-dual-track]] — 热记忆双轨路由  ·  🧠 1.000  ·  📊 4 次
- 热记忆双轨路由
  - 结论
  - 双轨路由逻辑
- hot_watcher.sh 路由判断
  - 排序规则
- 主键：current_weight，次键：access_count
  - 原子写入保障
  - 防循环触发
  - 过滤规则
  - vault_sync.sh 等待热记忆写完
- 最多等待 MAX_WAIT=10 秒，超时则中止同步
  - 局限性
  - 手动触发
  - 关联

### 2. [[bm25-memory-retrieval-pipeline]] — BM25 记忆检索管道  ·  🧠 1.000  ·  📊 3 次
- BM25 记忆检索管道
  - 结论
  - 检索路径
  - 增量缓存机制
  - 文本预处理（clean_and_tokenize）
  - 参数说明
- 全局检索
- 项目范围限制
- 仅重建缓存
  - 局限性
  - 关联

### 3. [[llm-brain-os-architecture]] — LLM-Brain OS 系统架构  ·  🧠 1.000  ·  📊 3 次
- LLM-Brain OS 系统架构
  - 核心定位
  - 分层架构（6层）
  - 业务流程（全链路）
  - 技术特性
  - 关联

### 4. [[memory-weight-decay]] — 记忆权重衰减公式  ·  🧠 1.000  ·  📊 3 次
- 记忆权重衰减公式
  - 结论
  - 衰减公式
  - 生命周期状态机
  - 原子归档流程（archive_with_backlink_update）
  - 孤儿 .tmp 检测
  - 激活刷新触发时机
  - 自动生成文件豁免
  - 已知局限
  - 关联

### 5. [[obsidian-ux-layer]] — Obsidian UX 层  ·  🧠 1.000  ·  📊 1 次
- Obsidian UX 层
  - 结论
  - 边界
  - 细节
    - 目录与职责
    - frontmatter 新增字段（V2 扩展）
    - obsidian_audit.py 用法
    - CSS snippet 类名
    - 设计约束
  - 关联

### 6. [[context-dehydrator]] — 上下文脱水管道（context_dehydrator）  ·  🧠 1.000  ·  📊 1 次
- 上下文脱水管道（context_dehydrator）
  - 结论
  - 两种模式
    - summary 模式（BM25路径）
    - precise 模式（rg路径）
  - token 预算分配（assemble_final_context）
- token估算：len(text) / 3.5（中英混合）
- 按score降序排列
- 超出预算时：
- - 首文档：截断到剩余配额，追加 [截断提示]，保证有内容返回
- - 后续文档：追加警告行，break
  - 双链保护
  - CLI 用法
- summary模式
- precise模式
  - 关联
