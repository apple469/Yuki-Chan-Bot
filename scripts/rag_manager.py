# rag_manager.py

import time

# --- 维护工具入口 ---
if __name__ == "__main__":
    print("正在加载数据库")
    first_time = time.time()
    from modules.memory.rag import MemoryRAG
    rag = MemoryRAG()
    last_time = time.time()
    print(f"数据库加载完成，用时{last_time - first_time}\n\n")
    print("\n--- Yuki 记忆库核心维护 ---")
    print("1. 查看库状态 | 2. 预览重复项 | 3. 物理清理重复")
    
    cmd = input("> ").strip()
    if cmd == "1":
        res = rag.collection.get()
        print(f"当前总条数: {len(res['ids'])}")
    elif cmd == "2":
        rag.clean_duplicate_diaries(dry_run=True)
    elif cmd == "3":
        if input("确认清理？(y/n): ").lower() == 'y':
            rag.clean_duplicate_diaries(dry_run=False)