# core/brain.py
import datetime
from core.prompts import YUKI_SETTING_PRIVATE, YUKI_SETTING_GROUP
from config import (
    INITIAL_ENERGY, MAX_ENERGY, RECOVERY_PER_MIN, COST_PER_REPLY
)

class YukiState:
    def __init__(self):
        self.energy = INITIAL_ENERGY
        self.last_update = datetime.datetime.now()
        self.message_buffer = {}  # chat_id: [messages]
        self.buffer_tasks = {}    # chat_id: task
        self.last_message_time = {} # chat_id: timestamp
        self.writing_diary = set()  # chat_id

    @staticmethod
    def get_setting(mode):
        return YUKI_SETTING_PRIVATE if mode == "private" else YUKI_SETTING_GROUP

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

    def pop_buffer(self, chat_id):
        """原子化取出并清空缓冲区"""
        msgs = self.message_buffer.get(chat_id, [])
        self.message_buffer[chat_id] = []
        if chat_id in self.buffer_tasks:
            del self.buffer_tasks[chat_id]
        return msgs