from datetime import datetime
from config import DEBUG

def log(msg):
    if DEBUG:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [表情理解] {msg}")
    else:return
