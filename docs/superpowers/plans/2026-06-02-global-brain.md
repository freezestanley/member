# 全局中央记忆大脑 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `member/member` vault 升级为跨项目全局中央记忆大脑，所有 Claude Code 会话均可通过 `~/.claude/commands/` 中的指令检索、写入、归档知识。

**Architecture:** 全局 CLAUDE.md 注入被动规则（vault 路径 + 分区路由），`~/.claude/commands/` 下三个 command 文件封装主动行为（检索/摄取/归档），`bm25_search.py` 扩展覆盖 `wiki/projects/`，`memory_manager.py` 扩展覆盖 `wiki/projects/`。

**Tech Stack:** Python 3, rank_bm25, jieba, bash, git, Claude Code commands

---

## 文件变更清单

| 操作 | 路径 |
|------|------|
| 修改 | `~/.claude/CLAUDE.md` — 新增全局脑规则节 |
| 新建 | `~/.claude/commands/brain-query.md` |
| 新建 | `~/.claude/commands/brain-ingest.md` |
| 新建 | `~/.claude/commands/brain-consolidate.md` |
| 修改 | `scripts/bm25_search.py` — 检索范围扩展到 `wiki/projects/` |
| 修改 | `scripts/memory_manager.py` — 衰减扫描扩展到 `wiki/projects/` |
| 修改 | `CLAUDE.md`（项目级）— 移除指令定义段，保留结构说明 |
| 新建 | `wiki/projects/` 目录结构 |

---

## Task 1: 创建 `wiki/projects/` 目录结构

**Files:**
- Create: `wiki/projects/.gitkeep`
- Create: `wiki/projects/demo/.gitkeep`
- Create: `wiki/projects/openclaw/.gitkeep`
- Create: `wiki/projects/member/.gitkeep`

- [ ] **Step 1: 创建目录并添加占位文件**

```bash
mkdir -p /Users/za-stanlexu/Documents/member/member/wiki/projects/demo
mkdir -p /Users/za-stanlexu/Documents/member/member/wiki/projects/openclaw
mkdir -p /Users/za-stanlexu/Documents/member/member/wiki/projects/member
touch /Users/za-stanlexu/Documents/member/member/wiki/projects/demo/.gitkeep
touch /Users/za-stanlexu/Documents/member/member/wiki/projects/openclaw/.gitkeep
touch /Users/za-stanlexu/Documents/member/member/wiki/projects/member/.gitkeep
```

- [ ] **Step 2: 验证目录结构**

```bash
find /Users/za-stanlexu/Documents/member/member/wiki/projects -type f
```

期望输出：
```
wiki/projects/demo/.gitkeep
wiki/projects/openclaw/.gitkeep
wiki/projects/member/.gitkeep
```

- [ ] **Step 3: Commit**

```bash
cd /Users/za-stanlexu/Documents/member/member
git add wiki/projects/
git commit -m "feat: add wiki/projects/ directory structure for per-project knowledge"
```

---

## Task 2: 扩展 `bm25_search.py` 覆盖 `wiki/projects/`

**Files:**
- Modify: `scripts/bm25_search.py`

当前 `WIKI_DIR = "./wiki/concepts"` 只扫描单一目录。需改为扫描 `wiki/concepts/` + `wiki/projects/` 全部子目录。

- [ ] **Step 1: 写失败测试（手动验证基准）**

在项目根目录运行当前脚本，确认它不能检索 `wiki/projects/` 下的文件：

```bash
cd /Users/za-stanlexu/Documents/member/member
echo '---
type: concept
project: demo
created_at: 2026-06-02
last_modified: 2026-06-02
last_activated: 2026-06-02
access_count: 1
initial_weight: 1.0
current_weight: 1.0
---
# 测试节点
这是一个 demo 项目专属的测试概念。' > wiki/projects/demo/test-node.md

python3 scripts/bm25_search.py "测试节点"
```

期望输出：空结果（不含 `wiki/projects/demo/test-node.md`），证明当前脚本不覆盖 `projects/`。

- [ ] **Step 2: 修改 `bm25_search.py`**

将文件内容替换为：

