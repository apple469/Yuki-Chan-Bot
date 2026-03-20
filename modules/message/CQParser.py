from typing import Dict

from main import meme_processor, llm, parser
from modules.message.GetMeta import MetaGetter
from network.ws_connection import BotConnector
from modules.message.CQProtocol import CQProtocol

class CQCodeParser:
    """
    调用CQMetaGetter获取原json格式数据，解码数据后调用CQProtocol替换CQ码，返回解析后的原字符串
    """
    def __init__(self, connector: BotConnector):
        self.connector = connector
        self.nickname_cache: Dict[str, str] = {}
        self.protocol = CQProtocol()
        self.meta = MetaGetter(connector)

    async def get_user_nickname(self, user_id: str) -> str:
        """
        调用CQMetaGetter获取用户昵称

        """
        if user_id in self.nickname_cache:
            return self.nickname_cache[user_id]
        if user_id.lower() == "all":
            return "全体成员"
        user_info = await self.meta.get_user_info(user_id)
        if user_info and user_info.get("nickname"):
            nickname = user_info["nickname"]
            self.nickname_cache[user_id] = nickname
            return nickname
        return f"用户{user_id}"

    async def parse_At_CQ_codes(self, text: str) -> str:
        uids = self.protocol.extract_at_uids(text)
        for uid in set(uids):
            name = await self.get_user_nickname(uid)
            text = self.protocol.replace_at_placeholder(text, uid, name)
        return text

    async def parse_Reply_CQ_codes(self, content: str) -> str:
        """替换文本中所有的回复CQ码"""
        reply_buffer = self.protocol.extract_reply_matches(content)
        for mid in reply_buffer:
            text_data = await self.meta.get_reply_text(mid)
            reply_data = self.protocol.replace_reply_placeholder(text_data)
            content = content.replace(f"[CQ:reply,id={mid}]", reply_data)
        return content

    async def parse_all_cq_codes(self, text: str) -> str:
        text = await self.parse_Reply_CQ_codes(text)
        text = await self.parse_At_CQ_codes(text)
        text = self.protocol.replace_other_CQ_codes(text)
        return text


async def clean_cq_code(text):
    """处理消息中的CQ码，提取图片URL并调用meme_processor理解，返回最终文本"""
    modified_text, image_urls = meme_processor.extract_urls_from_text(text)

    if image_urls:
        understood_contents = []
        for url in image_urls:
            result = await meme_processor.understand_from_url(url, llm)
            understood_contents.append(result)

        final_text = modified_text
        for content in understood_contents:
            final_text = final_text.replace("[图片占位符]", content, 1)
    else:
        final_text = text

    parsed_text = await parser.parse_all_cq_codes(final_text)
    return parsed_text
