# connection.py
import json
import asyncio
import websockets
from typing import Optional, Dict
from config import NAPCAT_WS_URL

class BotConnector:
    def __init__(self, ws_url: str = NAPCAT_WS_URL):
        self.ws_url = ws_url
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
            print(f"网络异常: {e}")
            await self.close()
        return None

    async def listen(self):
        """Receiver: 持续监听消息的生成器"""
        while True:
            try:
                async with websockets.connect(self.ws_url) as ws:
                    self.websocket = ws
                    print(f"[Network] 已接通 NapCat 线路")
                    async for message in ws:
                        yield json.loads(message)
            except Exception as e:
                print(f"[Network] 线路中断，3秒后重连... ({e})")
                await asyncio.sleep(3)

    async def close(self):
        if self.websocket:
            await self.websocket.close()
            self.websocket = None


