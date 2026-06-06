# Obsidian-first Memory Vault Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an Obsidian-first UX layer for the memory vault using Dataview, Templater, Bases, Canvas, and then add an Agent-readable audit layer.

**Architecture:** Keep the existing Python memory engine intact. Add Obsidian-native artifacts in `templates/`, `dashboards/`, `bases/`, and `canvases/`, then add a small script layer that can read these artifacts and reproduce the most important governance queries for Agent use.

**Tech Stack:** Markdown, YAML frontmatter, Obsidian Bases YAML, Obsidian Canvas JSON, Dataview query blocks, Templater syntax, Python `pytest`, PyYAML, standard library JSON/path parsing.

---

## Phase 1: Obsidian UX Layer

### Task 1: Add Obsidian UX Asset Validation Tests

**Files:**
- Create: `tests/test_obsidian_ux_assets.py`
- No implementation files yet.

**Step 1: Write failing tests**

Create `tests/test_obsidian_ux_assets.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parent.parent

TEMPLATES = [
    "templates/concept-global.md",
    "templates/concept-project.md",
    "templates/decision.md",
    "templates/pitfall.md",
    "templates/usage-manual.md",
]

DASHBOARDS = [
    "dashboards/记忆治理总览.md",
    "dashboards/低权重待处理.md",
    "dashboards/最近激活.md",
    "dashboards/缺少 aliases.md",
    "dashboards/项目 member 记忆.md",
    "dashboards/归档候选.md",
    "dashboards/链接治理.md",
]

BASES = [
    "bases/active-memory.base",
    "bases/project-memory.base",
    "bases/archive-candidates.base",
    "bases/recent-activations.base",
    "bases/alias-needed.base",
]

REQUIRED_FRONTMATTER_FIELDS = [
    "type:",
    "created_at:",
    "last_modified:",
    "project:",
    "aliases:",
    "code_symbols:",
    "initial_weight:",
    "current_weight:",
    "last_activated:",
    "access_count:",
    "status:",
    "superseded_by:",
    "weight_schema_version:",
    "category:",
    "importance:",
    "ewma_access:",
    "last_boost:",
    "last_boosted_at:",
    "last_weight_migrated_at:",
    "tags:",
    "cssclasses:",
]


def test_templates_exist_and_keep_memory_frontmatter_contract():
    for rel in TEMPLATES:
        path = ROOT / rel
        assert path.exists(), f"missing template: {rel}"
        text = path.read_text(encoding="utf-8")
        assert text.startswith("---\n"), f"{rel} must start with YAML frontmatter"
        for field in REQUIRED_FRONTMATTER_FIELDS:
            assert field in text, f"{rel} missing {field}"
        assert "<% tp.date.now(" in text, f"{rel} should use Templater dates"
        assert "memory/" in text, f"{rel} should include memory tags"


def test_dashboards_exist_and_contain_dataview_blocks():
    for rel in DASHBOARDS:
        path = ROOT / rel
        assert path.exists(), f"missing dashboard: {rel}"
        text = path.read_text(encoding="utf-8")
        assert "```dataview" in text, f"{rel} must contain a Dataview block"
        assert "wiki" in text, f"{rel} should query wiki notes"


def test_bases_are_valid_yaml_with_table_views():
    for rel in BASES:
        path = ROOT / rel
        assert path.exists(), f"missing base: {rel}"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict), f"{rel} must parse as YAML mapping"
        assert "filters" in data, f"{rel} missing filters"
        assert "properties" in data, f"{rel} missing properties"
        assert "views" in data, f"{rel} missing views"
        assert isinstance(data["views"], list) and data["views"], f"{rel} must define views"
        assert data["views"][0]["type"] == "table", f"{rel} first view should be table"


def test_canvas_is_valid_json_and_links_core_memory_files():
    path = ROOT / "canvases/LLM-Brain-OS.canvas"
    assert path.exists(), "missing LLM-Brain-OS.canvas"
    data = json.loads(path.read_text(encoding="utf-8"))
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    assert len(nodes) >= 10
    assert len(edges) >= 8
    files = {node.get("file") for node in nodes if node.get("type") == "file"}
    for expected in [
        "wiki/global_hot.md",
        "wiki/project_exclusives/member/hot.md",
        "wiki/project_exclusives/member/llm-brain-os-architecture.md",
        "dashboards/记忆治理总览.md",
        "docs/memory-repository-technical-solution.md",
        "docs/memory-repository-user-manual.md",
    ]:
        assert expected in files


