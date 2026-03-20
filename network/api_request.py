import datetime
import time
from openai import OpenAI
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL


class ApiCall:
    def __init__(self, api_key, base_url):
        self.fail_count = 0
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.last_fail_time = 0
        self.is_degraded = False

    def check_auto_recovery(self):
        """检查并尝试恢复熔断状态"""
        if self.is_degraded and (time.time() - self.last_fail_time > 600):
            self.is_degraded = False
            self.fail_count = 0
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] [System] 尝试恢复 TEATOP 主线路...")

    def robust_api_call(self, messages, model="deepseek-chat", max_retries=3, **kwargs):
        """统一的稳健 API 调用逻辑"""
        self.check_auto_recovery()

        last_exception = None
        for attempt in range(max_retries):
            try:
                # 决定使用哪个客户端
                if self.is_degraded or (attempt > 0 and max_retries > 1):
                    # 降级模式或非首次尝试失败后，直连 DeepSeek 官方
                    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
                    model = "deepseek-chat"
                    if not self.is_degraded and attempt > 0:
                        self.is_degraded = True
                        self.last_fail_time = time.time()
                        print(f"[Critical] TEATOP 异常，已自动切至官方线路 (尝试 {attempt + 1})")
                else:
                    client = self.client

                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    **kwargs
                )
                self.fail_count = 0  # 成功则重置
                return response.choices[0].message.content

            except Exception as e:
                last_exception = e
                if not self.is_degraded:
                    self.fail_count += 1
                print(f"[API Error] 第 {attempt + 1} 次尝试失败: {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)  # 同步调用下简单等待

        raise last_exception