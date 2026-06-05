# [ARCH-V2.1-COMPRESSED] LLM-BRAIN-OS-V2.1-RESILIENT
[ENV] DIR=/Users/za-stanlexu/Documents/member/member/; STATUS_MACHINE=[active|deprecated]
[INDEX_SINGLETONS] inbox/.{symbol,alias}_map.{pkl,json} -> Dict[str, rel_path] (1-to-1 SSOT Max Court)

[PIPE-INGEST: 3-IN-1 ANTI-ZOMBIE INTERCEPTOR]
1. PREEMPTION: Scan new_doc.[code_symbols, aliases]. Match any old_owner OR old_stem in new_doc.aliases -> Trigger Forced Pruning: old_doc.status=deprecated, old_doc.superseded_by=new_rel_path, old_doc.current_weight=0.01.
2. ATOMIC OVERWRITE: No file renaming/relocation (protect links). Overwrite full_target_path. 
3. SHADOW APPENDIX: Read old_body -> Strip nested history -> Append below "## 历史版本演进快照 (历史留存)" -> sync write to shadow JSON/PKL.

[PIPE-RETRIEVAL: LIFE-CYCLE DOUBLE-TUNNEL]
1. ONLINE MASKS: bm25_search.py calculates FinalScore. If doc.status==deprecated OR doc.path in superseded_blacklist OR doc.current_weight<=0.02 -> Hard Drop.
2. SCOPE-DECAY: If doc contains Top 5% Common-Symbols AND (doc.project!=current_ctx AND doc.last_activated > 14 days) -> FinalScore *= 0.2 (Forced 80% Demotion). Cut strict Top 3.
3. DEHYDRATOR: context_dehydrator.py scans Top 3. Hard cut everything below "## 历史版本演进快照" -> Strip frontmatter/HTML comments/死空格 -> Clean Stream to LLM context.

[DISASTER-RECOVERY: REBUILD DEFENSE]
If pickle.load(.pkl) crashes (EOF/Dirty Write) -> Try read readable .json backup -> Fail? -> Trigger rebuild_indices_from_scratch(): os.walk(wiki/) -> Extract all active metadata -> Atomic flush both .pkl and .json. Resilience = 100%.

[RED-LINES ADDENDUM]
BANS-8: Never use dynamic renaming (e.g. auth_v2.md) to keep history in active zone. (Reason: Jam Top 3 recall).
BANS-9: Never introduce blocking interactive CLI (e.g. [y/n]) in automation pipelines. (Reason: Hang fcntl.LOCK_EX, 10s Timeout deadlock).