```python
import os, re, sys, jieba
from rank_bm25 import BM25Okapi

VAULT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEARCH_DIRS = [
    os.path.join(VAULT_ROOT, "wiki", "concepts"),
    os.path.join(VAULT_ROOT, "wiki", "projects"),
]

def clean_and_tokenize(text):
    text = re.sub(r"---.*?---", "", text, flags=re.DOTALL)
    text = re.sub(r"[\[\]\-\#\*\>\`]", "", text)
    return list(jieba.cut(text.lower()))

if len(sys.argv) >= 2:
    query_str = " ".join(sys.argv[1:])
    doc_paths, corpus = [], []
    for search_dir in SEARCH_DIRS:
        if not os.path.exists(search_dir):
            continue
        for root, _, files in os.walk(search_dir):
            for file in files:
                if file.endswith(".md"):
                    path = os.path.join(root, file)
                    with open(path, "r", encoding="utf-8") as f:
                        doc_paths.append(path)
                        corpus.append(clean_and_tokenize(f.read()))

    if corpus:
        bm25 = BM25Okapi(corpus)
        doc_scores = bm25.get_scores(clean_and_tokenize(query_str))
        final_results = []
        for idx, path in enumerate(doc_paths):
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
            weight_match = re.search(r"current_weight:\s*([\d\.]+)", text)
            weight = float(weight_match.group(1)) if weight_match else 1.0
            final_score = doc_scores[idx] * weight
            if doc_scores[idx] > 0:
                final_results.append((final_score, path))

        final_results.sort(key=lambda x: x[0], reverse=True)
        print(f"=== BM25 复合检索结果 (Top 3) ===")
        for score, path in final_results[:3]:
            print(f" [得分: {round(score, 2)}] 路径: {path}")
```

关键改动：
- `WIKI_DIR` 硬编码相对路径 → `VAULT_ROOT` 动态计算绝对路径（从任意工作目录可调用）
- `SEARCH_DIRS` 列表同时扫描 `wiki/concepts/` 和 `wiki/projects/`

- [ ] **Step 3: 验证扩展后能检索到 `wiki/projects/` 文件**

```bash
cd /Users/za-stanlexu/Documents/member/member
python3 scripts/bm25_search.py "测试节点"
```

期望输出包含：
```
=== BM25 复合检索结果 (Top 3) ===
 [得分: ...] 路径: .../wiki/projects/demo/test-node.md
```

- [ ] **Step 4: 验证从非 vault 目录调用也能工作**

```bash
cd /tmp
python3 /Users/za-stanlexu/Documents/member/member/scripts/bm25_search.py "测试节点"
```

期望：同样输出正确路径（绝对路径），不报 FileNotFoundError。

- [ ] **Step 5: 清理测试文件并 commit**

```bash
cd /Users/za-stanlexu/Documents/member/member
rm wiki/projects/demo/test-node.md
git add scripts/bm25_search.py
git commit -m "feat: extend bm25_search.py to cover wiki/projects/ with absolute path resolution"
```

---

## Task 3: 扩展 `memory_manager.py` 覆盖 `wiki/projects/`

**Files:**
- Modify: `scripts/memory_manager.py`

- [ ] **Step 1: 读取当前完整文件**

```bash
cat /Users/za-stanlexu/Documents/member/member/scripts/memory_manager.py
```

- [ ] **Step 2: 修改 `memory_manager.py`**

将文件头部的目录定义替换，并将扫描逻辑改为多目录：

```python
import os, re, math, shutil
from datetime import datetime

VAULT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCAN_DIRS = [
    os.path.join(VAULT_ROOT, "wiki", "concepts"),
    os.path.join(VAULT_ROOT, "wiki", "projects"),
]
ARCHIVE_DIR = os.path.join(VAULT_ROOT, "wiki", "archive")
HALF_LIFE_DAYS = 30
FORGET_THRESHOLD = 0.15

def calculate_weight(initial_w, last_active_str, access_count):
    last_active = datetime.strptime(last_active_str.strip(), "%Y-%m-%d")
    days_passed = max(0, (datetime.now() - last_active).days)
    decay_factor = math.pow(2, -(days_passed / HALF_LIFE_DAYS))
    frequency_bonus = 1.0 + 0.2 * math.log1p(access_count - 1)
    return round(initial_w * decay_factor * frequency_bonus, 3)

os.makedirs(ARCHIVE_DIR, exist_ok=True)

for scan_dir in SCAN_DIRS:
    if not os.path.exists(scan_dir):
        continue
    for root, _, files in os.walk(scan_dir):
        for file in files:
            if not file.endswith(".md"):
                continue
            path = os.path.join(root, file)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            fm_match = re.match(r"^---(.*?)---", content, re.DOTALL)
            if not fm_match:
                continue
            fm_text = fm_match.group(1)
            try:
                init_w = float(re.search(r"initial_weight:\s*([\d\.]+)", fm_text).group(1))
                last_act = re.search(r"last_activated:\s*([\d\-]+)", fm_text).group(1)
                count = int(re.search(r"access_count:\s*(\d+)", fm_text).group(1))
            except AttributeError:
                continue

            new_w = calculate_weight(init_w, last_act, count)
            updated = re.sub(r"current_weight:\s*[\d\.]+", f"current_weight: {new_w}", content)
            with open(path, "w", encoding="utf-8") as f:
                f.write(updated)

            if new_w < FORGET_THRESHOLD:
                dest = os.path.join(ARCHIVE_DIR, file)
                shutil.move(path, dest)
                print(f"[归档] {path} -> {dest} (weight: {new_w})")
            else:
                print(f"[保留] {file} (weight: {new_w})")
```

