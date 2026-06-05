# [ARCH-V3-FINAL] LLM-Brain OS 归档一致性方案

[DATE] 2026-06-05 | [BRANCH] feat/Pipeline | [STATUS] 待实施

---

## [DIR] 目录结构

```
/member/
  wiki/                          # 活跃语料库
    global_concepts/
    project_exclusives/
  archive/                       # 与wiki/同级，镜像wiki/子目录结构
    global_concepts/
    project_exclusives/
```

归档=物理移动到`archive/<原相对路径>`。`archive/`不在任何脚本扫描路径内，隔离由目录边界保证。
`archive/`保留在Obsidian vault根目录下，Obsidian自动扫描，`[[a]]`双链零死链，无需任何设置。双链改写逻辑（`~~[[a]]~~`）不再需要，`archive_with_backlink_update`中对应代码可删除。

---

## [FM] Frontmatter 扩展

所有知识笔记追加：
```yaml
status: active          # active | deprecated | archived | incomplete
superseded_by: ""       # 相对wiki/路径，格式：global_concepts/foo.md
```
跳过生成文件：`hot.md` `global_hot.md` `index.md` `log.md`

---

## [SCRIPTS] 脚本改动

### memory_manager.py（~55行）

**A. ARCHIVE_DIR路径**
```python
ARCHIVE_DIR = os.path.join(BRAIN_DIR, "archive")  # 原：wiki/archive
```

**B. archive_with_backlink_update 修复路径打平bug**
```python
wiki_root = os.path.join(BRAIN_DIR, "wiki")
rel_path = os.path.relpath(note_path, wiki_root)     # project_exclusives/xx/a.md
archive_path = os.path.join(archive_dir, rel_path)   # archive/project_exclusives/xx/a.md
os.makedirs(os.path.dirname(archive_path), exist_ok=True)
# 移动前写status
content = open(note_path).read()
content = re.sub(r'^status:\s*\S+', 'status: archived', content, flags=re.MULTILINE)
open(note_path, 'w').write(content)
os.rename(note_path, archive_path)
```

**C. scan_and_clean 无frontmatter自动补全**
- 跳过生成文件集合
- project推断：路径含`global_concepts/`→`global`，含`project_exclusives/<name>/`→`<name>`
- created_at/last_activated用文件mtime，其余默认值
- 已有frontmatter但缺status/superseded_by→只追加缺失字段

**D. scan_and_clean 孤儿.tmp检测**
- 发现`foo.md.tmp`存在→对应`foo.md`标`status: incomplete`

### bm25_search.py（+12行）

collect_md_paths加status过滤，读前512字节：
- `archived|deprecated|incomplete`→跳过
- 无status字段→默认active

### hot_refresh.py（+3行）

collect_notes第74行后：
```python
if fm.get("status") in ("archived", "deprecated", "incomplete"):
    continue
```

### skills/brain-ingest.md（~15行）

写入流程改为原子操作：
```
1. 写 foo.md.tmp
2. fcntl.LOCK_EX → _inbox/.wiki_write.lock
3. rename foo.md.tmp → foo.md  (POSIX原子)
4. fcntl.LOCK_EX → _inbox/.index.lock → 更新index.md → 释放
5. 释放 .wiki_write.lock
```
frontmatter模板补`status: active` + `superseded_by: ""`

---

## [LOCKS] 并发保证

- 所有wiki文件写操作：`_inbox/.wiki_write.lock`
- index.md专用：`_inbox/.index.lock`
- 复用hot_refresh.py已有`atomic_write`函数
- 限制：flock跨进程有效，跨线程无效（当前单进程调用，无影响）

---

## [DEFECTS] 残留缺陷与隐患

| ID | 级别 | 描述 | 处置 |
|----|------|------|------|
| D-A | 低 | render_global_indices不过滤status | 物理移动后原路径无文件，实际无影响，可接受 |
| D-B | 低 | superseded_by无路径校验 | 不影响脚本逻辑，后续按需加 |
| D-C | 中 | flock跨线程无效 | 当前单进程无影响，多线程化时换threading.Lock |
| D-D | 低 | .tmp孤儿检测依赖scan_and_clean运行时机 | bm25缓存mtime保护，窗口极短，可接受 |
| D-E | 中 | symbol_map与归档物理平移不一致（预防性） | 当前symbol_map未实现，隐患暂不存在。**实现时必须**：os.rename成功后同步清除已归档文件的所有symbol/alias条目 |
| D-F | 低 | hot_watcher.sh对.tmp的竞态条件 | **已消除**：fswatch过滤器`-i "\.md$"`天然排除.tmp，watcher不感知.tmp变动。禁止修改此过滤器加入非.md后缀 |

---

## [IMPL] 实施顺序

```
1. mkdir archive/
2. memory_manager.py：ARCHIVE_DIR + 路径修复 + 归档前写status + 补全 + .tmp检测
3. bm25_search.py：collect_md_paths加status过滤
4. hot_refresh.py：collect_notes加status过滤
5. skills/brain-ingest.md：flock+tmp rename原子写入 + frontmatter模板补字段
6. 首次运行 python3 scripts/memory_manager.py → 自动补全全库frontmatter
```

步骤6完成后现有笔记全部获得status字段，不需要手动批量处理。

---

## [REVIEW] Codex对抗性review结论

三条findings全部已在方案中覆盖，均为"已设计未实施"状态：
- 硬删除→归档迁移：方案已定义，待实施
- os.path.basename路径打平：方案已识别缺陷B，待改代码
- ingest非原子：方案已定义flock+tmp rename，待改代码
