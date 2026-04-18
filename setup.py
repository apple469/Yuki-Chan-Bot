import os
import subprocess
import sys
from dotenv import load_dotenv, set_key

def ensure_dirs():
    """确保必要的文件夹存在"""
    dirs = ["./models", "./data", "./yuki_memory", "./logs"]
    for d in dirs:
        if not os.path.exists(d):
            os.makedirs(d)
            print(f"已创建文件夹: {d}")

def ensure_files():
    """确保必要的文件存在并有初始内容"""
    # 1. 自动生成初始黑名单
    if not os.path.exists("blacklist.txt"):
        with open("blacklist.txt", "w", encoding="utf-8") as f:
            # 写入你之前文件里提到的默认过滤词
            f.write("yuki\n主人\n哥哥\n池宇健\n人家")
        print("已生成初始 blacklist.txt")
    else:
        print("已存在 blacklist.txt，跳过")

def install_requirements():
    """自动安装依赖"""
    if input("\n是否安装/更新依赖插件? (y/n): ").lower() == 'y':
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
            print("依赖安装完成")
        except Exception as e:
            print(f"依赖安装失败，请手动执行 pip install -r requirements.txt\n错误: {e}")

def config_env_key():
    env_path = ".env"
    if not os.path.exists(env_path):
        with open(env_path, "w", encoding="utf-8") as f:
            f.write("# Yuki-Chan Configuration\n")

    keys_to_configure = [
        ("LLM_API_KEY", "请输入首选 LLM API Key: ", ""),
        ("BACKUP_API_KEY", "请输入备选 LLM API Key: ", ""),
        ("IMAGE_PROCESS_API_KEY", "请输入 图像处理 API Key: ", ""),
        ("NAPCAT_WS_URL", "请输入 NapCat WebSocket 地址 (默认: ws://127.0.0.1:3001): ", "ws://127.0.0.1:3001")
    ]

    for key, prompt, default in keys_to_configure:
        load_dotenv()
        if not os.getenv(key):
            value = input(prompt).strip()
            save_value = value if value else default
            if save_value:
                set_key(env_path, key, save_value)
                print(f"{key} 已保存: {save_value}")
        else:
            print(f"{key} 已存在，跳过")


def config_bot_settings():
    """配置机器人身份及目标对话对象"""
    env_path = ".env"
    settings = [
        ("ROBOT_NAME", "给BOT起个名字吧："),
        ("MASTER_NAME", "希望BOT称呼你的名字："),
        ("TARGET_QQ", "请输入私聊用 QQ 号: "),
        ("TARGET_GROUPS", "请输入目标群聊 QQ 号 (多个用逗号隔开): ")
    ]

    for key, prompt in settings:
        load_dotenv()
        # 修改点：同上
        if not os.getenv(key):
            value = input(prompt).strip()
            if value:
                set_key(env_path, key, value)
                print(f"{key} 已设置")
        else:
            print(f"{key} 已存在，跳过")

def quick_setup():
    print("\n>>> 步骤 1: 建立文件夹结构")
    ensure_dirs()
    ensure_files()

    print("\n>>> 步骤 2: 安装依赖文件")
    install_requirements()

    print("\n>>> 步骤 3: 配置 API 密钥")
    config_env_key()

    print("\n>>> 步骤 4: 配置机器人 QQ 号")
    config_bot_settings()

    # 2. 配置 RAG 嵌入模型
    print("\n>>> 步骤 5: 下载 RAG 嵌入模型")
    print("正在加载程序")
    from utils.download_model import download_model
    try:
        download_model()
    except Exception as e:
        print(f"模型下载环节出现问题: {e}")


if __name__ == "__main__":
    print("开始配置必要参数和环境")
    quick_setup()
    print("向导结束，请到 config.py 文件中手动修改使用模型名称和请求地址！")