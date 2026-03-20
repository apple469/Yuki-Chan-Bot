import re
from typing import Dict, Optional

from network.connection import BotConnector


class CQCodeParser:
    def __init__(self, connector: BotConnector):
        # 💡 这里不再用 super()，而是直接把工具存起来
        self.connector = connector
        self.nickname_cache: Dict[str, str] = {}

    async def get_user_info(self, user_id: str) -> Optional[Dict]:
        try:
            uid = int(user_id) if user_id.isdigit() else user_id
            response = await self.connector.send_request(
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

    async def get_reply_text(self, msg_id: str) -> str:
        """获取被回复消息的文本内容"""
        try:
            # 使用已有的 send_request 访问 NapCat 接口
            res = await self.connector.send_request("get_msg", {"message_id": int(msg_id)}, f"rp_{msg_id}")
            if res and res.get("status") == "ok":
                data = res.get("data", {})
                sender = data.get("sender", {}).get("nickname", "人")
                text = re.sub(r'\[CQ:.*?\]', '', data.get("raw_message", "")) # 只要前20字文本
                return f"【引用{sender}的消息: {text}】"
        except Exception as e:
            print(f"获取回复消息失败: {e}")
            pass
        return "[引用消息]"

    async def replace_reply_all(self, content: str) -> str:
        """替换文本中所有的回复CQ码"""
        matches = re.findall(r'\[CQ:reply,id=(\d+)\]', content)
        for mid in matches:
            rep_text = await self.get_reply_text(mid)
            content = content.replace(f"[CQ:reply,id={mid}]", rep_text)
        return content

    async def parse_all_cq_codes(self, text: str) -> str:
        text = await self.replace_reply_all(text)
        text = await self.parse_at_cq_codes(text)
        text = re.sub(r'\[CQ:image[^\]]*\]', '[图片]', text)
        text = re.sub(r'\[CQ:face[^\]]*\]', '[表情]', text)
        text = re.sub(r'\[CQ:record[^\]]*\]', '[语音]', text)
        text = re.sub(r'\[CQ:video[^\]]*\]', '[视频]', text)
        text = re.sub(r'\[CQ:file[^\]]*\]', '[文件]', text)
        text = re.sub(r'\[CQ:json[^\]]*\]', '[小程序]', text)

        return text
