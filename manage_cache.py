# manage_cache.py
import asyncio
from meme_processor import MemeProcessor

async def main():
    processor = MemeProcessor()
    
    while True:
        print("\n--- Yuki 表情包缓存管理系统 ---")
        print("1. 查看缓存使用统计报告")
        print("2. 预览低频缓存清理 (使用次数 < 5)")
        print("3. 执行低频缓存清理 (使用次数 < 5)")
        print("4. 退出")
        
        choice = input("请选择操作: ").strip()
        
        if choice == '1':
            report = processor.get_cache_stats()
            print(f"\n{'使用次数':<8} | {'识别内容':<30} | {'哈希/URL预览'}")
            print("-" * 70)
            for item in report:
                # 这里的 value 是 AI 识别出的文字描述，full_key 是对应的图片哈希或URL
                print(f"{item['count']:<10} | {item['value']:<32} | {item['key']}")
            print(f"\n总计: {len(report)} 条记录")

        elif choice == '2':
            # dry_run=True 只预览不删除
            to_delete = processor.clean_low_usage_cache(threshold=1, dry_run=True)
            print(f"\n以下 {len(to_delete)} 条记录将被清理:")
            for item in to_delete:
                print(f"- [次数:{item['count']}] {item['value']} ({item['key'][:30]}...)")

        elif choice == '3':
            confirm = input("确定要执行清理吗？(y/n): ").lower()
            if confirm == 'y':
                # dry_run=False 执行实际删除
                to_delete = processor.clean_low_usage_cache(threshold=1, dry_run=False)
                print(f"清理完成，共移除 {len(to_delete)} 条记录。")

        elif choice == '4':
            break
        else:
            print("无效选择，请重新输入。")

if __name__ == "__main__":
    asyncio.run(main())