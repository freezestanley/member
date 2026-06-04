hot.md 空间路由与大纲树化技术方案一、 架构改动对比 (Architecture Evolution)text【旧方案：单轨混杂】
wiki/hot.md (全局共用) ──> 堆积各项目高权笔记 ──> 形成 "Token 黑洞" (Claude 专一性受损)

【新方案：双轨路由】
                             ┌──> wiki/global_hot.md (仅限全局元知识 Top N)
fswatch 变更 ──> hot_watcher ┤
                             └──> wiki/project_exclusives/<项目名>/hot.md (项目隔离 Top M)
请谨慎使用此类代码。二、 hot.md 存储模板与语法规范 (Standard Template)升级后的 global_hot.md 与各项目 hot.md 统一采用动态大纲树结构。不允许存在拉平的简单列表，必须回显源笔记的 H1 ~ H3 标题层级，以便 Claude 预知知识全貌。2.1 规范模板markdown# 🧠 Project Hot Memory Dashboard (DO NOT EDIT MANUALLY)
> [!WARNING]
> 本文件由 `hot_refresh.py` 自动生成，任何手动修改将在下次文件变更时被覆盖。

## 📌 Top Memory Outline Tree

### 1. [[git_atomic_commit]] — Git原子操作规范 · 🧠0.92 · 📊14次
#### H1: 核心原则
##### H2: 什么是原子提交
##### H2: Commit Message 约束
#### H1: 边界防御与异常处理

### 2. [[fcntl_lock_standard]] — fcntl文件锁机制 · 🧠0.85 · 📊9次
#### H1: 锁类型选择
#### H1: 指数退避重试算法
请谨慎使用此类代码。三、 hot_refresh.py 核心改动设计 (Python Engine Upgrades)脚本需支持 --global 与 --project <name> 双参数路由，并具备Markdown 标题树提取能力。3.1 核心解析与渲染算法pythonimport re
import os
import fcntl
import time
from typing import List, Dict, Any

def extract_markdown_headers(file_path: str) -> List[str]:
    """提取源文件中的 H1~H3 标题，并转换为标准大纲树缩进"""
    tree_lines = []
    if not os.path.exists(file_path):
        return tree_lines
        
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            # 排除 FrontMatter 干扰，仅匹配正文行
            match = re.match(r'^(#{1,3})\s+(.+)$', line)
            if match:
                level_hashes, title_text = match.groups()
                level = len(level_hashes)
                # 转换层级：源文件的 H1 对应大纲树的 #### H1
                # 源文件 # -> 大纲树 #### H1: 
                # 源文件 ## -> 大纲树 ##### H2:
                indent = "#" * (level + 3)
                tree_lines.append(f"{indent} H{level}: {title_text.strip()}")
    return tree_lines

def generate_hot_file(target_path: str, source_files: List[Dict[str, Any]], top_k: int):
    """根据权重排序，提取大纲并写入目标热记忆文件"""
    # 1. 按权重降序排序
    sorted_files = sorted(source_files, key=lambda x: x['weight'], reverse=True)[:top_k]
    
    # 2. 构造 Markdown 内容
    lines = [
        "# 🧠 Brain Hot Memory Dashboard (DO NOT EDIT MANUALLY)",
        "> [!WARNING]",
        "> 本文件由 `hot_refresh.py` 自动生成，任何手动修改将在下次文件变更时被覆盖。\n",
        "## 📌 Top Memory Outline Tree\n"
    ]
    
    for idx, doc in enumerate(sorted_files, 1):
        stem = doc['stem']
        title = doc['title']
        weight = f"{doc['weight']:.2f}"
        count = doc['access_count']
        
        # 写入大纲树根节点
        lines.append(f"### {idx}. [[{stem}]] — {title} · 🧠{weight} · 📊{count}次")
        
        # 注入子标题树
        sub_headers = extract_markdown_headers(doc['file_path'])
        if sub_headers:
            lines.extend(sub_headers)
        lines.append("") # 换行隔离
        
    # 3. 带有 fcntl 锁的原子写入
    lock_file_path = "member/_inbox/.hot_refresh.lock"
    with open(lock_file_path, "w") as lock_f:
        start_time = time.time()
        while True:
            try:
                fcntl.flock(lock_f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.time() - start_time > 10.0:
                    raise RuntimeError("获取 hot_refresh 互斥锁超时（>10s），写出中止。")
                time.sleep(0.5) # 指数退避或固定步长重试
                
        with open(target_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))
            
        fcntl.flock(lock_f, fcntl.LOCK_UN)
