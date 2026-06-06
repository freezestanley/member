# WeightEngine v2.2 实施级设计规范

**日期**：2026-06-06
**版本**：v2.2（implementation-ready）
**状态**：待实现
**实施策略**：先完成 Phase 1，Phase 2 作为独立后续任务

---

## 1. 结论

采用 "统一权重引擎 + 统一激活写入 + 安全迁移 + 显式归档复活" 的方案。

Phase 1 只改活跃区生命周期：

- 新增 `scripts/weight_engine.py`
- 新增 `scripts/frontmatter_utils.py`
- 新增 `scripts/activation_writer.py`
- 新增 `config/weight_config.yml`
- 修改 `scripts/memory_manager.py`
- 修改四个 `skills/brain-*.md` 的回写步骤
- 保留 `scripts/bm25_search.py` 查询只读行为

Phase 2 才引入 archive 召回与显式复活：

- `bm25_search.py --include-archive` 只读召回归档笔记
- `activation_writer.py --revive` 显式移动归档笔记
- 默认检索不扫描 archive
- BM25 检索过程中永远不自动移动文件

本版本可实施标准：

- 每个新增模块有明确 API、CLI、输入输出、错误码
- 每个旧模块有明确改动范围
- 每个行为有测试落点
- 第一轮迁移不会立即批量归档旧笔记
- 激活会同步更新 `current_weight`，避免 hot memory 只刷新旧权重

---

## 2. 当前代码事实

| 文件 | 当前事实 | v2.2 处理 |
|------|----------|-----------|
| `scripts/memory_manager.py` | `calculate_weight(initial_w, last_active_str, access_count)` 是三参数 v1 公式 | 保留，不改签名；新增 v2 helper |
| `scripts/memory_manager.py` | `scan_and_clean()` 直接写 frontmatter，并低于阈值立即归档 | 改为 v2 计算；新增迁移宽限，首次迁移不归档 |
| `scripts/bm25_search.py` | 只扫 `wiki/global_concepts` 和 `wiki/project_exclusives` | Phase 1 不改 archive；Phase 2 增加显式参数 |
| `scripts/bm25_search.py` | cache 写入无锁，固定 `CACHE_PATH` | Phase 2 再做 cache 参数化和锁 |
| `skills/brain-*.md` | 手写 `last_activated`、`last_modified`、`access_count + 1` | 改为调用 `activation_writer.py` |
| `scripts/rg_body_search.py` | 剥离 frontmatter 后按正文和 alias 正则命中，不过滤 `status` | Phase 1 由 `activation_writer.py` 在写入前拒绝非 active 笔记 |
| `hot_refresh.py` | 读取 `current_weight` 和 `access_count` 排序 | 保持不改；激活写入同步更新 `current_weight` |
| `requirements.txt` | 未包含 YAML 依赖 | 新增 `PyYAML` |

---

## 3. 非目标

Phase 1 不做以下事情：

- 不改变 `bm25_search.py` 默认输出格式
- 不让 BM25 自动复活归档笔记
- 不修改 `hot_refresh.py` 的排序逻辑
- 不删除 `access_count`
- 不要求旧笔记权重与 v1 数学等价
- 不引入数据库或后台服务

---

## 4. 数据模型

### 4.1 Frontmatter 字段

新增字段：

```yaml
weight_schema_version: 2
category: general
importance: 1
ewma_access: 0.0
last_boost: 1.0
last_boosted_at: ""
last_weight_migrated_at: ""
```

保留字段：

```yaml
initial_weight: 1.0
current_weight: 1.0
last_activated: YYYY-MM-DD
last_modified: YYYY-MM-DD
access_count: 1
status: active
superseded_by: ""
```

字段语义：

| 字段 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `weight_schema_version` | int | `2` | 标记是否已迁移到 v2 |
| `category` | str | `general` | 查半衰期表，未知类别 fallback 到 `general` |
| `importance` | int | `1` | 范围 `1..5`，1 为中立 |
| `ewma_access` | float | `0.0` | 近期访问事件率，不是累计次数 |
| `last_boost` | float | `1.0` | 最近一次情境 boost |
| `last_boosted_at` | date string | `""` | boost 写入日期；空值表示无有效 boost |
| `last_weight_migrated_at` | date string | `""` | 首次迁移日期，用于归档宽限 |
| `access_count` | int | `1` | 历史审计字段，不参与 v2 权重公式 |

