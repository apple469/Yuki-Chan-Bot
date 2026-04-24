import os
import shutil
import subprocess
import sys
from config import _add_inline_comments, generate_default_config
import yaml

# uv 环境提示：如果检测到 uv 但未在虚拟环境中运行，给出友好提示
if shutil.which("uv") and sys.prefix == sys.base_prefix:
    venv_python = os.path.join(".venv", "Scripts", "python.exe") if sys.platform == "win32" else os.path.join(".venv", "bin", "python")
    if os.path.exists(venv_python):
        print("💡 检测到 uv 虚拟环境存在，但未激活。")
        print("   请使用以下命令运行 setup.py：")
        print(f"   uv run python setup.py")
        print("   或先激活虚拟环境后再运行。\n")

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
            f.write("yuki\n主人\n哥哥\n池宇健\n人家")
        print("已生成初始 blacklist.txt")
    else:
        print("📝 已存在 blacklist.txt，跳过")

    # 2. 自动生成 .gitignore
    gitignore_content = """.idea/
.env
.vscode/
__pycache__/
yuki_memory/
models/
data/
project_for_ai.txt
models.zip
skills/
core/skills
logs/
core/tasks
configs/config.yaml
.venv/
"""
    if not os.path.exists(".gitignore"):
        with open(".gitignore", "w", encoding="utf-8") as f:
            f.write(gitignore_content)
        print("🛡️ 已生成 .gitignore")
    else:
        with open(".gitignore", "r", encoding="utf-8") as f:
            existing = f.read()
        if "configs/*" not in existing:
            with open(".gitignore", "a", encoding="utf-8") as f:
                f.write("\nconfigs/*\n")
            print("🛡️ 已追加 configs/* 到 .gitignore")
        else:
            print("已存在 .gitignore，跳过")

        # 3. 自动生成/升级 configs/config.yaml
        os.makedirs("configs", exist_ok=True)
        config_path = "configs/config.yaml"


        if not os.path.exists(config_path):
            with open(config_path, "w", encoding="utf-8") as f:
                f.write(generate_default_config())
            print("[Config] 已生成初始 configs/config.yaml")
        else:
            with open(config_path, "r", encoding="utf-8") as f:
                content = f.read()
            if "# Yuki-Chan Bot" not in content:
                # 这是一个旧格式文件，我们进行“结构化升级”
                old_data = _load_yaml()
                # 备份
                shutil.copy(config_path, config_path + ".old")
                # 直接用新模板覆盖，然后调用我们下方的 _save_yaml 把旧数据刷进去
                with open(config_path, "w", encoding="utf-8") as f:
                    f.write(generate_default_config())
                _save_yaml(old_data)
                print("[Config] 已将旧版配置升级为带注释的新格式，旧文件已备份为 .old")
            else:
                print("[Config] 已存在 configs/config.yaml，跳过")