请谨慎使用此类代码。四、 hot_watcher.sh 路由剪裁设计 (Shell Routing Infrastructure)底层监视器必须通过正则从 fswatch 捕获的绝对路径中，精准剪裁出 项目名，实现定向刷新。bash#!/bin/bash
# hot_watcher.sh

VAULT_DIR="/path/to/your/wiki"
COOLDOWN=2

# 使用 fswatch 监控 wiki 目录下的 md 变更
fswatch -0 -o -e ".*_hot\.md$" -e ".*/hot\.md$" "$VAULT_DIR" | while read -d "" event; do
    echo "检测到文件变更，防抖等待 ${COOLDOWN}s..."
    sleep $COOLDOWN
    
    # 捕获最新发生变化的 md 文件路径（排除 hot 文件自身）
    CHANGED_FILE=$(git status --porcelain | grep '\.md$' | grep -v 'hot\.md' | head -n 1 | awk '{print $2}')
    
    if [ -z "$CHANGED_FILE" ]; then
        continue
    fi

    # 串行触发检索缓存重建
    python3 scripts/bm25_search.py --rebuild-cache

    # 核心空间路由剪裁
    if [[ "$CHANGED_FILE" =~ wiki/global_concepts/ ]]; then
        echo "触发全局热记忆刷新..."
        python3 scripts/hot_refresh.py --global
    elif [[ "$CHANGED_FILE" =~ wiki/project_exclusives/([^/]+)/ ]]; then
        PROJECT_NAME="${BASH_REMATCH[1]}"
        echo "检测到项目 [${PROJECT_NAME}] 变更，触发定向项目热记忆刷新..."
        python3 scripts/hot_refresh.py --project "$PROJECT_NAME"
    fi
done
请谨慎使用此类代码。五、 L5 Brain-Skill 上下文挂载微调 (Agent Injection Matrix)当 Claude (Brain-Skill) 启动或切换项目时，其系统提示词（System Prompt）或动态挂载上下文逻辑进行如下改动：python# L5 Skill 环境初始化逻辑伪代码
def bootstrap_claude_context(current_project: str):
    # 1. 强制注入环境变量，供底层链路识别
    os.environ["CURRENT_PROJECT"] = current_project
    
    # 2. 核心：双轨热记忆组装
    global_hot_meta = read_file("wiki/global_hot.md")
    project_hot_meta = read_file(f"wiki/project_exclusives/{current_project}/hot.md")
    
    # 3. 灌入 Claude 的 System Prompt / Context Window
    claude_system_context = f"""
    你当前正在处理项目：[{current_project}]。
    以下是当前系统的常驻高权记忆大纲树，请在对话中优先参考：
    
    ==== 全局通用元知识 ====
    {global_hot_meta}
    
    ==== 当前项目独占知识 ====
    {project_hot_meta}
    """
    return claude_system_context
请谨慎使用此类代码。六、 防御边界与异常处理 (Safety Rails)空项目防御：若新项目没有任何高权笔记，hot_refresh.py 必须生成一个仅包含警告信息的骨架 hot.md，严禁直接删表或报 FileNotFound。大纲树深度死循环防御：提取标题时，严格限制 len(level_hashes) <= 3。若有笔记使用 # 超过 4 层（如 ####），一律忽略，防止 Token 空间无端膨胀。并发安全隔离：即使是 --global 和 --project 同时触发，由于它们抢占的是同一把底层锁 .hot_refresh.lock，在内核层也是严格串行化执行，绝不会发生交织写损坏。