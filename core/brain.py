# brain.py
import datetime
from config import (
    INITIAL_ENERGY, MAX_ENERGY, RECOVERY_PER_MIN, COST_PER_REPLY
)
from core.prompts import YUKI_SETTING_PRIVATE, YUKI_SETTING_GROUP

class YukiState:
    def __init__(self):
        self.energy = INITIAL_ENERGY
        self.last_update = datetime.datetime.now()
        self.message_buffer = {}
        self.buffer_tasks = {}
        self.last_message_time = {}   # 记录每个群聊的最后用户消息时间戳
        self.writing_diary = set()            # 记录正在写日记的群聊ID，防止并发

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

    @staticmethod
    def get_setting(mode):
        return YUKI_SETTING_PRIVATE if mode == "private" else YUKI_SETTING_GROUP