### 4.2 迁移规则

旧笔记首次被 `scan_and_clean()` 扫描时：

```python
was_migrated = fm.get("weight_schema_version") != "2"

updates = {
    "weight_schema_version": "2",
    "category": fm.get("category", "general"),
    "importance": str(clamp_int(fm.get("importance", "1"), 1, 5)),
    "ewma_access": str(init_ewma_from_access_count(access_count, config)),
    "last_boost": str(clamp_float(fm.get("last_boost", "1.0"), 1.0, config["boost_values"]["high"])),
    "last_boosted_at": fm.get("last_boosted_at", ""),
    "last_weight_migrated_at": today.isoformat(),
}
```

迁移 EWMA 初始化：

```python
def init_ewma_from_access_count(access_count: int, config: dict) -> float:
    historical_signal = max(0.0, float(access_count) - 1.0)
    return round(min(config["ewma_migration_cap"], historical_signal), 3)
```

迁移宽限规则：

- 如果本次扫描刚把旧笔记迁移为 v2，即 `was_migrated is True`，本次只写字段和 `current_weight`，不执行归档。
- 下一次 `scan_and_clean()` 扫描时，若 v2 权重仍低于阈值，才允许归档。
- 这样避免第一次上线 v2 时因为公式变化批量移动旧笔记。

schema 完整性规则：

- 任何代码路径只要写入 `weight_schema_version: 2`，必须同时保证本节全部 v2 字段存在并合法。
- `scan_and_clean()` 使用 `migrate_weight_fields()` 完成该规则。
- `activation_writer.activate_note()` 必须复用 `migrate_weight_fields()`，或在写入前执行等价的完整字段补齐；禁止只写 `weight_schema_version: 2` 而缺失 `category`、`importance`、`last_weight_migrated_at` 等字段。
- 字段补齐、EWMA 更新、boost 更新、`current_weight` 更新必须在同一次原子写入内完成。

---

## 5. 权重公式

### 5.1 输入

```python
@dataclass(frozen=True)
class NoteMetadata:
    initial_weight: float
    category: str
    importance: int
    days_idle: int
    ewma_access: float
    last_boost: float
    boost_age_days: int | None
```

### 5.2 公式

```python
effective_hl = category_half_life * (1 + (importance - 1) * importance_k)
decay = 2 ** (-days_idle / effective_hl)

freq_bonus = min(
    1.0 + freq_k * math.log1p(max(0.0, ewma_access)),
    freq_bonus_max,
)

if boost_age_days is None or boost_age_days > boost_ttl_days:
    effective_boost = 1.0
else:
    effective_boost = clamp(last_boost, 1.0, boost_values["high"])

weight = round(
    clamp(initial_weight * decay * freq_bonus * effective_boost, weight_min, weight_max),
    3,
)
```

### 5.3 默认配置

`config/weight_config.yml`：

```yaml
category_half_life:
  strategy: 90
  fact: 60
  decision: 75
  log: 7
  spec: 120
  general: 30

importance_k: 0.6

freq_k: 0.15
freq_bonus_max: 1.6
ewma_half_life_days: 14
ewma_max: 20.0
ewma_migration_cap: 5.0

boost_ttl_days: 7
boost_keywords:
  high: ["重要", "紧急", "开会", "决策", "上线"]
  medium: ["参考", "复习", "回顾"]
boost_values:
  high: 1.4
  medium: 1.2
  default: 1.0

weight_min: 0.01
weight_max: 5.0
forget_threshold: 0.15
revive_weight_margin: 0.05
```

`requirements.txt` 必须新增：

```text
PyYAML
```

配置加载规则：

- `load_config(path: str | None = None) -> dict`
- `path is None` 时读取 `config/weight_config.yml`
- 内置 `DEFAULT_CONFIG`，文件缺字段时按默认值补齐
- 配置值非法时抛 `ValueError`，CLI 捕获后以 exit code `2` 退出

---

## 6. 新增模块合同