关键改动：
- `WIKI_DIR` / `ARCHIVE_DIR` 硬编码相对路径 → 绝对路径
- `SCAN_DIRS` 列表扫描 `wiki/concepts/` + `wiki/projects/`
- 补全 `import shutil`（原脚本依赖 shutil 但可能缺失）

- [ ] **Step 3: 验证脚本无报错**

```bash
cd /tmp
python3 /Users/za-stanlexu/Documents/member/member/scripts/memory_manager.py
```

期望：无 FileNotFoundError，输出 `[保留]` 或 `[归档]` 行（若 wiki 目录为空则无输出）。

- [ ] **Step 4: Commit**

```bash
cd /Users/za-stanlexu/Documents/member/member
git add scripts/memory_manager.py
git commit -m "feat: extend memory_manager.py to scan wiki/projects/ with absolute path resolution"
```

---

## Task 4: 创建 `~/.claude/commands/` 三个 command 文件

**Files:**
- Create: `~/.claude/commands/brain-query.md`
- Create: `~/.claude/commands/brain-ingest.md`
- Create: `~/.claude/commands/brain-consolidate.md`

- [ ] **Step 1: 创建 commands 目录**

```bash
mkdir -p ~/.claude/commands
```

- [ ] **Step 2: 创建 `brain-query.md`**

```bash
cat > ~/.claude/commands/brain-query.md << 'EOF'
# /brain-query

用途：在全局中央知识库中检索，以知识库内容为依据回答。

**执行流程（不可跳过）：**

1. 运行 BM25 检索：
   ```bash
   python3 /Users/za-stanlexu/Documents/member/member/scripts/bm25_search.py "$ARGUMENTS"
   ```

2. 读取输出中的 Top 3 文件路径。

3. 用 Read 工具精准读取这三个文件的完整内容。

4. 以读取到的内容为依据回答用户问题。

5. 刷新每个命中文件的 frontmatter：
   - `last_activated`: 改为今天日期（格式 YYYY-MM-DD）
   - `last_modified`: 改为今天日期
   - `access_count`: 原值 +1

**禁令：**
- 禁止绕过 BM25 直接 Grep 全局扫描 vault
- 禁止在未读 Top 3 文件内容前回答
- 禁止检索结果为空时仍声称找到了相关知识
EOF
```

- [ ] **Step 3: 创建 `brain-ingest.md`**

```bash
cat > ~/.claude/commands/brain-ingest.md << 'EOF'
# /brain-ingest

用途：将当前对话中的重要知识提炼并写入全局中央知识库。

**执行流程（不可跳过）：**

1. 获取当前项目名：
   ```bash
   basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
   ```

2. 判断待写内容类型：
   - 跨项目通用概念、工程规范、方法论 → 写入 `wiki/concepts/`
   - 当前项目专属决策、模块设计、业务逻辑 → 写入 `wiki/projects/<项目名>/`

3. 原子化提炼：一文一议，文件名为名词，控制在约 1000 字内。

4. 每篇笔记必须包含 frontmatter：
   ```markdown
   ---
   type: concept
   created_at: YYYY-MM-DD
   last_modified: YYYY-MM-DD
   project: <项目名 或 global>
   code_symbols: []
   initial_weight: 1.0
   current_weight: 1.0
   last_activated: YYYY-MM-DD
   access_count: 1
   ---
   ```

5. 正文中相关概念使用 `[[概念名]]` 双向链接。

6. 同步到 git：
   ```bash
   bash /Users/za-stanlexu/Documents/member/member/scripts/vault_sync.sh
   ```

**禁令：**
- 禁止把项目专属知识写入 `wiki/concepts/`
- 禁止多主题合并写入同一文件
- 禁止直接覆盖 `_inbox/` 中的原始文件
EOF
```

- [ ] **Step 4: 创建 `brain-consolidate.md`**

```bash
cat > ~/.claude/commands/brain-consolidate.md << 'EOF'
# /brain-consolidate

用途：执行记忆衰减计算，将低权重笔记归档到 `wiki/archive/`。

**执行流程（不可跳过）：**

1. 运行衰减脚本：
   ```bash
   python3 /Users/za-stanlexu/Documents/member/member/scripts/memory_manager.py
   ```

2. 读取脚本输出。

3. 向用户汇报：
   - 哪些笔记被归档（路径 + 最终权重）
   - 哪些笔记被保留（数量汇总即可，不逐条列出）
EOF
```

- [ ] **Step 5: 验证三个文件存在**

```bash
ls ~/.claude/commands/
```

