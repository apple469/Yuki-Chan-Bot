# message_utils.py
import re
import json
import asyncio
import websockets
from typing import Optional, Dict
from config import NAPCAT_WS_URL


class CQCodeParser:
    def __init__(self, ws_url: str = NAPCAT_WS_URL):
        self.ws_url = ws_url
        self.nickname_cache: Dict[str, str] = {}
        self.websocket = None

    async def ensure_connection(self):
        if self.websocket is None:
            self.websocket = await websockets.connect(self.ws_url)
        return self.websocket

    async def send_request(self, action: str, params: dict, echo: str) -> Optional[Dict]:
        try:
            ws = await self.ensure_connection()
            request = {"action": action, "params": params, "echo": echo}
            await ws.send(json.dumps(request))
            try:
                while True:
                    response = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    data = json.loads(response)
                    if data.get("echo") == echo:
                        return data
            except asyncio.TimeoutError:
                print(f"请求 {action} 超时")
        except Exception as e:
            print(f"发送请求失败: {e}")
            try:
                await self.close()
            except:
                pass
            self.websocket = None
        return None

    async def get_user_info(self, user_id: str) -> Optional[Dict]:
        try:
            uid = int(user_id) if user_id.isdigit() else user_id
            response = await self.send_request(
                "get_stranger_info",
                {"user_id": uid, "no_cache": False},
                f"get_user_{user_id}"
            )
            if response and response.get("retcode") == 0:
                return response.get("data")
        except Exception as e:
            print(f"获取用户信息失败: {e}")
        return None

    async def get_user_nickname(self, user_id: str) -> str:
        if user_id in self.nickname_cache:
            return self.nickname_cache[user_id]
        if user_id.lower() == "all":
            return "全体成员"
        user_info = await self.get_user_info(user_id)
        if user_info and user_info.get("nickname"):
            nickname = user_info["nickname"]
            self.nickname_cache[user_id] = nickname
            return nickname
        return f"用户{user_id}"

    async def parse_at_cq_codes(self, text: str) -> str:
        if not text:
            return text
        pattern = r'\[CQ:at,qq=(\d+|all)[^\]]*\]'
        matches = list(re.finditer(pattern, text))
        if not matches:
            return text
        result = text
        for match in reversed(matches):
            cq_code = match.group(0)
            qq = match.group(1)
            nickname = await self.get_user_nickname(qq)
            result = result[:match.start()] + f"@{nickname}" + result[match.end():]
        return result

    async def parse_all_cq_codes(self, text: str) -> str:
        text = await self.parse_at_cq_codes(text)
        text = re.sub(r'\[CQ:image[^\]]*\]', '[图片]', text)
        text = re.sub(r'\[CQ:face[^\]]*\]', '[表情]', text)
        text = re.sub(r'\[CQ:record[^\]]*\]', '[语音]', text)
        text = re.sub(r'\[CQ:video[^\]]*\]', '[视频]', text)
        text = re.sub(r'\[CQ:file[^\]]*\]', '[文件]', text)
        return text

    async def close(self):
        if self.websocket:
            await self.websocket.close()
            self.websocket = None


class MessageSender:
    def __init__(self, websocket):
        self.websocket = websocket

    async def send(self, chat_id, message, mode="private"):
        action = "send_private_msg" if mode == "private" else "send_group_msg"
        params = {"message": message, "user_id" if mode == "private" else "group_id": int(chat_id)}
        await self.websocket.send(json.dumps({"action": action, "params": params}))