### 6.1 `scripts/frontmatter_utils.py`

职责：统一 frontmatter 解析、字段 upsert、原子写入，避免多个脚本重复写正则。

必须提供：

```python
FRONTMATTER_RE = re.compile(r"^(---\s*\n)(.*?)(\n---\s*\n)", re.DOTALL)

def split_frontmatter(content: str) -> tuple[str, str, str]:
    """
    返回 (prefix, fm_text, suffix)。
    prefix 包含 opening delimiter，例如 "---\n"。
    fm_text 不包含 opening/closing delimiter。
    suffix 从 closing delimiter 开始，例如 "\n---\n# Title\n..."。
    无 frontmatter 时 raise ValueError。
    """

def parse_frontmatter_text(fm_text: str) -> dict[str, str]:
    """
    解析简单 key: value 行。
    保留原始字符串值；复杂 YAML 不在这里展开。
    """

def upsert_frontmatter_fields(content: str, updates: dict[str, str]) -> str:
    """
    已有 key 替换整行；缺失 key 追加到 fm_text 末尾。
    最终用 prefix + new_fm_text + suffix 重组。
    不改变正文。
    """

def atomic_write_text(path: str, content: str, lock_path: str, timeout_seconds: float = 10.0) -> None:
    """
    fcntl.flock 独占锁 + path.tmp + os.replace。
    写入失败时删除 tmp。
    """
```

设计约束：

- 不用 PyYAML 解析笔记 frontmatter，只解析简单标量字段。
- 保留 `aliases: []`、`code_symbols: []` 等复杂字段原文，不主动修改。
- `upsert_frontmatter_fields()` 只处理本方案字段。
- lock 文件可保留在文件旁边，不参与 markdown 扫描。

### 6.2 `scripts/weight_engine.py`

必须提供：

```python
DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config" / "weight_config.yml"

@dataclass(frozen=True)
class NoteMetadata:
    initial_weight: float = 1.0
    category: str = "general"
    importance: int = 1
    days_idle: int = 0
    ewma_access: float = 0.0
    last_boost: float = 1.0
    boost_age_days: int | None = None

def load_config(config_path: str | None = None) -> dict:
    ...

def days_since(date_str: str, today: date) -> int:
    ...

def build_metadata(fm: dict[str, str], today: date, config: dict) -> NoteMetadata:
    ...

class WeightEngine:
    def __init__(self, config: dict):
        ...

    def compute(self, meta: NoteMetadata) -> float:
        ...
```

错误处理：

- 日期缺失或非法时，`days_since()` 返回 `0`，不让单篇坏数据中断全库扫描。
- 数字字段非法时使用默认值并 clamp。
- `category` 未配置时 fallback 到 `general`。

### 6.3 `scripts/activation_writer.py`

Python API：

```python
def infer_boost(context: str, config: dict, manual_boost: float | None = None) -> float:
    ...

def update_ewma(prev_ewma: float, days_since_activation: int, config: dict) -> float:
    decayed = prev_ewma * 2 ** (-days_since_activation / config["ewma_half_life_days"])
    return round(min(config["ewma_max"], decayed + 1.0), 3)

def activate_note(
    note_path: str,
    config: dict,
    query_context: str = "",
    manual_boost: float | None = None,
    today: date | None = None,
) -> dict:
    ...
```

`activate_note()` 必须在一次原子写入内更新：

```yaml
weight_schema_version: 2
category: <existing_or_general>
importance: <existing_or_1>
last_weight_migrated_at: <existing_or_today>
last_activated: <today>
last_modified: <today>
access_count: <old + 1>
ewma_access: <updated>
last_boost: <inferred_or_manual>
last_boosted_at: <today if boost > 1.0 else "">
current_weight: <WeightEngine.compute(...) using updated fields>
```

激活必须同步更新 `current_weight`。原因：`hot_watcher.sh` 会在 frontmatter 改动后触发 `hot_refresh.py`，而 `hot_refresh.py` 只读取 `current_weight` 和 `access_count`。如果激活不更新 `current_weight`，v2 的 EWMA/boost 在热榜里不会即时体现。

CLI：

