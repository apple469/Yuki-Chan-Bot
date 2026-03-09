from memory_rag import memory_rag
# results = memory_rag.search_memory("圈圈老师", chat_id="1034986009", threshold= 1.0)
# print("群1034986009的回忆：", results)
# results2 = memory_rag.search_memory("池宇健说: 我要把yuki关掉了，内设一下\n陆羽说: emm怎么说呢\n池宇健说: 马上好", chat_id="742134223", threshold= 1.0)
# print("群742134223的回忆：", results2)

while True:
    pr = input("请输入要查询的内容（格式：chat_id:关键词，输入exit退出）：")
    if pr.lower() == "exit":
        break
    th = float(input("threshold: "))
    results = memory_rag.search_memory(pr, chat_id="1034986009", threshold=th)
    i = 0
    for result in results:
        print(f"记忆{i}", result)
        i+=1
    results2 = memory_rag.search_memory(pr, chat_id="742134223", threshold=th)
    i = 0
    for result in results2:
        print(f"记忆{i}", result)
        i += 1