def install_requirements():
    """自动安装依赖（优先使用 uv，回退到 pip）"""
    if input("\n是否现在安装/更新依赖插件? (y/n): ").lower() != 'y':
        return

    has_uv = shutil.which("uv") is not None
    try:
        if has_uv:
            print("🚀 检测到 uv，使用 uv 安装依赖...")
            subprocess.check_call(["uv", "sync"])
            print("✅ 依赖安装完成（via uv）")
        else:
            print("📦 未检测到 uv，使用 pip 安装依赖...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
            print("✅ 依赖安装完成（via pip）")
    except Exception as e:
        print(f"❌ 依赖安装失败\n错误: {e}")
        print("💡 建议手动执行: uv sync  或  pip install -r requirements.txt")


def migrate_from_env():
    """手动解析 .env 文件并强制迁移空值"""
    from config import _ATTR_MAP

    env_path = ".env"
    if not os.path.exists(env_path):
        return

    # 手动简单解析 .env (避免依赖第三方库)
    env_data = {}
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env_data[k.strip()] = v.strip().strip('"').strip("'")

    cfg = _load_yaml()
    migrated_count = 0

    # 映射表
    mapping = {
        "LLM_API_KEY": ("api", "llm_api_key"),
        "IMAGE_PROCESS_API_KEY": ("api", "image_process_api_key"),
        "NAPCAT_WS_URL": ("connection", "napcat_ws_url"),
        "NAPCAT_WS_TOKEN": ("connection", "napcat_ws_token"),
        "TARGET_QQ": ("target", "qq"),
        "TARGET_GROUPS": ("target", "groups"),
    }

    # 机器人身份（允许覆盖，因为旧版 .env 中通常是用户自定义的）
    if env_data.get("ROBOT_NAME"):
        cfg["robot_name"] = env_data["ROBOT_NAME"]
        print(f"  - [已迁移] ROBOT_NAME -> robot_name")
        migrated_count += 1
    if env_data.get("MASTER_NAME"):
        cfg["master_name"] = env_data["MASTER_NAME"]
        print(f"  - [已迁移] MASTER_NAME -> master_name")
        migrated_count += 1

    def set_nested(data, path, value):
        curr = data
        for key in path[:-1]:
            curr = curr.setdefault(key, {})
        curr[path[-1]] = value

    for env_key, yaml_path in mapping.items():
        val = env_data.get(env_key)
        if val:
            # 只有当 yaml 里没值或者是默认空字符串时，才覆盖
            current_val = cfg
            for p in yaml_path: current_val = current_val.get(p, {}) if isinstance(current_val, dict) else None

            if not current_val or current_val == "":
                # 类型转换
                if env_key == "TARGET_QQ": val = int(val)
                if env_key == "TARGET_GROUPS": val = [int(x.strip()) for x in val.split(",") if x.strip()]

                set_nested(cfg, yaml_path, val)
                print(f"  - [已迁移] {env_key} -> {'.'.join(yaml_path)}")
                migrated_count += 1

    if migrated_count > 0:
        _save_yaml(cfg)
        print(f"✅ 成功从 .env 同步了 {migrated_count} 项配置")


def _load_yaml():
    import yaml
    path = "configs/config.yaml"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def _save_yaml(data):
    """
    开发者方案：利用 config.py 的模板生成技术写回。
    """
    # 确保从 config.py 导入必要的常量和格式化函数


    # 1. 加载当前物理文件内容作为基准 (调用 setup.py 里的 _load_yaml)
    current_cfg = _load_yaml()

    # 2. 递归合并新数据到 current_cfg
    def deep_update(base, updater):
        for k, v in updater.items():
            if isinstance(v, dict) and k in base and isinstance(base[k], dict):
                deep_update(base[k], v)
            else:
                base[k] = v

    deep_update(current_cfg, data)

    # 3. 重新生成带注释的文本
    # 注意：这里使用 yaml.dump 生成纯文本，再通过 config.py 里的 _add_inline_comments 补全注释
    raw_yaml = yaml.dump(
        current_cfg,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False
    )
    # 调用 config.py 里的函数来美化并添加注释
    final_content = _add_inline_comments(raw_yaml)

    # 添加文件头
    header = "# Yuki-Chan Bot 配置文件\n# 所有配置均在此文件管理，请勿提交到 Git\n# 本文件已在 .gitignore 中\n\n"

    with open("configs/config.yaml", "w", encoding="utf-8") as f:
        f.write(header + final_content)

def config_yaml(mode):
    """配置 API Key 和 QQ 号，完全弃用正则，改为直接操作对象"""
    cfg = _load_yaml()
    changed = False

    print("\n--- 配置机器人身份 ---")
    robot_name = input("给 bot 起个名字吧[默认 yuki]: ").strip()
    if robot_name:
        cfg["robot_name"] = robot_name
        changed = True
        print(f"  ✓ robot_name 已设置为 {robot_name}")

    master_name = input("bot 如何称呼你呢 [默认 主人]: ").strip()
    if master_name:
        cfg["master_name"] = master_name
        changed = True
        print(f"  ✓ master_name 已设置为 {master_name}")

    print("\n--- 配置 API 密钥 ---")
    # 定义需要交互配置的项 (提示语, path)
    prompts = [
        ("请输入首选 LLM API Key: ", ("api", "llm_api_key")),
        ("请输入备选 LLM API Key（留空跳过）: ", ("api", "backup_api_key")),
        ("请输入图像处理 API Key: ", ("api", "image_process_api_key")),
    ]

    def set_nested(data, path, value):
        curr = data
        for key in path[:-1]:
            curr = curr.setdefault(key, {})
        curr[path[-1]] = value

    for msg, path in prompts:
        val = input(msg).strip()
        if val:
            set_nested(cfg, path, val)
            changed = True
            print(f"  ✓ {'.'.join(path)} 已设置")

    print("\n--- 配置 NapCat 连接 ---")
    ws_url_val = input("请输入 NapCat WebSocket 地址 [默认 ws://localhost:3001]: ").strip()
    if ws_url_val:
        set_nested(cfg, ("connection", "napcat_ws_url"), ws_url_val)
        changed = True
        print(f"  ✓ connection.napcat_ws_url 已设置为 {ws_url_val}")

    ws_token_val = input("请输入 NapCat WebSocket Token（留空则不认证）: ").strip()
    if ws_token_val:
        set_nested(cfg, ("connection", "napcat_ws_token"), ws_token_val)
        changed = True
        print("  ✓ connection.napcat_ws_token 已设置")

    print("\n--- 配置目标 QQ ---")
    # QQ 号配置逻辑
    qq_val = input("请输入私聊用 QQ 号: ").strip()
    if qq_val:
        try:
            set_nested(cfg, ("target", "qq"), int(qq_val))
            changed = True
            print("  ✓ target.qq 已设置")
        except: print("  ❌ QQ 号格式错误，跳过")

    group_val = input("请输入目标群聊 (多个用逗号隔开): ").strip()
    if group_val:
        try:
            groups = [int(x.strip()) for x in group_val.split(",") if x.strip()]
            set_nested(cfg, ("target", "groups"), groups)
            changed = True
            print("  ✓ target.groups 已设置")
        except: print("  ❌ 群号格式错误，跳过")

    if changed:
        _save_yaml(cfg)
        print("\n📄 配置已成功保存到 configs/config.yaml")
    else:
        print("\n保持原有配置不变。")
def quick_setup(mode):
    print("\n>>> 步骤 1: 建立文件夹结构")
    ensure_dirs()
    ensure_files()
    # 建立黑名单等必要文件
    if not os.path.exists("blacklist.txt"):
        with open("blacklist.txt", "w", encoding="utf-8") as f:
            f.write("")

    print("\n>>> 步骤 2: 安装依赖文件")
    install_requirements()

    print("\n>>> 步骤 3: 迁移旧版 .env 配置(如有)")
    migrate_from_env()

    print("\n>>> 步骤 4: 配置 API 密钥与 QQ 号")
    config_yaml(mode)

    print("\n>>> 步骤 5: 下载 RAG 嵌入模型")
    try:
        from utils.download_model import download_model
        download_model()
    except ImportError as e:
        print(f"⚠️ 依赖未安装，跳过模型下载: {e}")
        print("   请确保已运行 'uv sync' 或 'pip install -r requirements.txt'")
    except Exception as e:
        print(f"模型下载环节出现问题: {e}")


if __name__ == "__main__":
    print("开始配置必要参数和环境")
    try:
        user_input = input("输入配置方式（刷新（跳过已存在）和写入（全部覆盖））[默认 0]: ").strip()
        current_mode = int(user_input) if user_input else 0
    except ValueError:
        current_mode = 0

    quick_setup(current_mode)

    print("向导结束，如需调整参数，请编辑 configs/config.yaml！")
