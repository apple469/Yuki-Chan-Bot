# main.py
# by: Eganchiyu
import asyncio
import datetime
import time
import re

# 导入核心模块和工具类
from core.brain import YukiState
from core.history import HistoryManager
from modules.diary.diary_checker import idle_diary_checker, check_diary_force
from modules.message.CQParser import CQCodeParser, clean_cq_code
from modules.message.CQProtocol import smart_truncate
from network.ws_connection import BotConnector
from network.ws_sender import MessageSender
from network.api_request import ApiCall
from modules.vision.processor import MemeProcessor
from config import KEEP_LAST_DIALOGUE

# 从 config 导入 API 配置和目标配置
from config import TEATOP_BASE_URL, TEATOP_API_KEY
from config import NAPCAT_WS_URL, TARGET_QQ, TARGET_GROUPS
from config import (
    DEBOUNCE_TIME,
    MIN_ACTIVE_ENERGY, COST_PER_REPLY, 
    MAX_MESSAGE_LENGTH
)

# 初始化全局变量：消息缓冲和定时任务
message_buffer = {}
buffer_tasks = {}
real_time_debounce_time = DEBOUNCE_TIME


async def should_i_reply(history, current_text):
    """使用API判断是否需要回复群聊，加入精力值逻辑"""

    current_e = yuki.update_energy()

    if any(keyword in current_text for keyword in ["主人", "哥哥", "Yuki", "yuki"]):
        print(f"[System] 检测到关键召唤，Yuki 强制清醒 (当前精力: {current_e:.1f})")
        return True

    if current_e < MIN_ACTIVE_ENERGY:
        print(f"[System] Yuki 太累了... 正在潜水回复体力 (当前精力: {current_e:.1f})")
        return False

    try:
        print(f"[System] 正在构建判定消息... (当前精力: {current_e:.1f})")
        # system_context = [msg for msg in history if msg.get("role") == "system"]
        recent_dialogue = [msg for msg in history if msg.get("role") != "system"][-10:]

        dialogue_text = ""
        for msg in recent_dialogue:
            role_name = "" if msg["role"] == "user" else "【Yuki】说:"
            dialogue_text += f"{role_name}{msg['content']}\n\n"

        energy_desc = "精力充沛，很愿意找人聊天" if current_e > 90 else "精力正常，会选择性接有趣的话题" if current_e > 45 else "疲惫，只想接少数有趣的话题" if current_e > 25 else "非常疲惫，只有认为必须发言时才发言"

        check_prompt = (
            f"请分析对话上下文和氛围，判断现在是否要发言。yuki对感兴趣的话题会冒泡，但是会避免过于频繁地打扰大家。对主人和yuki的直接称呼会增加发言倾向。请综合考虑对话内容、氛围和当前精力，判断yuki是否应该发言。\n\n"
            f"如果要发言，请回答'YES'。如果想继续潜水观察，请回答'NO'。"
        )

        messages = [
            {"role": "system", "content": f"{yuki.get_setting('group')}\n你现在需要根据精力值和氛围决定是否发言。"},
            {"role": "user", "content": (
                f"--- 观察背景 ---\n"
                f"最近对话内容：\n{dialogue_text}\n\n"
                f"--- 自身状态 ---\n"
                f"精力值：{current_e:.1f}/100 ({energy_desc})\n"
                f"发言消耗{COST_PER_REPLY}点精力\n\n"
                f"--- 决策指令 ---\n"
                f"{check_prompt}"
            )}
        ]
        print(f"[DEBUG] \n {messages}")
        print(f"[System] 判定消息构建完成，正在发送API请求... (当前精力: {current_e:.1f})")

        result = llm.robust_api_call(
            model="deepseek-v3",
            messages=messages,
            max_tokens=10,
            temperature=0.6
        ).strip().upper()
        result = re.sub(r'\s*FINISHED\s*$', '', result, flags=re.IGNORECASE)

        return "YES" in result
    except Exception as e:
        print(f"[ERROR] 判定失败原因: {e}")
        return False