```bash
python3 scripts/activation_writer.py \
  --path "/abs/path/wiki/project_exclusives/member/foo.md" \
  --context "查询词" \
  [--boost 1.4] \
  [--config config/weight_config.yml] \
  [--today 2026-06-06]
```

成功输出 JSON 到 stdout：

```json
{
  "ok": true,
  "path": "/abs/path/wiki/project_exclusives/member/foo.md",
  "access_count": 2,
  "ewma_access": 1.0,
  "last_boost": 1.0,
  "current_weight": 1.104
}
```

错误码：

| code | 含义 |
|------|------|
| `0` | 成功 |
| `2` | 参数或配置非法 |
| `3` | 文件不存在或不在允许范围 |
| `4` | frontmatter 缺失 |
| `5` | 获取锁超时 |
| `6` | 写入失败 |

路径边界：

- Phase 1 的 `activate_note()` 只允许 `wiki/global_concepts/` 和 `wiki/project_exclusives/` 下的 `.md` 文件。
- Phase 1 遇到 `archive/` 路径必须返回 exit code `3`，不能把归档笔记当活跃笔记直接激活。
- Phase 2 只有 `activation_writer.py --revive` 可以接收 `archive/` 路径。
- `hot.md`、`global_hot.md`、`index.md`、`log.md` 必须拒绝激活。
- 路径校验必须使用 `Path(note_path).resolve()` 的 canonical path；resolved path 必须能 `relative_to()` `wiki/global_concepts` 或 `wiki/project_exclusives`。
- 任何 symlink、`..`、相对路径绕过后若 resolved path 不在允许目录内，必须返回 exit code `3`。

状态边界：

- `activate_note()` 必须先解析 frontmatter 状态。
- 判断状态前必须执行归一化：strip 空白，去除首尾单/双引号，去除行内注释后的尾部空白。
- `status` 缺失时按 `active` 处理，并在完整 schema 补齐时写入 `status: active`。
- `status` 为 `archived`、`deprecated`、`incomplete` 时必须拒绝写入，返回 exit code `3`。
- 这样即使 `rg_body_search.py` 命中过期或未完成文件，skill 也不会把它重新激活。

---

## 7. `memory_manager.py` 改动合同

必须保留：

```python
def calculate_weight(initial_w, last_active_str, access_count):
    """Legacy v1 formula. Do not change signature."""
```

新增：

```python
def calculate_weight_v2(fm: dict[str, str], today: date, config: dict) -> float:
    meta = build_metadata(fm, today, config)
    return WeightEngine(config).compute(meta)

def migrate_weight_fields(fm: dict[str, str], today: date, config: dict) -> tuple[dict[str, str], bool]:
    """
    返回 (updates, was_migrated)。
    """
```

`scan_and_clean()` 改为：

```python
def scan_and_clean(
    config_path: str | None = None,
    today: date | None = None,
    dry_run: bool = False,
) -> dict:
    config = load_config(config_path)
    today = today or date.today()
    ...
```

处理顺序：

1. 跳过 `_GENERATED_FILES`
2. 检测孤儿 `.tmp`
3. 无 frontmatter 时 `_build_frontmatter()`
4. `_ensure_status_fields()`
5. `parse_frontmatter_text()`
6. `migrate_weight_fields()`
7. `calculate_weight_v2()`
8. upsert 迁移字段和 `current_weight`
9. 如果 `was_migrated`，本次不归档
10. 如果不是迁移且 `current_weight < forget_threshold`，调用 `archive_with_backlink_update()`
11. 否则原子写回 frontmatter

返回摘要：

```python
{
    "scanned": 0,
    "migrated": 0,
    "updated": 0,
    "archived": 0,
    "archive_conflicts": 0,
    "archive_candidates_after_grace": 0,
    "skipped": 0,
    "incomplete": 0,
}
```

摘要语义：

- `archived` 表示本轮如果不是 dry-run 会立即归档的已迁移笔记数量。
- `archive_candidates_after_grace` 表示首次迁移后权重低于阈值、但本轮受迁移宽限保护的候选数量。
- `dry_run=True` 时只计算摘要和将要写入的字段，不写文件、不归档、不刷新索引。

CLI 合同：

