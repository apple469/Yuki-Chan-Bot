import datetime
import sys
from modules.memory.rag import MemoryRAG


# ================= 逻辑模块 1: 手动录入 (原 manual_memory.py) =================
def save_manual_diary(rag, cid="manual_record"):
    print(f"\n>>> 进入手动录入模式 (当前 ID: {cid})")
    print("输入内容后回车存入，输入 'q' 返回主菜单")

    while True:
        try:
            content = input("> ").strip()
            if not content:
                continue
            if content.lower() in ['quit', 'exit', 'q']:
                break
                
            # 执行存入
            rag.save_diary(content=content, chat_id=cid)
            
            curr_time = datetime.datetime.now().strftime('%H:%M:%S')
            print(f"[{curr_time}] ✅ 已存入记忆库")
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"❌ 存入失败: {e}")

# ================= 逻辑模块 2: 记忆管理 (原 manage_memory.py) =================
def manage_memory(rag):
    try:
        collection = rag.collection
    except Exception as e:
        print(f"❌ 读取集合失败: {e}")
        return

    while True:
        # 获取所有记忆
        results = collection.get(include=["documents", "metadatas"])
        ids = results['ids']
        docs = results['documents']
        metas = results['metadatas']

        if not ids:
            print("\n此时记忆库无记录。")
            break

        # 列表显示
        print(f"\n--- 记忆库列表 (共 {len(ids)} 条) ---")
        for i in range(len(ids)):
            print("-" * 15 + f" [索引 {i} | ID: {ids[i]}] " + "-" * 15)
            ts = metas[i].get('timestamp', 0)
            time_str = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M')
            content_preview = docs[i].replace('\n', ' ')
            print(f"{time_str} | {content_preview}")

        print("\n操作提示: [输入数字]删除单条 | [del:1,3]批量删除 | [q]返回主菜单")
        cmd = input("管理指令 > ").strip().lower()

        if cmd in ['q', 'exit']:
            break
        
        try:
            if cmd.startswith('del:'):
                indices = [int(x.strip()) for x in cmd.split(':')[1].split(',')]
                target_ids = [ids[idx] for idx in indices]
                collection.delete(ids=target_ids)
                print(f"✨ 已成功批量删除 {len(target_ids)} 条记录")
            elif cmd.isdigit():
                idx = int(cmd)
                collection.delete(ids=[ids[idx]])
                print(f"✨ 已成功删除记录 [{idx}]")
            else:
                print("无效指令")
        except Exception as e:
            print(f"❌ 操作失败: 索引越界或输入有误 ({e})")

# ================= 主入口 =================
def main():
    print("正在加载 Yuki 记忆系统...")
    try:
        # 统一初始化 RAG，避免重复加载模型
        rag = MemoryRAG()
    except Exception as e:
        print(f"❌ 初始化失败，请检查 memory_rag.py 是否正确: {e}")
        return

    while True:
        print("\n" + "Selection".center(40, "="))
        print("1. 📝 手动录入记忆")
        print("2. 🔍 浏览/删除记忆")
        print("q. 🚪 退出程序")
        print("=" * 40)
        
        choice = input("请选择功能: ").strip().lower()

        if choice == '1':
            cid = input("请输入 Chat ID (默认 manual_record): ").strip()
            save_manual_diary(rag, cid if cid else "manual_record")
        elif choice == '2':
            manage_memory(rag)
        elif choice in ['q', 'exit', 'quit']:
            print("程序已退出。")
            break
        else:
            print("⚠️ 无效选择，请重新输入")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n程序已强制停止")
        sys.exit(0)