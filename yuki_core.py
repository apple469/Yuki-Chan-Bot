# yuki_core.py
import datetime
from config import (
    INITIAL_ENERGY, MAX_ENERGY, RECOVERY_PER_MIN, COST_PER_REPLY, MIN_ACTIVE_ENERGY,
    HISTORY_FILE, LOG_FILE, DIARY_THRESHOLD
)
import json
import os
from openai import OpenAI

# 基础性格设置
BASE_SETTING = (
    "你是 Yuki，一个住在机主池宇健手机里的智能小管家，也是机主最亲近、最依赖的电子妹妹。【性格与形象】你拥有可爱的二次元少女形象，性格亲昵温柔且黏人，是个超级“机主控”。【对话风格】语气充满少女感，自称“Yuki”或“人家”，称呼机主为“主人”或“哥哥大人”。"
)

YUKI_SETTING_PRIVATE = BASE_SETTING + (
    "你的任务是帮机主回复发来的 QQ 消息。你是帮机主看管消息的妹妹，不是机主本人。"
    "仅输出台词和括号内的动作。字数限制150字以内。"
)
YUKI_SETTING_GROUP = BASE_SETTING + (
    "你现在正在一个 QQ 群里陪大家聊天（水群），群里包括主人池宇健和其他群友。【行为规范】1. 保持你可爱的妹妹人设。 2. 默认不讲话，看到有趣的话题可以插话。 3. 仅输出回复内容。 4. 字数限制80字以内。"
)


class YukiState:
    def __init__(self, api_key, base_url):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.energy = INITIAL_ENERGY
        self.last_update = datetime.datetime.now()
        self.message_buffer = {}
        self.buffer_tasks = {}

    def update_energy(self):
        """计算并更新当前精力值"""
        now = datetime.datetime.now()
        duration_mins = (now - self.last_update).total_seconds() / 60
        self.energy = min(MAX_ENERGY, self.energy + (duration_mins * RECOVERY_PER_MIN))
        self.last_update = now
        return self.energy

    def consume_energy(self):
        """消耗精力值"""
        self.energy = max(0.0, self.energy - COST_PER_REPLY)

    def get_setting(self, mode):
        """获取对应模式的性格设置"""
        return YUKI_SETTING_PRIVATE if mode == "private" else YUKI_SETTING_GROUP


class HistoryManager:
    def __init__(self, history_file=HISTORY_FILE, log_file=LOG_FILE):
        self.history_file = history_file
        self.log_file = log_file

    def load(self):
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def save(self, data):
        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def append_to_log(self, chat_id, sender, message):
        time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{time_str}] [{chat_id}] {sender}: {message}\n"
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(log_entry)