期望输出：
```
brain-consolidate.md
brain-ingest.md
brain-query.md
```

- [ ] **Step 6: 在 vault 内 commit（记录 commands 创建）**

```bash
cd /Users/za-stanlexu/Documents/member/member
git add -A
git commit -m "feat: add ~/.claude/commands/ brain-query, brain-ingest, brain-consolidate"
```

---

## Task 5: 更新 `~/.claude/CLAUDE.md` 新增全局脑规则节

**Files:**
- Modify: `~/.claude/CLAUDE.md` — 在文件末尾追加新节

- [ ] **Step 1: 追加全局中央记忆大脑节**

在 `~/.claude/CLAUDE.md` 文件末尾追加以下内容：

```markdown

<!-- global brain start -->
## 全局中央记忆大脑

**Vault 路径**：`/Users/za-stanlexu/Documents/member/member`

### 分区路由规则
- 跨项目通用概念、工程规范、通用方法论 → `wiki/concepts/`
- 当前项目专属决策、模块设计、业务逻辑 → `wiki/projects/<当前项目名>/`

### 主动行为触发时机
- 完成一个功能模块或重要技术决策后 → 执行 `/brain-ingest`
- 遇到历史决策、跨项目规范、需要参考旧结论时 → 执行 `/brain-query <关键词>`
- 定期（每周或知识库明显膨胀时）→ 执行 `/brain-consolidate`

### 禁令
- 禁止把项目专属知识写入 `wiki/concepts/`（原因：污染全局共享层）
- 禁止绕过 BM25 直接 Grep 全局扫描 vault（原因：破坏权重排序机制）
- 禁止在未读 Top 3 检索结果前回答 `/brain-query`（原因：答案必须有知识库依据）
<!-- global brain end -->
```

- [ ] **Step 2: 验证追加成功**

```bash
tail -25 ~/.claude/CLAUDE.md
```

期望：输出包含 `<!-- global brain start -->` 到 `<!-- global brain end -->` 的完整节。

---

## Task 6: 清理项目级 `CLAUDE.md` 中的重复指令定义

**Files:**
- Modify: `CLAUDE.md`（`/Users/za-stanlexu/Documents/member/member/CLAUDE.md`）

当前项目级 CLAUDE.md 的 `## 5. 系统指令` 节定义了 `/brain-query`、`/brain-ingest`、`/wiki-consolidate` 的执行逻辑。这些现在已迁移到 `~/.claude/commands/`，项目级 CLAUDE.md 只需保留 vault 结构说明。

- [ ] **Step 1: 确认需删除的段落范围**

读取 `CLAUDE.md`，定位 `## 5. 系统指令` 节（约第 81-127 行），以及 `## 6. 执行边界` 节。

- [ ] **Step 2: 将 `## 5. 系统指令` 替换为简短引用说明**

将 `## 5. 系统指令` 节内容替换为：

```markdown
## 5. 系统指令

指令定义已迁移至 `~/.claude/commands/`，全局生效：
- `/brain-query <检索词>` — BM25 检索中央知识库
- `/brain-ingest` — 提炼当前对话知识写入 vault
- `/brain-consolidate` — 执行记忆衰减与归档

执行细节见 `~/.claude/commands/brain-*.md`。
```

- [ ] **Step 3: Commit**

```bash
cd /Users/za-stanlexu/Documents/member/member
git add CLAUDE.md
git commit -m "refactor: move command definitions to ~/.claude/commands/, keep vault structure in CLAUDE.md"
```

---

## Task 7: 端到端验证

- [ ] **Step 1: 切换到另一个项目目录，验证 commands 全局可用**

```bash
cd /Users/za-stanlexu/Documents/demo 2>/dev/null || cd /tmp
# 在 Claude Code 中输入：
# /brain-query 测试
```

期望：Claude 执行 BM25 检索，返回 vault 中的结果（或"无结果"，不报路径错误）。

- [ ] **Step 2: 验证 `/brain-ingest` 写入正确分区**

在某个项目目录下执行 `/brain-ingest`，告知 Claude 当前有一条项目专属决策需要记录。

验证写入位置：
```bash
ls /Users/za-stanlexu/Documents/member/member/wiki/projects/<项目名>/
```

期望：新文件出现在 `wiki/projects/<项目名>/` 而不是 `wiki/concepts/`。

- [ ] **Step 3: 验证 `/brain-consolidate` 可从任意目录运行**

```bash
cd /tmp
python3 /Users/za-stanlexu/Documents/member/member/scripts/memory_manager.py
```

期望：无 FileNotFoundError，正常输出保留/归档报告。

- [ ] **Step 4: 最终 commit（vault sync）**

```bash
cd /Users/za-stanlexu/Documents/member/member
bash scripts/vault_sync.sh
```