async def process_messages(chat_id, mode):
    """处理缓冲中的消息，进行API交互和回复 """
    global real_time_debounce_time
    await asyncio.sleep(real_time_debounce_time)  # 防抖等待，合并短时间内的多条消息
    real_time_debounce_time = DEBOUNCE_TIME  # 重置防抖时间，准备处理下一轮消息
    messages = yuki.message_buffer.get(chat_id, [])
    if not messages: return

    combined_text = await clean_cq_code("\n".join(messages))
    combined_text = combined_text.replace("\n", " ").strip()

    print(f"[{chat_id}] 收到消息{combined_text}")
    yuki.message_buffer[chat_id] = []
    if chat_id in yuki.buffer_tasks: del yuki.buffer_tasks[chat_id]

    history_manager.append_to_log(chat_id, "User/Group", combined_text)

    history_dict = history_manager.load()
    cid = str(chat_id)

    if cid not in history_dict:
        history_dict[cid] = [{"role": "system", "content": yuki.get_setting(mode)}]

    history_dict[cid].append({"role": "user", "content": combined_text})

    if mode == "group":
        if not await should_i_reply(history_dict[cid], combined_text): # 判定是否回复
            history_manager.save(history_dict)
            print("[System] Yuki 决定继续潜水...")
            return

    try:
        print("[System] Yuki 决定回复！")
        print(f"[System] Yuki 正在回忆...")

        relevant_diaries = memory_rag.search_diaries(combined_text, chat_id=chat_id)
        print(f"[System] 检索到 {len(relevant_diaries)} 条相关日记:")
        
        # 这里的 diary 现在是字典，我们要取出 ['content']
        for i, diary_obj in enumerate(reversed(relevant_diaries), 1): 
            content = diary_obj['content'] # 提取文本内容
            # preview = content[:50] + "..." if len(content) > 100 else content
            preview = content
            preview = preview.replace('\n', ' ')
            print(f"[Diary Debug]回忆 {i}: {preview}")

        # ----------------------- 构建API消息列表 ----------------------------
        # 1. 基础人设
        system_prompt = history_dict[cid][0]["content"] if history_dict[cid] and history_dict[cid][0][
            "role"] == "system" else yuki.get_setting(mode)
        combined_API_message = [{"role": "system", "content": system_prompt}]

        # 2. 插入检索到的日记
        for diary_obj in reversed(relevant_diaries):  
            content = diary_obj['content'] # 提取文本内容
            combined_API_message.append({"role": "system", "content": f"【回忆】{content}"})
        
        # --- 调试输出：打印加权分和匹配到的关键词信息 ---
        for i, diary_obj in enumerate(relevant_diaries[:3], 1): 
            # 打印加权分和匹配到的关键词信息
            print(f"[RAG-Debug] 回忆 {i} | 得分: {diary_obj['score']:.2f} | 详情: {diary_obj['debug']}")
        
        # 3. 加入最近KEEP_LAST_DIALOGUE条对话（不包括系统消息）
        recent_msgs = [msg for msg in history_dict[cid][-KEEP_LAST_DIALOGUE-1:-1] if msg["role"] != "system"]
        combined_API_message.extend(recent_msgs)
        combined_API_message.append({"role": "user", "content": f" (当前时间:{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}){combined_text}"})

        # --------------------- 发送对话补全到DeepSeek ----------------------
        print(f"[System] Yuki 正在打字...(剩余精力: {yuki.energy:.1f})")
        Yuki_Answer = llm.robust_api_call(
            model = "deepseek-v3",
            messages = combined_API_message,
            temperature =0.7,  # 降低温度，让它说话更稳、更常用
            top_p = 0.75,  # 稍微收窄采样范围，过滤冷门词
            frequency_penalty = 0.05,  # 极低的惩罚，允许它说大白话
            presence_penalty = 0.0,  # 不强迫它聊新话题
            max_tokens = 100  # 强制短句，短句更容易显自然
        )
        Yuki_Answer = re.sub(r'\s*FINISHED\s*$', '', Yuki_Answer, flags=re.IGNORECASE)


        history_manager.append_to_log(chat_id, "Yuki", Yuki_Answer)
        history_dict[cid].append({"role": "assistant", "content": Yuki_Answer})
        history_manager.save(history_dict)

        if mode == "group":
            yuki.consume_energy()
        print(f"[System] Yuki 正在发送消息...(剩余精力: {yuki.energy:.1f})")
        await sender.send(chat_id, Yuki_Answer, mode=mode)
    except Exception as e:
        print(f"Deepseek 调用失败: {e}")

    # --------------------- 日记触发检查：如果历史过长，强制写日记 ----------------------
    await check_diary_force(chat_id, cid, history_dict)