```python
def _cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--config")
    parser.add_argument("--today")
    args = parser.parse_args(argv)

    summary = scan_and_clean(
        config_path=args.config,
        today=parse_today(args.today),
        dry_run=args.dry_run,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    if not args.dry_run:
        render_global_indices()
    return 0
```

CLI 约束：

- `parse_today(None)` 返回 `None`，由 `scan_and_clean()` 使用 `date.today()`。
- `--today` 使用 `YYYY-MM-DD`，非法日期返回 exit code `2`。
- `--config` 指向不存在或非法 YAML 时返回 exit code `2`。
- `--dry-run` 不得调用 `render_global_indices()`，不得写 `wiki/index.md`。
- 非 dry-run 保持现有主流程语义：扫描完成后刷新 `wiki/index.md`。
- `__main__` 只能调用 `_cli()`，禁止继续无条件执行 `scan_and_clean(); render_global_indices()`。

归档保护：

- `status` 为 `deprecated` 或 `incomplete` 的笔记不参与权重计算，不移动。
- 刚迁移的笔记不归档。
- `initial_weight` 非法时按 `1.0`。
- `last_activated` 非法时按 today 计算，即 `days_idle = 0`。

`archive_with_backlink_update()` 安全合同：

- 归档目标路径必须先按 `archive/<原 wiki 相对路径>` 计算。
- 如果目标已存在，必须在修改源文件 frontmatter 之前 fail-fast。
- fail-fast 行为：抛 `FileExistsError` 或返回显式 conflict 结果；不得覆盖 archive 内已有文件。
- `scan_and_clean()` 捕获归档冲突后，源文件必须保持 `status: active` 和原路径不变，摘要 `archive_conflicts += 1`，`archived` 不增加。
- 只有确认目标不存在并成功获得写锁后，才允许把源文件 `status` 写为 `archived` 并移动文件。
- 移动文件使用 `os.replace()` 只允许在已确认无目标冲突时执行；不得用可能静默覆盖的无检查路径。

首次迁移运行手册：

1. 先执行 dry-run：

   ```bash
   python3 scripts/memory_manager.py --dry-run
   ```

2. 检查输出摘要，确认 `migrated`、`archived`、`archive_candidates_after_grace` 数量符合预期；首次迁移产生的低权重候选必须进入 `archive_candidates_after_grace`，不能计入 `archived`。
3. 暂停 `hot_watcher.sh` 或确保 watcher 未运行，避免批量 frontmatter 迁移触发多次 `hot_refresh.py` 和 BM25 cache 重建。
4. 执行实际迁移：

   ```bash
   python3 scripts/memory_manager.py
   ```

5. 迁移完成后手动刷新一次全局和当前项目热榜，并重建一次 BM25 cache：

   ```bash
   python3 scripts/hot_refresh.py --global
   for d in wiki/project_exclusives/*; do
     [ -d "$d" ] || continue
     python3 scripts/hot_refresh.py --project "$(basename "$d")"
   done
   python3 scripts/bm25_search.py --rebuild-cache
   ```

   当前仓库至少存在 `member` 和 `test` 两个项目目录；如果只想迁移当前项目，必须在执行前明确缩小 `scan_and_clean()` 的扫描范围，不能只刷新 `member` 却扫描全库。

6. 再恢复 watcher。

`_build_frontmatter()` 新增字段：

```yaml
weight_schema_version: 2
category: general
importance: 1
ewma_access: 0.0
last_boost: 1.0
last_boosted_at: ""
last_weight_migrated_at: ""
```

---

## 8. Skill 改动合同

四个文件：

- `skills/brain-query.md`
- `skills/brain-query-rg.md`
- `skills/brain-search.md`
- `skills/brain-search-rg.md`

把手动回写步骤替换为：

```bash
python3 /Users/za-stanlexu/Documents/member/member/scripts/activation_writer.py \
  --path "<命中文件绝对路径>" \
  --context "<原始查询词>"
```

如果查询语境明确包含高优先级意图，可传：

```bash
--boost 1.4
```

skill 输出模板中的回写结果改为：

```text
回写结果：<已更新 | 部分失败 | 未更新>
激活摘要：<current_weight=N, ewma_access=N, boost=N>
```

