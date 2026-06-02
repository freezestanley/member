import os, re, sys, jieba
from rank_bm25 import BM25Okapi

WIKI_DIR = "./wiki/concepts"

def clean_and_tokenize(text):
    text = re.sub(r"---.*?---", "", text, flags=re.DOTALL)
    text = re.sub(r"[\[\]\-\#\*\>\`]", "", text)
    return list(jieba.cut(text.lower()))

if len(sys.argv) >= 2:
    query_str = " ".join(sys.argv[1:])
    doc_paths, corpus = [], []
    for root, _, files in os.walk(WIKI_DIR):
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
            with open(path, "r", encoding="utf-8") as f: text = f.read()
            weight_match = re.search(r"current_weight:\s*([\d\.]+)", text)
            weight = float(weight_match.group(1)) if weight_match else 1.0
            final_score = doc_scores[idx] * weight
            if doc_scores[idx] > 0: final_results.append((final_score, path))
                
        final_results.sort(key=lambda x: x[0], reverse=True)
        print(f"=== BM25 复合检索结果 (Top 3) ===")
        for score, path in final_results[:3]:
            print(f" [得分: {round(score, 2)}] 路径: {path}")

