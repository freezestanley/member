# scripts/bm25_search.py
import os
import re
import sys
import pickle
import jieba
from rank_bm25 import BM25Okapi

# 🚨 锁死中央知识库的绝对路径
BRAIN_DIR = "/Users/za-stanlexu/Documents/member/member"
GLOBAL_DIR = os.path.join(BRAIN_DIR, "wiki/global_concepts")
PROJECT_DIR = os.path.join(BRAIN_DIR, "wiki/project_exclusives")
CACHE_PATH = os.path.join(BRAIN_DIR, "_inbox/.bm25_cache.pkl")


def clean_and_tokenize(text):
    """剥离 Frontmatter 和 Markdown 杂质，仅保留干净文本用于 TF-IDF 计算。"""
    text = re.sub(r"---.*?---", "", text, flags=re.DOTALL)
    text = re.sub(r"[\[\]\-\#\*\>\`\n\r]", " ", text)
    return [word for word in jieba.cut(text.lower()) if word.strip()]


def collect_md_paths(search_dirs):
    """遍历给定目录列表，返回所有 .md 文件的绝对路径。"""
    paths = []
    for d in search_dirs:
        if not os.path.exists(d):
            continue
        for root, _, files in os.walk(d):
            for f in files:
                if f.endswith(".md"):
                    paths.append(os.path.join(root, f))
    return paths


def build_or_load_cache(search_dirs=None):
    """
    加载或重建 BM25 索引 Cache。

    Cache 结构（pickle）：
    {
      "mtimes": {文件绝对路径: mtime_float},
      "doc_paths": [路径列表],
      "corpus": [[tokens], [tokens], ...]
    }

    重建条件：
    - Cache 文件不存在
    - 任意已缓存文件的 mtime 与缓存记录不一致
    - 有新文件未在缓存中
    """
    if search_dirs is None:
        search_dirs = [GLOBAL_DIR, PROJECT_DIR]

    current_paths = collect_md_paths(search_dirs)
    current_mtimes = {p: os.path.getmtime(p) for p in current_paths}

    # 尝试加载现有 cache
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, "rb") as f:
                cache = pickle.load(f)
            cached_mtimes = cache.get("mtimes", {})

            # 检查是否需要重建：路径集合变化 or 任意 mtime 变化
            needs_rebuild = (
                set(current_paths) != set(cached_mtimes.keys())
                or any(current_mtimes.get(p) != cached_mtimes.get(p)
                       for p in current_paths)
            )

            if not needs_rebuild:
                return cache  # Cache 命中，直接返回
        except Exception:
            pass  # Cache 损坏，重建

    # 重建索引
    print("[bm25_cache] 正在重建索引...", file=sys.stderr)
    corpus = []
    for path in current_paths:
        try:
            with open(path, "r", encoding="utf-8") as f:
                corpus.append(clean_and_tokenize(f.read()))
        except Exception:
            corpus.append([])

    cache = {
        "mtimes": current_mtimes,
        "doc_paths": current_paths,
        "corpus": corpus,
    }

    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "wb") as f:
        pickle.dump(cache, f)
    print(f"[bm25_cache] 索引已保存，共 {len(current_paths)} 篇笔记。", file=sys.stderr)

    return cache


def main():
    if len(sys.argv) < 2:
        print("❌ 错误：请输入检索关键词。")
        sys.exit(1)

    # 解析参数
    args = sys.argv[1:]
    project_filter = None
    rebuild_cache_only = False

    if "--rebuild-cache" in args:
        rebuild_cache_only = True
        args = [a for a in args if a != "--rebuild-cache"]

    if "--project" in args:
        idx = args.index("--project")
        if idx + 1 < len(args):
            project_filter = args[idx + 1]
            args = args[:idx] + args[idx + 2:]
        else:
            print("❌ 错误：--project 后需跟项目名。")
            sys.exit(1)

    # 确定扫描范围
    if project_filter:
        project_exclusive_dir = os.path.join(PROJECT_DIR, project_filter)
        search_dirs = [GLOBAL_DIR, project_exclusive_dir]
    else:
        search_dirs = [GLOBAL_DIR, PROJECT_DIR]

    # 仅重建缓存，不执行检索
    if rebuild_cache_only:
        build_or_load_cache(search_dirs=[GLOBAL_DIR, PROJECT_DIR])
        print("[bm25_cache] 缓存重建完成。")
        return

    if not args:
        print("❌ 错误：请输入检索关键词。")
        sys.exit(1)

    query_str = " ".join(args)

    # 加载 Cache（命中则直接用，否则重建）
    cache = build_or_load_cache(search_dirs=[GLOBAL_DIR, PROJECT_DIR])
    all_paths = cache["doc_paths"]
    all_corpus = cache["corpus"]

    # 筛选出本次 search_dirs 范围内的文件
    allowed_prefixes = tuple(
        os.path.abspath(d) for d in search_dirs if os.path.exists(d)
    )
    filtered = [
        (p, c) for p, c in zip(all_paths, all_corpus)
        if os.path.abspath(p).startswith(allowed_prefixes)
    ]

    if not filtered:
        print("🫙 中央知识库活跃区为空，未找到可检索内容。")
        return

    doc_paths, corpus = zip(*filtered)
    doc_paths, corpus = list(doc_paths), list(corpus)

    # BM25 检索
    bm25 = BM25Okapi(corpus)
    tokenized_query = clean_and_tokenize(query_str)
    doc_scores = bm25.get_scores(tokenized_query)

    final_results = []
    for idx, path in enumerate(doc_paths):
        if idx >= len(doc_scores) or doc_scores[idx] <= 0:
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception:
            continue

        weight_match = re.search(r"current_weight:\s*([\d\.]+)", content)
        current_weight = float(weight_match.group(1)) if weight_match else 1.0
        final_score = doc_scores[idx] * current_weight
        final_results.append((final_score, path))

    final_results.sort(key=lambda x: x[0], reverse=True)

    print("=== BM25 记忆加权交叉检索结果 (Top 3) ===")
    for score, path in final_results[:3]:
        rel_path = os.path.relpath(path, BRAIN_DIR)
        print(f"📄 [加权得分: {round(score, 2)}] 相对物理路径: {rel_path}")


if __name__ == "__main__":
    main()