def test_memory_snippet_exists_without_forcing_appearance_config():
    snippet = ROOT / ".obsidian/snippets/memory-vault.css"
    assert snippet.exists()
    text = snippet.read_text(encoding="utf-8")
    assert ".memory-hot" in text
    assert ".memory-cold" in text
    appearance = ROOT / ".obsidian/appearance.json"
    if appearance.exists():
        appearance_text = appearance.read_text(encoding="utf-8")
        assert "memory-vault" not in appearance_text
```

**Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m pytest tests/test_obsidian_ux_assets.py -v
```

Expected: FAIL because `templates/`, `dashboards/`, `bases/`, `canvases/`, and snippet files do not exist yet.

**Step 3: Commit failing tests**

```bash
git add tests/test_obsidian_ux_assets.py
git commit -m "test: add obsidian ux asset contract"
```

### Task 2: Create Templater Note Templates

**Files:**
- Create: `templates/concept-global.md`
- Create: `templates/concept-project.md`
- Create: `templates/decision.md`
- Create: `templates/pitfall.md`
- Create: `templates/usage-manual.md`
- Test: `tests/test_obsidian_ux_assets.py`

**Step 1: Create `templates/concept-global.md`**

```markdown
---
type: concept
created_at: <% tp.date.now("YYYY-MM-DD") %>
last_modified: <% tp.date.now("YYYY-MM-DD") %>
project: global
aliases: []
code_symbols: []
initial_weight: 1.0
current_weight: 1.0
last_activated: <% tp.date.now("YYYY-MM-DD") %>
access_count: 1
status: active
superseded_by: ""
weight_schema_version: 2
category: general
importance: 1
ewma_access: 0.0
last_boost: 1.0
last_boosted_at: ""
last_weight_migrated_at: <% tp.date.now("YYYY-MM-DD") %>
tags:
  - memory/active
  - type/concept
  - project/global
  - category/general
cssclasses:
  - memory-note
---

# <% tp.file.title %>

## 结论

写一条可跨项目复用的稳定结论。

## 边界

说明适用范围和不适用场景。

## 细节

补充必要约束、示例或代码符号。

## 关联

- [[相关概念]]
```

**Step 2: Create `templates/concept-project.md`**

Use the same structure, with these differences:

```yaml
project: member
tags:
  - memory/active
  - type/concept
  - project/member
  - category/general
```

Body H2 `结论` should say: `写一条只对当前项目成立的稳定结论。`

**Step 3: Create `templates/decision.md`**

Use:

```yaml
type: decision
category: decision
importance: 3
tags:
  - memory/active
  - type/decision
  - project/member
  - category/decision
cssclasses:
  - memory-note
  - memory-decision
```

Body sections:

```markdown
## 决策

## 背景

## 取舍

## 影响

## 关联
```

**Step 4: Create `templates/pitfall.md`**

Use:

```yaml
type: pitfall
category: fact
importance: 2
tags:
  - memory/active
  - type/pitfall
  - project/member
  - category/fact
cssclasses:
  - memory-note
  - memory-pitfall
```

Body sections:

```markdown
## 问题

## 根因

## 解决

## 避免方式

## 关联
```

**Step 5: Create `templates/usage-manual.md`**

Use:

```yaml
type: manual
category: spec
importance: 2
tags:
  - memory/active
  - type/manual
  - project/member
  - category/spec
cssclasses:
  - memory-note
```

Body sections:

```markdown
## 适用对象

## 前置条件

## 操作步骤

## 常见问题

## 关联
```

**Step 6: Run focused tests**

Run:

```bash
python3 -m pytest tests/test_obsidian_ux_assets.py::test_templates_exist_and_keep_memory_frontmatter_contract -v
```

Expected: PASS.

**Step 7: Commit**

```bash
git add templates tests/test_obsidian_ux_assets.py
git commit -m "feat: add obsidian templater memory templates"
```

### Task 3: Create Dataview Governance Dashboards

