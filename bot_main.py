# bot_main.py
import json
import asyncio
import websockets
import datetime
from config import (
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, NAPCAT_WS_URL,
    TARGET_QQ, TARGET_GROUP, DEBOUNCE_TIME, DIARY_THRESHOLD,
    MIN_ACTIVE_ENERGY, COST_PER_REPLY
)
from yuki_core import YukiState, HistoryManager, BASE_SETTING
from message_utils import CQCodeParser, MessageSender
from meme_processor import MemeProcessor

# 初始化各模块
message_processor = CQCodeParser(NAPCAT_WS_URL)
meme_processor = MemeProcessor()
yuki = YukiState(DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL)
history_manager = HistoryManager()

async def summarize_memory(chat_id, history):
    print(f"[{chat_id}] 记忆有点长了，Yuki 正在写日记回顾...")
    content_to_summarize = json.dumps(history[1:], ensure_ascii=False)
    time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    summary_prompt = f"你现在是 Yuki。请以 Yuki 的口吻写一篇 150 字以内的日记，总结这段对话。当前时间：{time_str}"
    try:
        response = yuki.client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": f"{BASE_SETTING}"},
                {"role": "user", "content": f"{summary_prompt}\n\n内容如下：\n{content_to_summarize}"}
            ]
        )
        diary_entry = response.choices[0].message.content
        new_diary_node = {"role": "system", "content": f"【日记({time_str})】：\n{diary_entry}"}
        system_messages = [msg for msg in history if msg["role"] == "system"]
        system_messages.append(new_diary_node)
        return system_messages
    except Exception as e:
        print(f"写日记失败: {e}")
        return history

async def should_i_reply(history, current_text):
    """使用API判断是否需要回复群聊，加入精力值逻辑"""
    current_e = yuki.update_energy()

    if any(keyword in current_text for keyword in ["主人", "哥哥", "Yuki", "yuki"]):
        print(f"!!! 检测到关键召唤，Yuki 强制清醒 (当前精力: {current_e:.1f})")
        return True

    if current_e < MIN_ACTIVE_ENERGY:
        print(f"Yuki 太累了... 正在潜水回复体力 (当前精力: {current_e:.1f})")
        return False

    try:
        system_context = [msg for msg in history if msg.get("role") == "system"]
        recent_dialogue = [msg for msg in history if msg.get("role") != "system"][-8:]

        dialogue_text = ""
        for msg in recent_dialogue:
            role_name = "" if msg["role"] == "user" else "Yuki说:"
            dialogue_text += f"{role_name}{msg['content']}\n"

        energy_desc = "精力充沛，很愿意找人聊天" if current_e > 90 else "精力正常，偶尔会回复消息" if current_e > 60 else "疲惫，只想接少数有趣的话题" if current_e > 30 else "非常疲惫，只有认为必须发言时才发言"

        check_prompt = (
            f"【Yuki的当前状态】\n精力值：{current_e:.1f}/100 ({energy_desc})，发言消耗{COST_PER_REPLY}点精力\n\n"
            f"请分析对话氛围，判断现在是否要发言。判断依据：当前发言者是不是说完了要说的全部内容、感兴趣程度、提问对象等，应合理判断氛围\n注意：如果对方表述不完整或模糊，如[图片]，可以不发言"
            f"如果要发言，请回答'YES'。如果想继续潜水观察，请回答'NO'。"
        )

        messages = (system_context +
                    [{"role": "system", "content": f"最近对话：\n{dialogue_text}"}] +
                    [{"role": "user", "content": check_prompt}])

        response = yuki.client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            max_tokens=10,
            temperature=0.7
        )

        result = response.choices[0].message.content.strip().upper()
        return "YES" in result
    except Exception as e:
        print(f"判定失败原因: {e}")
        return False

async def clean_cq_code(text):
    """
    清理CQ码，解析@为用户名，并对动画表情进行AI理解
    返回处理后的文本
    """
    modified_text, image_urls = meme_processor.extract_urls_from_text(text)

    if image_urls:
        understood_contents = []
        for url in image_urls:
            result = await meme_processor.understand_from_url(url)
            understood_contents.append(result)

        final_text = modified_text
        for content in understood_contents:
            final_text = final_text.replace("[图片占位符]", content, 1)
    else:
        final_text = text

    parsed_text = await message_processor.parse_all_cq_codes(final_text)
    return parsed_text

async def process_messages(chat_id, websocket, mode):
    await asyncio.sleep(DEBOUNCE_TIME)
    messages = yuki.message_buffer.get(chat_id, [])
    if not messages: return

    raw_combined_text = "\n".join(messages)
    combined_text = await clean_cq_code(raw_combined_text)

    yuki.message_buffer[chat_id] = []
    if chat_id in yuki.buffer_tasks: del yuki.buffer_tasks[chat_id]

    history_manager.append_to_log(chat_id, "User/Group", combined_text)

    history_dict = history_manager.load()
    cid = str(chat_id)

    if cid not in history_dict:
        history_dict[cid] = [{"role": "system", "content": yuki.get_setting(mode)}]

    history_dict[cid].append({"role": "user", "content": combined_text})
    history_manager.save(history_dict)

    if mode == "group":
        if not await should_i_reply(history_dict[cid], combined_text):
            print("Yuki 决定继续潜水...")
            return

    try:
        print(f"Yuki 正在思考... (剩余精力: {yuki.energy:.1f})")
        response = yuki.client.chat.completions.create(model="deepseek-chat", messages=history_dict[cid])
        ans = response.choices[0].message.content

        if mode == "group":
            yuki.consume_energy()

        history_manager.append_to_log(chat_id, "Yuki", ans)
        history_dict[cid].append({"role": "assistant", "content": ans})
        history_manager.save(history_dict)

        sender = MessageSender(websocket)
        await sender.send(chat_id, ans, mode=mode)
    except Exception as e:
        print(f"Deepseek 调用失败: {e}")

    if len(history_dict[cid]) > DIARY_THRESHOLD:
        history_dict[cid] = await summarize_memory(chat_id, history_dict[cid])
        history_manager.save(history_dict)

async def main_logic(mode):
    print(f"连接 NapCat 服务端 | 模式: {mode} | 初始精力: {yuki.energy}")
    async for websocket in websockets.connect(NAPCAT_WS_URL):
        try:
            async for message in websocket:
                data = json.loads(message)
                if data.get("post_type") != "message": continue

                msg_type = data.get("message_type")
                if mode == "private" and msg_type == "private" and data.get("user_id") == TARGET_QQ:
                    manage_buffer(data.get("user_id"), data.get("raw_message"), websocket, "private")
                elif mode == "group" and msg_type == "group" and data.get("group_id") == TARGET_GROUP:
                    sender_name = data.get("sender", {}).get("nickname", "未知路人")
                    manage_buffer(data.get("group_id"), f"{sender_name}说: {data.get('raw_message')}", websocket, "group")
        except:
            await asyncio.sleep(3)

def manage_buffer(chat_id, content, websocket, mode):
    if chat_id not in yuki.message_buffer: yuki.message_buffer[chat_id] = []
    yuki.message_buffer[chat_id].append(content)
    if chat_id in yuki.buffer_tasks: yuki.buffer_tasks[chat_id].cancel()
    yuki.buffer_tasks[chat_id] = asyncio.create_task(process_messages(chat_id, websocket, mode))

if __name__ == "__main__":
    choice = input("1. 私聊 / 2. 群聊: ")
    asyncio.run(main_logic("private" if choice == "1" else "group"))