禁止：

- skill 继续手动编辑 `last_activated`
- skill 继续手动 `access_count + 1`
- skill 手动写 `current_weight`
- skill 手动写 `hot.md` 或 `global_hot.md`
- skill 示例命令中继续使用 Unicode 弯引号 `U+201C/U+201D`

命令规范：

- 所有 shell 示例必须使用 ASCII 双引号 `"`。
- 当前 skill 中已有的非 ASCII 弯引号包裹查询词写法，必须顺手改为 `"<查询词>"`。
- 路径参数必须使用绝对路径；不得传 BM25 输出的相对路径给 `activation_writer.py`。

---

## 9. Phase 2 Archive 合同

Phase 2 不允许改 Phase 1 默认行为。

### 9.1 BM25 只读归档召回

新增参数：

```bash
python3 scripts/bm25_search.py "<query>" --include-archive
```

要求：

- 默认不扫描 archive
- `--include-archive` 才扫描 archive
- archive 命中输出必须包含 `[archived]`
- 不移动文件
- 不更新 frontmatter
- 不调用 `activation_writer.py`

文本输出示例：

```text
📄 [加权得分: 1.23] [archived] 相对物理路径: archive/project_exclusives/member/foo.md
```

### 9.2 显式复活

CLI：

```bash
python3 scripts/activation_writer.py --revive \
  --path "/abs/path/archive/project_exclusives/member/foo.md" \
  --context "查询词"
```

复活流程：

1. 校验路径在 `archive/` 下
2. 计算镜像目标路径
3. 目标存在时生成 `_revived_YYYYMMDD_HHMMSS` 后缀
4. 源文件加锁
5. 更新 `status: active`
6. 设置 `current_weight = forget_threshold + revive_weight_margin`
7. `os.replace()` 或 `shutil.move()` 到目标路径
8. 对目标调用 `activate_note()`
9. 删除 `_inbox/.bm25_cache.pkl` 和 `_inbox/.bm25_cache_with_archive.pkl`
10. 输出 JSON，包含 `old_path`、`new_path`、`current_weight`

---

## 10. 测试计划

### 10.1 新增 `tests/test_weight_engine.py`

必须覆盖：

- `importance=1` 时 half-life 不加成
- `importance=5` 时 half-life 为 `hl * 3.4`
- `ewma_access=0.0` 时 frequency bonus 为 `1.0`
- `ewma_access` 很大时 frequency bonus 不超过 `freq_bonus_max`
- boost 为空日期时不生效
- boost 超过 TTL 时不生效
- 非法数字字段 fallback 到默认值
- 未知 category fallback 到 `general`

### 10.2 新增 `tests/test_activation_writer.py`

必须覆盖：

- 激活后 `access_count + 1`
- 激活后 `ewma_access` 增加
- 激活后 `current_weight` 同步更新
- 对旧笔记激活会一次性补齐完整 v2 schema，不产生只有 `weight_schema_version: 2` 的半迁移状态
- `activate_note()` 使用 canonical path 校验，拒绝 symlink 或 `..` 逃逸到活跃区外的路径
- 同日多次激活 EWMA 递增
- 间隔 `ewma_half_life_days` 后旧 EWMA 约减半再加 1
- `manual_boost=1.4` 写入 `last_boost` 和 `last_boosted_at`
- `status: deprecated`、`status: incomplete`、`status: archived` 均拒绝激活，包含带引号和行内注释的 status 值
- frontmatter 缺失返回错误
- 原子写产生的 `.tmp` 不残留

### 10.3 修改 `tests/test_brain_scripts.py`

保留现有 v1 测试：

- `test_cold_start_access_count_1`
- `test_cold_start_access_count_0_no_crash`
- `test_frequency_bonus_increases_with_access`

新增：

- 旧笔记首次迁移补齐 v2 字段
- 旧笔记首次迁移即使权重低于阈值也不归档
- 已迁移笔记下一次扫描低于阈值才归档
- `_build_frontmatter()` 包含 v2 字段
- `memory_manager.py --dry-run` 不写文件、不移动文件、不调用 `render_global_indices()`
- dry-run 摘要区分本轮归档 `archived` 和迁移宽限候选 `archive_candidates_after_grace`
- `archive_with_backlink_update()` 遇到目标路径已存在时不覆盖、不改源文件 `status`

