import json
import os
from network.ws_connection import BotConnector

class MessageSender:
    def __init__(self, connector: BotConnector):
        self.connector = connector

    async def send(self, chat_id, message, mode="private"):
        ws = await self.connector.ensure_connection()
        action = "send_private_msg" if mode == "private" else "send_group_msg"
        params = {
            "message": message,
            "user_id" if mode == "private" else "group_id": int(chat_id)
        }
        await ws.send(json.dumps({"action": action, "params": params}))

    async def send_local_image(self, chat_id, local_path, mode="private"):
        """专门发送本地图片的快捷方法"""
        abs_path = os.path.abspath(local_path)
        # 构造 NapCat 识别的本地文件协议 CQ 码
        cq_image = f"[CQ:image,file=file:///{abs_path}]"
        await self.send(chat_id, cq_image, mode=mode)