**Files:**
- Create: `dashboards/记忆治理总览.md`
- Create: `dashboards/低权重待处理.md`
- Create: `dashboards/最近激活.md`
- Create: `dashboards/缺少 aliases.md`
- Create: `dashboards/项目 member 记忆.md`
- Create: `dashboards/归档候选.md`
- Create: `dashboards/链接治理.md`
- Test: `tests/test_obsidian_ux_assets.py`

**Step 1: Create overview dashboard**

`dashboards/记忆治理总览.md`:

````markdown
# 记忆治理总览

## 入口

- [[低权重待处理]]
- [[最近激活]]
- [[缺少 aliases]]
- [[项目 member 记忆]]
- [[归档候选]]
- [[链接治理]]
- [[LLM-Brain-OS.canvas|LLM-Brain OS Canvas]]
- [[global_hot]]
- [[hot]]

## 活跃记忆 Top 20

```dataview
TABLE project, category, current_weight, access_count, last_activated
FROM "wiki"
WHERE status = "active"
SORT current_weight DESC
LIMIT 20
```
````

**Step 2: Create low-weight dashboard**

`dashboards/低权重待处理.md`:

````markdown
# 低权重待处理

```dataview
TABLE project, category, current_weight, last_activated, access_count
FROM "wiki"
WHERE status = "active" AND current_weight < 0.3
SORT current_weight ASC
```
````

**Step 3: Create recent activations dashboard**

`dashboards/最近激活.md`:

````markdown
# 最近激活

```dataview
TABLE project, category, current_weight, access_count
FROM "wiki"
WHERE status = "active" AND last_activated
SORT last_activated DESC
LIMIT 50
```
````

**Step 4: Create alias gap dashboard**

`dashboards/缺少 aliases.md`:

````markdown
# 缺少 aliases

```dataview
TABLE project, category, current_weight, last_modified
FROM "wiki"
WHERE status = "active" AND (aliases = null OR length(aliases) = 0)
SORT last_modified DESC
```
````

**Step 5: Create project memory dashboard**

`dashboards/项目 member 记忆.md`:

````markdown
# 项目 member 记忆

```dataview
TABLE category, current_weight, access_count, last_activated
FROM "wiki/project_exclusives/member"
WHERE status = "active"
SORT current_weight DESC
```
````

**Step 6: Create archive candidate dashboard**

`dashboards/归档候选.md`:

````markdown
# 归档候选

```dataview
TABLE project, category, current_weight, last_activated, access_count
FROM "wiki"
WHERE status = "active" AND current_weight < 0.15
SORT current_weight ASC
```
````

**Step 7: Create link governance dashboard**

`dashboards/链接治理.md`:

````markdown
# 链接治理

## 孤儿候选

```dataview
TABLE project, category, current_weight, length(file.inlinks) AS inlinks, length(file.outlinks) AS outlinks
FROM "wiki"
WHERE status = "active" AND length(file.inlinks) = 0 AND length(file.outlinks) = 0
SORT current_weight DESC
```

## 高权重无出链

```dataview
TABLE project, category, current_weight, length(file.outlinks) AS outlinks
FROM "wiki"
WHERE status = "active" AND current_weight >= 0.8 AND length(file.outlinks) = 0
SORT current_weight DESC
```
````

**Step 8: Run dashboard tests**

Run:

```bash
python3 -m pytest tests/test_obsidian_ux_assets.py::test_dashboards_exist_and_contain_dataview_blocks -v
```

Expected: PASS.

**Step 9: Commit**

```bash
git add dashboards tests/test_obsidian_ux_assets.py
git commit -m "feat: add dataview memory governance dashboards"
```

### Task 4: Create Obsidian Bases Views

**Files:**
- Create: `bases/active-memory.base`
- Create: `bases/project-memory.base`
- Create: `bases/archive-candidates.base`
- Create: `bases/recent-activations.base`
- Create: `bases/alias-needed.base`
- Test: `tests/test_obsidian_ux_assets.py`

**Step 1: Create `bases/active-memory.base`**

```yaml
filters:
  and:
    - 'file.inFolder("wiki")'
    - 'status == "active"'
properties:
  file.name:
    displayName: Note
  project:
    displayName: Project
  category:
    displayName: Category
  current_weight:
    displayName: Weight
  access_count:
    displayName: Access
  last_activated:
    displayName: Last activated
views:
  - type: table
    name: Active memory
    limit: 100
    order:
      - file.name
      - project
      - category
      - current_weight
      - access_count
      - last_activated
```

