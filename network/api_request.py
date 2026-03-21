import datetime
import time
from openai import AsyncOpenAI  # 必须换成这个
import asyncio
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL


class ApiCall:
    def __init__(self, api_key, base_url):
        self.fail_count = 0
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.last_fail_time = 0
        self.is_degraded = False

    def check_auto_recovery(self):
        """检查并尝试恢复熔断状态"""
        if self.is_degraded and (time.time() - self.last_fail_time > 600):
            self.is_degraded = False
            self.fail_count = 0
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] [System] 尝试恢复 TEATOP 主线路...")

    async def robust_api_call(self, messages, model="deepseek-chat", max_retries=3, **kwargs):
        """全异步化的稳健 API 调用"""
        self.check_auto_recovery()
        last_exception = None

        for attempt in range(max_retries):
            try:
                # 逻辑：如果降级，动态创建异步客户端
                if self.is_degraded or (attempt > 0 and max_retries > 1):
                    client = AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
                    model = "deepseek-chat"
                    if not self.is_degraded and attempt > 0:
                        self.is_degraded = True
                        self.last_fail_time = time.time()
                        print(f"[Critical] TEATOP 异常，已自动切至官方线路 (尝试 {attempt + 1})")
                else:
                    client = self.client  # 这里的 self.client 也要在 __init__ 里改成 AsyncOpenAI

                # --- 关键改动：使用 await ---
                response = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    **kwargs
                )
                self.fail_count = 0
                return response.choices[0].message.content

            except Exception as e:
                last_exception = e
                print(f"[API Error] 第 {attempt + 1} 次尝试失败: {e}")
                if attempt < max_retries - 1:
                    # --- 关键改动：非阻塞睡眠 ---
                    await asyncio.sleep(1)

        raise last_exception