# meme_processor.py
import aiohttp
import asyncio
import base64
import cv2
import numpy as np
import os
import re
import json
import hashlib
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception
from config import SILICONFLOW_API_KEY, SILICONFLOW_API_URL, CACHE_DIR, CACHE_FILE, MAX_CONCURRENT_MEME, DEBUG, \
    REQUEST_TIMEOUT


def log(msg):
    if DEBUG:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [表情理解] {msg}")


class MemeCache:
    def __init__(self):
        self.cache = {}
        if not os.path.exists(CACHE_DIR):
            os.makedirs(CACHE_DIR)
        self._load_cache()

    def _load_cache(self):
        """从文件加载缓存到内存"""
        # 使用 print 强制输出，不受 DEBUG 控制
        print(f"【缓存调试】重新加载缓存文件: {CACHE_FILE}")
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    new_cache = json.load(f)
                # 检查是否有变化
                if new_cache != self.cache:
                    print(f"【缓存调试】缓存已更新，原有 {len(self.cache)} 条，现在 {len(new_cache)} 条")
                    self.cache = new_cache
                else:
                    print(f"【缓存调试】缓存无变化，仍为 {len(self.cache)} 条")
            except Exception as e:
                print(f"【缓存调试】加载缓存失败: {e}")
                self.cache = {}
        else:
            print(f"【缓存调试】缓存文件不存在")
            self.cache = {}

    def save(self):
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
            print(f"【缓存调试】缓存已保存到 {CACHE_FILE}")
        except Exception as e:
            print(f"【缓存调试】保存缓存失败: {e}")

    def get(self, key):
        # 每次获取前重新加载文件，确保手动修改生效
        self._load_cache()
        value = self.cache.get(key)
        print(f"【缓存调试】获取 key: {key[:50]}... = {value}")
        return value

    def set(self, key, value):
        self.cache[key] = value

    def clear(self):
        self.cache = {}
        if os.path.exists(CACHE_FILE):
            os.remove(CACHE_FILE)
        print("【缓存调试】缓存已清空")


class MemeProcessor:
    def __init__(self):
        self.cache = MemeCache()
        self.semaphore = asyncio.Semaphore(MAX_CONCURRENT_MEME)

    def get_image_hash(self, image_data):
        return hashlib.md5(image_data).hexdigest()

    def compress_image(self, image_data, max_size=640, quality=70):
        try:
            nparr = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                log("无法读取图片")
                return None
            h, w = img.shape[:2]
            if max(h, w) > max_size:
                scale = max_size / max(h, w)
                new_w, new_h = int(w * scale), int(h * scale)
                img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
                log(f"尺寸从 {w}x{h} 压缩到 {new_w}x{new_h}")
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
            _, buffer = cv2.imencode('.jpg', img, encode_param)
            return base64.b64encode(buffer).decode('utf-8')
        except Exception as e:
            log(f"压缩失败: {e}")
            return None

    def is_retryable_error(self, exception):
        if isinstance(exception, asyncio.TimeoutError):
            return True
        if isinstance(exception, aiohttp.ClientError):
            return True
        if isinstance(exception, aiohttp.ClientResponseError) and exception.status in (429, 500, 502, 503, 504):
            return True
        return False

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        retry=retry_if_exception(is_retryable_error),
        reraise=True
    )
    async def call_api(self, b64_data):
        headers = {
            "Authorization": f"Bearer {SILICONFLOW_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "Qwen/Qwen3-VL-8B-Instruct",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_data}"}},
                        {"type": "text",
                         "text": "用词或短句描述这个表情包的核心意思，不超过10个字（如：送玫瑰，开心，害羞，难过，震惊，或者“趴在床上，无语，二次元角色”等）。如果是多文字图片，输出文字，可超过字数限制。长段文字直接输出“长段文字”"}
                    ]
                }
            ],
            "max_tokens": 50,
            "temperature": 0.7
        }
        async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
            async with session.post(SILICONFLOW_API_URL, json=payload, headers=headers) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    return result["choices"][0]["message"]["content"]
                else:
                    text = await resp.text()
                    log(f"API 返回错误 {resp.status}: {text[:200]}")
                    raise aiohttp.ClientResponseError(
                        request_info=resp.request_info,
                        history=resp.history,
                        status=resp.status,
                        message=text
                    )

    async def understand_from_url(self, img_url):
        # 强制重新加载缓存文件
        img_url = img_url.replace("&amp;", "&")
        cache_key = f"url:{img_url}"

        # 使用 print 强制输出调试信息
        print(f"【URL调试】完整URL: {img_url}")
        print(f"【URL调试】缓存key: {cache_key}")

        cached = self.cache.get(cache_key)
        if cached:
            print(f"【URL调试】命中URL缓存: {cached}")
            return f"[动画表情:{cached}]"

        try:
            print(f"【下载调试】开始下载图片")
            async with aiohttp.ClientSession() as session:
                async with session.get(img_url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        print(f"【下载调试】下载失败，HTTP {resp.status}")
                        return "[动画表情]"
                    content = await resp.read()
                    if len(content) > 10 * 1024 * 1024:
                        print("【下载调试】图片超过10MB，跳过")
                        return "[动画表情]"

            img_hash = self.get_image_hash(content)
            print(f"【哈希调试】图片哈希 = {img_hash}")

            # 检查哈希缓存
            cached = self.cache.get(img_hash)
            if cached:
                print(f"【哈希调试】命中哈希缓存: {cached}")
                return f"[动画表情:{cached}]"

            print("【处理调试】开始压缩...")
            b64_data = self.compress_image(content)
            if not b64_data:
                return "[动画表情]"

            print("【API调试】发送AI请求...")
            async with self.semaphore:
                analysis = await self.call_api(b64_data)

            print(f"【API调试】识别结果: {analysis}")
            clean_analysis = analysis.strip().replace('\n', ' ').replace('\r', '')

            # 保存到缓存
            self.cache.set(img_hash, clean_analysis)
            self.cache.set(cache_key, clean_analysis)
            self.cache.save()
            print(f"【缓存调试】已保存新结果: {clean_analysis}")

            return f"[动画表情:{clean_analysis}]"

        except Exception as e:
            print(f"【错误调试】理解表情失败: {e}")
            return "[动画表情]"


    def extract_urls_from_text(self, text):
        pattern = r'\[CQ:image,.*?url=([^,\]]+).*?\]'

        def replace_with_placeholder(match):
            return "[图片占位符]"

        modified_text = re.sub(pattern, replace_with_placeholder, text)
        urls = re.findall(pattern, text)
        return modified_text, urls