**Step 2: Create `bases/project-memory.base`**

```yaml
filters:
  and:
    - 'file.inFolder("wiki/project_exclusives/member")'
    - 'status == "active"'
properties:
  file.name:
    displayName: Note
  category:
    displayName: Category
  current_weight:
    displayName: Weight
  access_count:
    displayName: Access
  last_activated:
    displayName: Last activated
views:
  - type: table
    name: Member memory
    limit: 100
    order:
      - file.name
      - category
      - current_weight
      - access_count
      - last_activated
```

**Step 3: Create `bases/archive-candidates.base`**

```yaml
filters:
  and:
    - 'file.inFolder("wiki")'
    - 'status == "active"'
    - 'current_weight < 0.3'
properties:
  file.name:
    displayName: Note
  project:
    displayName: Project
  current_weight:
    displayName: Weight
  last_activated:
    displayName: Last activated
views:
  - type: table
    name: Archive candidates
    limit: 100
    order:
      - file.name
      - project
      - current_weight
      - last_activated
```

**Step 4: Create `bases/recent-activations.base`**

```yaml
filters:
  and:
    - 'file.inFolder("wiki")'
    - 'status == "active"'
properties:
  file.name:
    displayName: Note
  project:
    displayName: Project
  current_weight:
    displayName: Weight
  last_activated:
    displayName: Last activated
views:
  - type: table
    name: Recent activations
    limit: 100
    order:
      - file.name
      - project
      - current_weight
      - last_activated
```

**Step 5: Create `bases/alias-needed.base`**

```yaml
filters:
  and:
    - 'file.inFolder("wiki")'
    - 'status == "active"'
    - 'aliases.isEmpty()'
properties:
  file.name:
    displayName: Note
  project:
    displayName: Project
  aliases:
    displayName: Aliases
  last_modified:
    displayName: Last modified
views:
  - type: table
    name: Alias needed
    limit: 100
    order:
      - file.name
      - project
      - aliases
      - last_modified
```

**Step 6: Run base tests**

Run:

```bash
python3 -m pytest tests/test_obsidian_ux_assets.py::test_bases_are_valid_yaml_with_table_views -v
```

Expected: PASS.

**Step 7: Commit**

```bash
git add bases tests/test_obsidian_ux_assets.py
git commit -m "feat: add obsidian bases for memory views"
```

### Task 5: Create Canvas System Map

**Files:**
- Create: `canvases/LLM-Brain-OS.canvas`
- Test: `tests/test_obsidian_ux_assets.py`

**Step 1: Create canvas JSON**

Create `canvases/LLM-Brain-OS.canvas` with valid JSON:

