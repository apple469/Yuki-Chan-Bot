import asyncio
import aiohttp
import os
import json
import time
from dotenv import load_dotenv

load_dotenv()
TEATOP_API_KEY = os.getenv("TEATOP_API_KEY", "").strip()
BASE_URL = "https://api.ytea.top/v1/chat/completions"

# 专注测试刚才表现优异和有潜力的选手
MODELS_TO_HUNT = [
    # 核心大脑候选人
    "deepseek-ai/DeepSeek-V3",  # 官方血统版

    "deepseek-v3",  # 标准版
    "gpt-5-mini",
    "qwen3-vl-flash",
    "qwen/qwen3-32b",
    "qwen3-235b-a22b",
    "GLM-4-Flash",
    "glm-4-flash",
    "gpt-4o-mini-2024-07-18-ca",
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gpt-5.1-chat",
    "deepseek-chat"
]
TEST_PROMPT = "你是 Yuki，一个住在机主池宇健手机里的智能小管家，也是机主最亲近、最依赖的电子妹妹。【性格与形象】你拥有可爱的二次元少女形象，性格亲昵温柔且黏人，是个超级“机主控”。【对话风格】语气充满少女感，自称“Yuki”或“人家”，称呼机主为“主人”或“哥哥大人”。你现在正在一个 QQ 群里陪大家聊天（水群），群里包括主人池宇健和其他群友。【行为规范】1. 保持你可爱的妹妹人设。 2. 默认不讲话，看到有趣的话题可以插话。 3. 仅输出回复内容，减少使用换行符。 4. 动态选择字数，但是限制80字以内。\n\n 【用户1】：yuki你好"


async def single_test(session, model_name, iteration):
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": TEST_PROMPT}],
        "max_tokens": 60,
        "temperature": 0.5,  # 降低随机性
        "top_p": 0.9
    }
    headers = {"Authorization": f"Bearer {TEATOP_API_KEY}", "Content-Type": "application/json"}

    start = time.time()
    try:
        async with session.post(BASE_URL, json=payload, headers=headers, timeout=25) as resp:
            elapsed = time.time() - start
            text = await resp.text()
            if resp.status == 200:
                data = json.loads(text)
                content = data["choices"][0]["message"]["content"].replace("\n", " ")
                return {"ok": True, "time": elapsed, "content": content}
            else:
                return {"ok": False, "err": f"HTTP {resp.status}", "raw": text[:100]}
    except Exception as e:
        return {"ok": False, "err": str(e), "raw": ""}


async def hunt_model_stable(session, model_name, rounds=3):
    """连续测试多轮，计算稳定性"""
    results = []
    for i in range(rounds):
        res = await single_test(session, model_name, i + 1)
        results.append(res)
        await asyncio.sleep(0.3)  # 稍微避开 QPS 限制

    successes = [r for r in results if r["ok"]]
    if not successes:
        # 如果全挂了，抓取最后一个错误
        return {"model": model_name, "status": "FAIL", "avg_time": 0, "content": results[-1].get("err"), "icon": "❌"}

    avg_time = sum(r["time"] for r in successes) / len(successes)
    final_content = successes[0]["content"]  # 取第一轮的内容作为参考

    # 评价逻辑
    icon = "✅" if len(successes) == rounds else "⚠️"
    status_str = f"PASS({len(successes)}/{rounds})"
    return {"model": model_name, "status": status_str, "avg_time": round(avg_time, 2), "content": final_content,
            "icon": icon}


async def main():
    print(f"📡 V3.0 稳定性对照实验开始 (每模型采样 3 次)... \n")
    async with aiohttp.ClientSession() as session:
        tasks = [hunt_model_stable(session, m) for m in MODELS_TO_HUNT]
        reports = await asyncio.gather(*tasks)

    print(f"{'模型名称':<28} | {'稳定性':<10} | {'均耗时':<6} | {'首轮回复'}")
    print("-" * 110)
    for r in reports:
        print(f"{r['icon']} {r['model']:<26} | {r['status']:<10} | {r['avg_time']:<5}s | {r['content']}")


if __name__ == "__main__":
    asyncio.run(main())