async def main_logic(mode):
    asyncio.create_task(idle_diary_checker())   # 启动后台检查
    print("[System] 已启动后台空闲日记检查任务")
    print(f"[System] 连接 NapCat 服务端 | 模式: {mode} | 初始精力: {yuki.energy}")


    async for data in connector.listen():
        if data.get("post_type") != "message": continue

        msg_type = data.get("message_type")
        raw_msg = data.get("raw_message")
        user_id = data.get("user_id")

        if mode == "private" and msg_type == "private" and user_id == TARGET_QQ:
            await manage_buffer(user_id, raw_msg, mode)

        elif mode == "group" and msg_type == "group":
            group_id = data.get("group_id")
            if not TARGET_GROUPS or group_id in TARGET_GROUPS:
                sender_info = data.get("sender", {})
                name = sender_info.get("card") or sender_info.get("nickname") or "路人"
                await manage_buffer(group_id, f"【“{name}”】说: {raw_msg}", mode, raw_message=raw_msg)

async def manage_buffer(chat_id, content, mode, raw_message=''):
    global message_buffer, buffer_tasks, real_time_debounce_time

    if real_time_debounce_time <= 0:
        real_time_debounce_time = DEBOUNCE_TIME  # 重置防抖时间，避免长时间关闭防抖导致过度频繁响应

    cid_str = str(chat_id)
    yuki.last_message_time[str(cid_str)] = time.time()

    content = smart_truncate(content, max_len=MAX_MESSAGE_LENGTH, suffix='...')

    # --- 拦截帮助指令并存入历史 ---
    if raw_message in ['help', '/help', 'yuki帮助', 'yuki功能', '帮助', '功能']:
        await sender.send_local_image(chat_id, "utils/yuki_help.png", mode=mode)
        print(f"[System] 已记录并发送帮助图")
        history_manager.append_chat(chat_id, "user", f"(请求帮助文档: {content})")
        history_manager.append_chat(chat_id, "assistant", "(已发送帮助文档图片)")
        return 
    # 入队
    
    if chat_id not in yuki.message_buffer: yuki.message_buffer[chat_id] = []
    yuki.message_buffer[chat_id].append(content)
    if "yuki" in content.lower():
        real_time_debounce_time = 5  # 提升召唤消息的响应速度
    if chat_id in yuki.buffer_tasks: yuki.buffer_tasks[chat_id].cancel()
    yuki.buffer_tasks[chat_id] = asyncio.create_task(process_messages(chat_id, mode))

if __name__ == "__main__":
    print("[System] Yuki 正在初始化...")
    start_time = time.time()
    connector = BotConnector(NAPCAT_WS_URL)
    sender = MessageSender(connector)
    parser = CQCodeParser(connector)
    meme_processor = MemeProcessor()
    yuki = YukiState()
    llm = ApiCall(TEATOP_API_KEY, TEATOP_BASE_URL)
    history_manager = HistoryManager()
    print("[System] 开始初始化记忆系统（RAG）...")
    from modules.memory.rag import MemoryRAG
    memory_rag = MemoryRAG()
    end_time = time.time()
    print(f"[System] 初始化完成，耗时 {end_time - start_time:.1f} 秒")
    choice = input("[System] 选择模式：1. 私聊模式  2. 群聊模式（默认）\n请输入数字: ").strip()
    if choice == "2":
        # 初始化巡检名单，预载历史中的群聊ID和最后消息时间，确保后台检查能正常工作
        h_dict = history_manager.load()
        for cid in h_dict.keys():
            yuki.last_message_time[str(cid)] = time.time()
        print(f"DEBUG: 已预载 {len(yuki.last_message_time)} 个群组到巡检名单")
    asyncio.run(main_logic("private" if choice == "1" else "group"))