```json
{
  "nodes": [
    {"id": "dashboard", "type": "file", "file": "dashboards/记忆治理总览.md", "x": 0, "y": 0, "width": 300, "height": 160},
    {"id": "global-hot", "type": "file", "file": "wiki/global_hot.md", "x": 360, "y": -220, "width": 300, "height": 160},
    {"id": "project-hot", "type": "file", "file": "wiki/project_exclusives/member/hot.md", "x": 360, "y": 0, "width": 300, "height": 160},
    {"id": "architecture", "type": "file", "file": "wiki/project_exclusives/member/llm-brain-os-architecture.md", "x": 360, "y": 220, "width": 300, "height": 160},
    {"id": "bm25", "type": "file", "file": "wiki/project_exclusives/member/bm25-memory-retrieval-pipeline.md", "x": 720, "y": -220, "width": 300, "height": 160},
    {"id": "dehydrator", "type": "file", "file": "wiki/project_exclusives/member/context-dehydrator.md", "x": 1080, "y": -220, "width": 300, "height": 160},
    {"id": "weight", "type": "file", "file": "wiki/project_exclusives/member/memory-weight-decay.md", "x": 720, "y": 0, "width": 300, "height": 160},
    {"id": "hot-routing", "type": "file", "file": "wiki/project_exclusives/member/hot-memory-dual-track.md", "x": 1080, "y": 0, "width": 300, "height": 160},
    {"id": "technical-solution", "type": "file", "file": "docs/memory-repository-technical-solution.md", "x": 720, "y": 220, "width": 300, "height": 160},
    {"id": "manual", "type": "file", "file": "docs/memory-repository-user-manual.md", "x": 1080, "y": 220, "width": 300, "height": 160},
    {"id": "templates", "type": "text", "text": "Templater 入库模板\\ntemplates/*.md", "x": -360, "y": -120, "width": 260, "height": 120},
    {"id": "bases", "type": "text", "text": "Obsidian Bases\\nbases/*.base", "x": -360, "y": 80, "width": 260, "height": 120}
  ],
  "edges": [
    {"id": "e1", "fromNode": "templates", "fromSide": "right", "toNode": "dashboard", "toSide": "left"},
    {"id": "e2", "fromNode": "bases", "fromSide": "right", "toNode": "dashboard", "toSide": "left"},
    {"id": "e3", "fromNode": "dashboard", "fromSide": "right", "toNode": "global-hot", "toSide": "left"},
    {"id": "e4", "fromNode": "dashboard", "fromSide": "right", "toNode": "project-hot", "toSide": "left"},
    {"id": "e5", "fromNode": "dashboard", "fromSide": "right", "toNode": "architecture", "toSide": "left"},
    {"id": "e6", "fromNode": "architecture", "fromSide": "right", "toNode": "bm25", "toSide": "left"},
    {"id": "e7", "fromNode": "bm25", "fromSide": "right", "toNode": "dehydrator", "toSide": "left"},
    {"id": "e8", "fromNode": "architecture", "fromSide": "right", "toNode": "weight", "toSide": "left"},
    {"id": "e9", "fromNode": "weight", "fromSide": "right", "toNode": "hot-routing", "toSide": "left"},
    {"id": "e10", "fromNode": "architecture", "fromSide": "right", "toNode": "technical-solution", "toSide": "left"},
    {"id": "e11", "fromNode": "technical-solution", "fromSide": "right", "toNode": "manual", "toSide": "left"}
  ]
}
```

**Step 2: Run canvas test**

Run:

```bash
python3 -m pytest tests/test_obsidian_ux_assets.py::test_canvas_is_valid_json_and_links_core_memory_files -v
```

Expected: PASS.

**Step 3: Commit**

```bash
git add canvases tests/test_obsidian_ux_assets.py
git commit -m "feat: add obsidian canvas system map"
```

### Task 6: Add Optional CSS Snippet

**Files:**
- Create: `.obsidian/snippets/memory-vault.css`
- Test: `tests/test_obsidian_ux_assets.py`

**Step 1: Create snippet**

Create `.obsidian/snippets/memory-vault.css`:

```css
.memory-note {
  --memory-accent: var(--interactive-accent);
}

.memory-hot {
  border-left: 3px solid var(--color-green);
  padding-left: 0.75rem;
}

.memory-cold {
  opacity: 0.78;
}

.memory-decision {
  border-left: 3px solid var(--color-blue);
  padding-left: 0.75rem;
}

.memory-pitfall {
  border-left: 3px solid var(--color-red);
  padding-left: 0.75rem;
}
```

Do not modify `.obsidian/appearance.json`.

**Step 2: Run snippet test**

Run:

```bash
python3 -m pytest tests/test_obsidian_ux_assets.py::test_memory_snippet_exists_without_forcing_appearance_config -v
```

Expected: PASS.

**Step 3: Run all Phase 1 tests**

Run:

```bash
python3 -m pytest tests/test_obsidian_ux_assets.py -v
python3 -m pytest
```

Expected: all tests PASS.

**Step 4: Commit**

```bash
git add .obsidian/snippets/memory-vault.css tests/test_obsidian_ux_assets.py
git commit -m "feat: add optional memory vault obsidian snippet"
```

## Phase 2: Agent-readable Obsidian Structure

### Task 7: Add Obsidian Audit Script Tests

**Files:**
- Create: `tests/test_obsidian_audit.py`
- Create later: `scripts/obsidian_audit.py`

**Step 1: Write failing tests**

Create `tests/test_obsidian_audit.py`:

```python
from __future__ import annotations

from pathlib import Path

import sys

sys.path.insert(0, "scripts")

from obsidian_audit import (  # noqa: E402
    find_alias_gaps,
    find_low_weight_candidates,
    load_canvas_file_nodes,
    parse_note_metadata,
)


def _note(path: Path, frontmatter: str, body: str = "# Note\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{frontmatter}---\n{body}", encoding="utf-8")
    return path


def test_parse_note_metadata_extracts_frontmatter_and_links(tmp_path):
    note = _note(
        tmp_path / "wiki" / "global_concepts" / "a.md",
        "status: active\naliases: [A]\ncurrent_weight: 1.0\n",
        "# A\n参见 [[b]]。\n",
    )

    meta = parse_note_metadata(note, tmp_path)

    assert meta["status"] == "active"
    assert meta["aliases"] == "[A]"
    assert meta["current_weight"] == "1.0"
    assert meta["outlinks"] == ["b"]


def test_find_alias_gaps_only_active_notes_without_aliases(tmp_path):
    _note(tmp_path / "wiki" / "global_concepts" / "missing.md", "status: active\naliases: []\n")
    _note(tmp_path / "wiki" / "global_concepts" / "ok.md", "status: active\naliases: [OK]\n")
    _note(tmp_path / "wiki" / "global_concepts" / "archived.md", "status: archived\naliases: []\n")

    gaps = find_alias_gaps(tmp_path / "wiki")

    assert [item["path"].name for item in gaps] == ["missing.md"]


def test_find_low_weight_candidates_filters_active_notes(tmp_path):
    _note(tmp_path / "wiki" / "global_concepts" / "cold.md", "status: active\ncurrent_weight: 0.12\n")
    _note(tmp_path / "wiki" / "global_concepts" / "warm.md", "status: active\ncurrent_weight: 0.8\n")

    candidates = find_low_weight_candidates(tmp_path / "wiki", threshold=0.3)

    assert [item["path"].name for item in candidates] == ["cold.md"]


def test_load_canvas_file_nodes_reads_canvas_json(tmp_path):
    canvas = tmp_path / "canvases" / "map.canvas"
    canvas.parent.mkdir(parents=True)
    canvas.write_text(
        '{"nodes":[{"id":"a","type":"file","file":"wiki/a.md"},{"id":"b","type":"text","text":"B"}],"edges":[]}',
        encoding="utf-8",
    )

    files = load_canvas_file_nodes(canvas)

    assert files == ["wiki/a.md"]
```

**Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m pytest tests/test_obsidian_audit.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'obsidian_audit'`.

**Step 3: Commit failing tests**

```bash
git add tests/test_obsidian_audit.py
git commit -m "test: add obsidian audit script contract"
```

### Task 8: Implement Obsidian Audit Script

**Files:**
- Create: `scripts/obsidian_audit.py`
- Test: `tests/test_obsidian_audit.py`

**Step 1: Implement script**

Create `scripts/obsidian_audit.py`:

```python
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from frontmatter_utils import parse_frontmatter_text, split_frontmatter


WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:[#|][^\]]*)?\]\]")


def parse_note_metadata(path: Path, root: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    try:
        _, fm_text, suffix = split_frontmatter(text)
        fm = parse_frontmatter_text(fm_text)
        body = suffix.split("---\n", 1)[1] if suffix.startswith("---\n") else suffix
    except ValueError:
        fm = {}
        body = text
    outlinks = [match.strip() for match in WIKILINK_RE.findall(body)]
    fm["path"] = path
    fm["relative_path"] = str(path.relative_to(root))
    fm["outlinks"] = outlinks
    return fm


def _iter_notes(wiki_root: Path):
    for path in wiki_root.rglob("*.md"):
        if path.name in {"hot.md", "global_hot.md", "index.md", "log.md"}:
            continue
        yield path


def _is_active(meta: dict) -> bool:
    return str(meta.get("status", "active")).strip().strip("\"'") == "active"


def _aliases_empty(value) -> bool:
    if value is None:
        return True
    return str(value).strip() in {"", "[]"}


def find_alias_gaps(wiki_root: Path) -> list[dict]:
    root = wiki_root.parent
    results = []
    for path in _iter_notes(wiki_root):
        meta = parse_note_metadata(path, root)
        if _is_active(meta) and _aliases_empty(meta.get("aliases")):
            results.append(meta)
    return sorted(results, key=lambda item: str(item["path"]))


def _float(value, default: float = 1.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def find_low_weight_candidates(wiki_root: Path, threshold: float = 0.3) -> list[dict]:
    root = wiki_root.parent
    results = []
    for path in _iter_notes(wiki_root):
        meta = parse_note_metadata(path, root)
        if _is_active(meta) and _float(meta.get("current_weight")) < threshold:
            results.append(meta)
    return sorted(results, key=lambda item: _float(item.get("current_weight")))


def load_canvas_file_nodes(canvas_path: Path) -> list[str]:
    data = json.loads(canvas_path.read_text(encoding="utf-8"))
    return [
        node["file"]
        for node in data.get("nodes", [])
        if node.get("type") == "file" and node.get("file")
    ]


def _jsonable(items: list[dict]) -> list[dict]:
    output = []
    for item in items:
        copy = dict(item)
        copy["path"] = str(copy["path"])
        output.append(copy)
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wiki-root", default="wiki")
    parser.add_argument("--canvas", default="canvases/LLM-Brain-OS.canvas")
    parser.add_argument("--threshold", type=float, default=0.3)
    args = parser.parse_args(argv)

    wiki_root = Path(args.wiki_root)
    canvas = Path(args.canvas)
    report = {
        "alias_gaps": _jsonable(find_alias_gaps(wiki_root)),
        "low_weight_candidates": _jsonable(find_low_weight_candidates(wiki_root, args.threshold)),
        "canvas_files": load_canvas_file_nodes(canvas) if canvas.exists() else [],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

**Step 2: Run audit tests**

Run:

```bash
python3 -m pytest tests/test_obsidian_audit.py -v
```

Expected: PASS.

**Step 3: Run script smoke test**

Run:

```bash
python3 scripts/obsidian_audit.py --wiki-root wiki --canvas canvases/LLM-Brain-OS.canvas
```

Expected: valid JSON containing `alias_gaps`, `low_weight_candidates`, and `canvas_files`.

**Step 4: Commit**

```bash
git add scripts/obsidian_audit.py tests/test_obsidian_audit.py
git commit -m "feat: add obsidian-native audit helper"
```

### Task 9: Add Agent-facing Obsidian Governance Manual

**Files:**
- Create: `docs/obsidian-first-memory-vault-manual.md`
- Test: existing test suite only.

**Step 1: Create manual**

Create `docs/obsidian-first-memory-vault-manual.md`:

```markdown
# Obsidian-first 记忆仓库使用说明

## 入口

- `dashboards/记忆治理总览.md`
- `canvases/LLM-Brain-OS.canvas`
- `bases/active-memory.base`
- `templates/concept-project.md`

## 人工治理流程

1. 打开 `dashboards/记忆治理总览.md`。
2. 查看低权重、缺 aliases、最近激活和链接治理视图。
3. 使用 `templates/` 创建新笔记。
4. 使用 `bases/` 做筛选和排序。
5. 使用 `canvases/LLM-Brain-OS.canvas` 理解系统结构。

## Agent 治理流程

1. 读取 `canvases/LLM-Brain-OS.canvas`。
2. 读取 `dashboards/记忆治理总览.md`。
3. 执行 `python3 scripts/obsidian_audit.py --wiki-root wiki --canvas canvases/LLM-Brain-OS.canvas`。
4. 根据 JSON 报告维护 aliases、链接和低权重笔记。

## 注意事项

- 不手动编辑 `global_hot.md` 或项目 `hot.md`。
- 不强制启用 CSS snippet。
- 不用 Dataview 结果替代 Python 脚本权重计算。
```

**Step 2: Run tests**

Run:

```bash
python3 -m pytest
```

Expected: all tests PASS.

**Step 3: Commit**

```bash
git add docs/obsidian-first-memory-vault-manual.md
git commit -m "docs: add obsidian-first memory vault manual"
```

## Final Verification

Run:

```bash
python3 -m pytest
python3 scripts/obsidian_audit.py --wiki-root wiki --canvas canvases/LLM-Brain-OS.canvas
git status --short
```

Expected:

- `pytest` reports all tests passed.
- `obsidian_audit.py` prints valid JSON.
- `git status --short` only shows unrelated pre-existing user changes, if any.

## Notes for Execution

- Do not modify `.obsidian/workspace.json`.
- Do not edit or delete current user changes unless explicitly requested.
- Use `apply_patch` for file edits.
- Commit per task as specified.
- If a Dataview or Bases expression is uncertain, keep the file syntactically valid and document the limitation rather than changing existing Python behavior.
