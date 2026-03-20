import datetime
from typing import Any

from config import KEEP_LAST_DIALOGUE
from main import yuki


async def build_chat_context(chat_id: str, combined_text: str, history_dict: dict, mode,
                             relevant_diaries: list[Any]) -> list[dict[str, str | Any]]:
    # 这里的 diary 现在是字典，我们要取出 ['content']
    for i, diary_obj in enumerate(reversed(relevant_diaries), 1):
        content = diary_obj['content']  # 提取文本内容
        # preview = content[:50] + "..." if len(content) > 100 else content
        preview = content
        preview = preview.replace('\n', ' ')
        print(f"[Diary Debug]回忆 {i}: {preview}")

    # ----------------------- 构建API消息列表 ----------------------------
    # 1. 基础人设
    system_prompt = history_dict[chat_id][0]["content"] if history_dict[chat_id] and history_dict[chat_id][0][
        "role"] == "system" else yuki.get_setting(mode)
    combined_API_message = [{"role": "system", "content": system_prompt}]

    # 2. 插入检索到的日记
    for diary_obj in reversed(relevant_diaries):
        content = diary_obj['content']  # 提取文本内容
        combined_API_message.append({"role": "system", "content": f"【回忆】{content}"})

    # --- 调试输出：打印加权分和匹配到的关键词信息 ---
    for i, diary_obj in enumerate(relevant_diaries[:3], 1):
        # 打印加权分和匹配到的关键词信息
        print(f"[RAG-Debug] 回忆 {i} | 得分: {diary_obj['score']:.2f} | 详情: {diary_obj['debug']}")

    # 3. 加入最近KEEP_LAST_DIALOGUE条对话（不包括系统消息）
    recent_msgs = [msg for msg in history_dict[chat_id][-KEEP_LAST_DIALOGUE - 1:-1] if msg["role"] != "system"]
    combined_API_message.extend(recent_msgs)
    combined_API_message.append(
        {"role": "user", "content": f" (当前时间:{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}){combined_text}"})
    return combined_API_message
