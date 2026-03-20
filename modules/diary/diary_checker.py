import asyncio
import datetime
import json
import re
import time

from config import DIARY_IDLE_SECONDS, DIARY_MIN_TURNS, DIARY_MAX_LENGTH, KEEP_LAST_DIALOGUE
from core.prompts import BASE_SETTING
from main import history_manager, yuki, llm, memory_rag


async def idle_diary_checker():
    """后台任务，每30秒检查一次空闲群聊"""
    while True:
        await asyncio.sleep(30)  # 检查间隔，可根据需要调整
        now = time.time()
        print(f"[System] 后台检查中... ({datetime.datetime.now().strftime('%H:%M:%S')})")
        history_dict = history_manager.load()
        for cid, last_msg in list(yuki.last_message_time.items()):
            # 跳过正在写日记的群聊
            if cid in yuki.writing_diary:
                continue

            # 计算空闲时间
            idle_seconds = now - last_msg
            if idle_seconds < DIARY_IDLE_SECONDS:
                continue  # 空闲时间不足

            # 检查对话轮数
            if cid not in history_dict:
                continue
            non_system_msgs = [msg for msg in history_dict[cid] if msg["role"] != "system"]
            non_system_count = len(non_system_msgs)
            if non_system_count < DIARY_MIN_TURNS :  # 如果轮数不足但空闲时间已经是阈值的两倍，不输出
                if idle_seconds < DIARY_IDLE_SECONDS * 2:
                    print(
                        f"[System] 群 {cid} 空闲 {idle_seconds:.1f} 秒，但对话轮数仅 {non_system_count}，继续观察..."
                        f"({datetime.datetime.now().strftime('%H:%M:%S')})"
                    )
                continue  # 轮数不足

            # 满足条件，触发写日记
            print(f"[System] 后台检查：群 {cid} 空闲 {idle_seconds:.1f} 秒，轮数 {non_system_count}，触发写日记")
            yuki.writing_diary.add(cid)
            try:
                new_history = await summarize_memory(int(cid), history_dict[cid])
                history_dict[cid] = new_history
                history_manager.save(history_dict)
            finally:
                yuki.writing_diary.discard(cid)


async def check_diary_force(chat_id, cid: str, history_dict: dict):
    effective_history = [message for message in history_dict[cid] if message["role"] != "system"]

    if len(effective_history) >= DIARY_MAX_LENGTH and cid not in yuki.writing_diary:
        print(f"[System] 历史长度达到保底阈值 {DIARY_MAX_LENGTH}，触发写日记")
        yuki.writing_diary.add(cid)
        try:
            history_dict[cid] = await summarize_memory(chat_id, history_dict[cid])
            history_manager.save(history_dict)
        finally:
            yuki.writing_diary.discard(cid)


async def summarize_memory(chat_id, history):
    '''根据当前对话历史写日记，并存入记忆库，返回更新后的历史'''

    print(f"[System] [{chat_id}] 记忆有点长了，Yuki 正在写日记回顾...")
    dialogue_msgs = [msg for msg in history if msg["role"] != "system"]
    content_to_summarize = json.dumps(dialogue_msgs, ensure_ascii=False)
    time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    summary_prompt = (
        f"你现在是 Yuki。请以 Yuki 的口吻写一篇 200 字以内的日记，总结这段对话。"
        f"要求真实记录，尤其是完整叙述和性格概述，不要删减重要内容。"
        f"当前时间：{time_str}。\n"
        f"注意：如果对话中有提到性格、喜好、习惯等细节，请务必写入日记，这些是Yuki记忆的重要组成部分。"
        f"日记格式要求：\n 不用加标题、天气、颜文字和时间戳，直接正文开头，不要换行。"
    )

    try:
        diary_content = llm.robust_api_call(
            model="deepseek-v3",
            messages=[
                {"role": "system", "content": f"{BASE_SETTING}"},
                {"role": "user", "content": (
                    f"以下是需要总结的对话内容：\n{content_to_summarize}\n\n"
                    f"---任务指令---\n"
                    f"{summary_prompt}"
                )}
            ],
            temperature=0.7,  # 降低温度，让它说话更稳、更常用
            top_p=0.8,  # 稍微收窄采样范围，过滤冷门词
            frequency_penalty=0.1,  # 极低的惩罚，允许它说大白话
            presence_penalty=0.0,  # 不强迫它聊新话题
            max_tokens=200  # 强制短句，短句更容易显自然
        )
        diary_content = re.sub(r'\s*FINISHED\s*$', '', diary_content, flags=re.IGNORECASE)
        diary_content = f"【日记({time_str})】：\n{diary_content}"
        memory_rag.save_diary(diary_content, chat_id=chat_id)
        print(f"[System] 日记已存入记忆库：{diary_content}")

        new_history_json = (
            [msg for msg in history if msg["role"] == "system"] +
            dialogue_msgs[-KEEP_LAST_DIALOGUE:]
        )
        return new_history_json

    except Exception as e:
        print(f"[System ERROR] 写日记失败: {e}")
        return history