### 10.4 Phase 2 测试

Phase 2 才新增：

- 默认 BM25 不返回 archive
- `--include-archive` 返回 archive 且标 `[archived]`
- archive 命中不移动文件
- `--project member --include-archive` 不召回其他项目 archive
- `--revive` 目标不存在时镜像还原
- `--revive` 目标存在时生成无碰撞后缀
- 复活后两个 BM25 cache 被删除或重建

---

## 11. 实施任务顺序

### Task 1：配置与依赖

文件：

- 修改 `requirements.txt`
- 新增 `config/weight_config.yml`

验收：

```bash
python3 -c "import yaml; print('yaml-ok')"
```

### Task 2：frontmatter 工具

文件：

- 新增 `scripts/frontmatter_utils.py`
- 新增 `tests/test_frontmatter_utils.py`

验收：

```bash
python3 -m pytest tests/test_frontmatter_utils.py -v
```

### Task 3：权重引擎

文件：

- 新增 `scripts/weight_engine.py`
- 新增 `tests/test_weight_engine.py`

验收：

```bash
python3 -m pytest tests/test_weight_engine.py -v
```

### Task 4：激活写入

文件：

- 新增 `scripts/activation_writer.py`
- 新增 `tests/test_activation_writer.py`

验收：

```bash
python3 -m pytest tests/test_activation_writer.py -v
```

### Task 5：memory_manager 迁移

文件：

- 修改 `scripts/memory_manager.py`
- 修改 `tests/test_brain_scripts.py`

验收：

```bash
python3 -m pytest tests/test_brain_scripts.py -v
python3 scripts/memory_manager.py --dry-run --today 2026-06-06
```

### Task 6：skill 回写替换

文件：

- 修改 `skills/brain-query.md`
- 修改 `skills/brain-query-rg.md`
- 修改 `skills/brain-search.md`
- 修改 `skills/brain-search-rg.md`

验收：

```bash
python3 - <<'PY'
from pathlib import Path

files = [
    Path("skills/brain-query.md"),
    Path("skills/brain-query-rg.md"),
    Path("skills/brain-search.md"),
    Path("skills/brain-search-rg.md"),
]

for path in files:
    text = path.read_text(encoding="utf-8")
    assert "activation_writer.py" in text, f"{path}: missing activation_writer.py"
    assert "last_activated`: 改为今天" not in text, f"{path}: still manually updates last_activated"
    assert "access_count`: 在原值基础上加 1" not in text, f"{path}: still manually increments access_count"
    assert "\u201c" not in text and "\u201d" not in text, f"{path}: contains non-ASCII shell quotes"
