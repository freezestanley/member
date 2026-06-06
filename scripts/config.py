"""
scripts/config.py
=================
脚本层公共常量中心。

所有散落在各脚本中的硬编码路径、枚举、阈值均应从此处导入，
禁止在各脚本文件中重复定义相同的值。

更改策略：
- 路径类常量：直接修改 BRAIN_DIR（其余路径自动推导）
- 阈值 / Top-N 类：修改对应常量，无需改动业务脚本
- 枚举类：统一在此处新增或删除，不在业务代码中散写字面量
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# 1. 根路径
# ---------------------------------------------------------------------------

# Vault 根目录（所有相对路径的起点）
BRAIN_DIR: Path = Path("/Users/za-stanlexu/Documents/member/member")

# ---------------------------------------------------------------------------
# 2. 目录路径
# ---------------------------------------------------------------------------

WIKI_ROOT: Path = BRAIN_DIR / "wiki"
GLOBAL_DIR: Path = WIKI_ROOT / "global_concepts"
PROJECT_DIR: Path = WIKI_ROOT / "project_exclusives"
ARCHIVE_DIR: Path = BRAIN_DIR / "archive"
INBOX_DIR: Path = BRAIN_DIR / "_inbox"

# 生成文件（不参与检索、衰减、审计）
GENERATED_FILES: frozenset = frozenset({"hot.md", "global_hot.md", "index.md", "log.md"})

# ---------------------------------------------------------------------------
# 3. 缓存 / 索引文件
# ---------------------------------------------------------------------------

BM25_CACHE_PATH: Path = INBOX_DIR / ".bm25_cache.pkl"
LOG_PATH: Path = WIKI_ROOT / "log.md"
GLOBAL_HOT_PATH: Path = WIKI_ROOT / "global_hot.md"

# ---------------------------------------------------------------------------
# 4. Hot-Refresh Top-N
# ---------------------------------------------------------------------------

# 全局热记忆榜单条目数（global_hot.md）
GLOBAL_TOP_N: int = 8

# 单项目热记忆榜单条目数（project hot.md）
PROJECT_TOP_M: int = 20

# BM25 检索默认返回条数
BM25_TOP_K: int = 3

# ---------------------------------------------------------------------------
# 5. 权重衰减（memory_manager.py 旧引擎，保持与 weight_config.yml 默认值一致）
# ---------------------------------------------------------------------------

# 旧衰减引擎半衰期（天）
HALF_LIFE_DAYS: int = 30

# 旧衰减引擎归档触发阈值
FORGET_THRESHOLD: float = 0.15

# ---------------------------------------------------------------------------
# 6. Status 枚举
# ---------------------------------------------------------------------------

# BM25 / 衰减 / 审计时跳过的 status 值
SKIP_STATUSES: frozenset = frozenset({"archived", "deprecated", "incomplete"})

# 归档时写入 frontmatter 的状态值
STATUS_ARCHIVED: str = "archived"

# ---------------------------------------------------------------------------
# 7. WeightEngine 配置文件路径
# ---------------------------------------------------------------------------

WEIGHT_CONFIG_PATH: Path = BRAIN_DIR / "config" / "weight_config.yml"
