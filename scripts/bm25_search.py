# scripts/bm25_search.py
import os
import re
import sys
import jieba
from rank_bm25 import BM25Okapi

# 🚨 锁死中央知识库的绝对路径
BRAIN_DIR = "/Users/za-stanlexu/Documents/member/member"
GLOBAL_DIR = os.path.join(BRAIN_DIR, "wiki/global_concepts")
PROJECT_DIR = os.path.join(BRAIN_DIR, "wiki/project_exclusives")

def clean_and_tokenize(text):
    # 剥离 Frontmatter 和 Markdown 杂质，仅保留干净文本用于计算 TF-IDF 相关度
    text = re.sub(r"---.*?---", "", text, flags=re.DOTALL)
    text = re.sub(r"[\[\]\-\#\*\>\`\n\r]", " ", text)
    return [word for word in jieba.cut(text.lower()) if word.strip()]

def main():
    if len(sys.argv) < 2:
        print("❌ 错误：请输入检索关键词。")
        sys.exit(1)

    # 支持 --project <项目名> 参数，限定只扫当前项目的 project_exclusives 子目录
    args = sys.argv[1:]
    project_filter = None
    if "--project" in args:
        idx = args.index("--project")
        if idx + 1 < len(args):
            project_filter = args[idx + 1]
            args = args[:idx] + args[idx + 2:]
        else:
            print("❌ 错误：--project 后需跟项目名。")
            sys.exit(1)

    query_str = " ".join(args)
    doc_paths = []
    corpus = []

    # 扫描公共域；project_exclusives 按 project_filter 决定扫单项目还是全部
    if project_filter:
        project_exclusive_dir = os.path.join(PROJECT_DIR, project_filter)
        search_dirs = [GLOBAL_DIR, project_exclusive_dir]
    else:
        search_dirs = [GLOBAL_DIR, PROJECT_DIR]

    for search_dir in search_dirs:
        if not os.path.exists(search_dir): continue
        for root, _, files in os.walk(search_dir):
            for file in files:
                if file.endswith(".md"):
                    path = os.path.join(root, file)
                    doc_paths.append(path)
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            corpus.append(clean_and_tokenize(f.read()))
                    except Exception:
                        corpus.append([])

    if not corpus or len(doc_paths) == 0:
        print("🫙 中央知识库活跃区为空，未找到可检索内容。")
        return

    # 实例化 BM25 核心算法
    bm25 = BM25Okapi(corpus)
    tokenized_query = clean_and_tokenize(query_str)
    doc_scores = bm25.get_scores(tokenized_query)
    
    final_results = []
    for idx, path in enumerate(doc_paths):
        if idx >= len(doc_scores) or doc_scores[idx] <= 0: continue
        
        try:
            with open(path, "r", encoding="utf-8") as f: content = f.read()
        except Exception: continue
        
        # 联动机制：提取笔记当前的记忆权重字段，对检索结果执行概率过滤与权重排序
        weight_match = re.search(r"current_weight:\s*([\d\.]+)", content)
        current_weight = float(weight_match.group(1)) if weight_match else 1.0
        
        # 最终复合得分 = BM25 相关度 * 笔记活跃度权重
        final_score = doc_scores[idx] * current_weight
        final_results.append((final_score, path))
        
    final_results.sort(key=lambda x: x[0], reverse=True)
    
    print("=== BM25 记忆加权交叉检索结果 (Top 3) ===")
    for score, path in final_results[:3]:
        # 打印相对路径缩短控制台长度，方便 Claude 精准识别执行 read_file
        rel_path = os.path.relpath(path, BRAIN_DIR)
        print(f"📄 [加权得分: {round(score, 2)}] 相对物理路径: {rel_path}")

if __name__ == "__main__":
    main()
