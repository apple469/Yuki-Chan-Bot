import datetime
import json
import os

from config import HISTORY_FILE, LOG_FILE


class HistoryManager:
    def __init__(self, history_file=HISTORY_FILE, log_file=LOG_FILE):
        self.history_file = history_file
        self.log_file = log_file

    def load(self):
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"加载文件发生错误：{e}")
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

    def inject_whisper(self, chat_id, message):
        """向指定对话注入悄悄话"""
        history = self.load()
        cid = str(chat_id)

        if cid in history:
            whisper_msg = {
                "role": "assistant",
                "content": f"【池宇健对yuki的悄悄话】：{message}"
            }
            history[cid].append(whisper_msg)
            self.save(history)
            print(f"悄悄话已注入到对话 {chat_id}: {message}")
            return True
        else:
            print(f"对话 {chat_id} 不存在")
            return False
