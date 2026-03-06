# config.py
import aiohttp
import os

# ================= API配置 =================
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY") # 填入自己的 API_KEY
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY") # 填入自己的 API_KEY
SILICONFLOW_API_URL = "https://api.siliconflow.cn/v1/chat/completions"

# ================= 连接配置 =================
NAPCAT_WS_URL = "ws://127.0.0.1:3001"

# ================= 目标配置 =================
TARGET_QQ = 3580583831
# TARGET_GROUP = 1034986009
TARGET_GROUP = 1085409165

# ================= 文件配置 =================
HISTORY_FILE = "chat_history.json"
LOG_FILE = "yuki_chat_all_nekonochi.log"
CACHE_DIR = "meme_cache"
CACHE_FILE = "meme_cache.json"

# ================= 时间配置 =================
DEBOUNCE_TIME = 1
DIARY_THRESHOLD = 50
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=60, connect=10, sock_read=30)

# ================= 精力值配置 =================
INITIAL_ENERGY = 100.0
MAX_ENERGY = 100.0
RECOVERY_PER_MIN = 0.8
COST_PER_REPLY = 5.0
MIN_ACTIVE_ENERGY = 15.0

# ================= 并发配置 =================
MAX_CONCURRENT_MEME = 1

# ================= 调试配置 =================
DEBUG = True