print("skill-contract-ok")
PY
rg -n "activation_writer.py" skills/brain-*.md
```

第一条命令必须输出 `skill-contract-ok`；第二条命令应命中四个 skill。

### Task 7：Phase 1 回归

验收：

```bash
python3 -m pytest tests/test_weight_engine.py tests/test_activation_writer.py tests/test_frontmatter_utils.py tests/test_brain_scripts.py -v
python3 scripts/memory_manager.py --dry-run
python3 scripts/bm25_search.py "memory weight" --project member
```

禁止把 `python3 scripts/memory_manager.py` 非 dry-run 放入自动回归验收。该命令会修改真实 vault、刷新索引并可能移动文件，只能按首次迁移运行手册在暂停 watcher 后人工执行。

---

## 12. 完成标准

Phase 1 完成必须同时满足：

- 所有新增测试通过
- 现有 `tests/test_brain_scripts.py` 通过
- `calculate_weight()` 三参数调用仍可用
- 新笔记 frontmatter 包含 v2 字段
- 旧笔记首次扫描只迁移不归档
- `activate_note()` 写入 `weight_schema_version: 2` 时不会留下半迁移 frontmatter
- skill 不再手动回写激活字段
- 激活命中后 `current_weight` 立即变化
- `activate_note()` 拒绝 `archived`、`deprecated`、`incomplete` 笔记
- `activate_note()` 使用 canonical path 防 symlink/`..` 逃逸
- `bm25_search.py` 默认仍只检索活跃区
- Phase 1 的 `activate_note()` 拒绝 archive 路径
- 归档目标同名冲突不会覆盖 archive 文件，也不会把源文件错误标为 archived
- 首次迁移有 dry-run 摘要，且摘要区分本轮归档与迁移宽限候选
- 迁移运行期间 watcher/cache 重建策略明确

Phase 2 不应与 Phase 1 混在同一个提交中实现。

---

## 13. 风险与缓解

| 风险 | 缓解 |
|------|------|
| v2 权重导致热榜重排 | `ewma_migration_cap` 控制迁移冲击；首次迁移不归档 |
| 激活写入失败导致 skill 无法回写 | CLI 返回 JSON + 明确错误码；skill 报告部分失败 |
| YAML 依赖缺失 | `requirements.txt` 新增 `PyYAML`，Task 1 单独验收 |
| frontmatter 复杂 YAML 被误改 | 工具只 upsert 指定字段，复杂字段保留原文 |
| boost 永久污染 | `last_boosted_at` + `boost_ttl_days` |
| 查询误移动归档文件 | Phase 2 规定 BM25 永远只读，复活必须显式 CLI |
| 迁移当天批量 archive | `last_weight_migrated_at` + 首次迁移宽限 |
| 首次迁移触发 watcher/cache 风暴 | dry-run 预检；实际迁移时暂停 watcher；迁移后只手动刷新一次 hot 和 BM25 cache |
| 激活只改 frontmatter 却触发 BM25 cache 重建 | Phase 1 接受该现状；Phase 2 评估正文 hash，frontmatter-only 变化不重建 corpus |
| rg 精确检索命中过期或未完成笔记 | `activation_writer.py` 二次校验 `status`，非 active 一律拒绝写入 |
| archive 目标同名导致覆盖或半归档 | 目标存在时先 fail-fast；源文件 frontmatter 不变；摘要记录 `archive_conflicts` |

---

## 14. 相比上一版 v2.2 的关键优化

| 上一版缺口 | 本版修正 |
|------------|----------|
| 仍偏概念，缺少模块级 API 合同 | 增加 `frontmatter_utils.py`、`weight_engine.py`、`activation_writer.py` 精确函数签名 |
| 激活不更新 `current_weight`，hot_refresh 不能即时体现 v2 权重 | `activate_note()` 必须同步计算并写入 `current_weight` |
| 首次迁移可能因公式变化立即归档旧笔记 | 增加 `last_weight_migrated_at` 和首次迁移不归档规则 |
| CLI 输出和错误处理不明确 | 增加 JSON 输出和 exit code 合同 |
| 测试只列方向，不够可执行 | 拆成具体测试文件和验收命令 |
| frontmatter 写入重复实现风险高 | 新增统一 `frontmatter_utils.py` |
| Phase 1/Phase 2 边界仍可能混淆 | 明确 Phase 2 不得混入 Phase 1 提交 |
| Phase 1 可能误激活 archive 路径 | `activate_note()` 限定只接受 wiki 活跃区路径，archive 只允许 `--revive` |
| 首次迁移会触发 watcher/cache 风暴 | 增加 `--dry-run`、暂停 watcher、迁移后单次刷新 runbook |
| skill 验收 grep 过宽 | 改为 Python 合同检查，避免把 "禁止手动写 hot.md" 等安全规则误判 |
| skill 示例已有中文弯引号 | 要求所有 shell 示例使用 ASCII 引号，并在 Task 6 验收 |
| 激活可能只写 schema version，形成半迁移笔记 | 要求 `activate_note()` 在原子写入前补齐完整 v2 schema |
| memory_manager 缺少真实 CLI 合同 | 增加 `_cli()`、`--dry-run`、`--config`、`--today` 和 dry-run 不刷新索引规则 |
| 归档使用无检查 rename 存在覆盖风险 | 增加归档目标冲突 fail-fast 合同和测试 |
| 迁移 runbook 只刷新 member 项目 | 改为遍历 `wiki/project_exclusives/*`，避免扫描全库后只刷新单项目 |
