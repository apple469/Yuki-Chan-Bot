import os
import shutil
import subprocess
import sys

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
        from config import generate_default_config
        default_config = generate_default_config()
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(default_config)
        print("[Config] 已生成初始 configs/config.yaml")
    else:
        with open(config_path, "r", encoding="utf-8") as f:
            content = f.read()
        if "# Yuki-Chan Bot" not in content:
            # 旧文件无注释，升级：保留现有值，重新生成带注释版本
            import yaml
            import re
            old_cfg = yaml.safe_load(content) or {}
            from config import generate_default_config
            new_content = generate_default_config()

            def _inject(data, prefix=""):
                nonlocal new_content
                for k, v in data.items():
                    if isinstance(v, dict):
                        _inject(v, f"{prefix}.{k}" if prefix else k)
                    else:
                        val_yaml = yaml.dump({k: v}, default_flow_style=False, sort_keys=False).strip()
                        _, val_part = val_yaml.split(":", 1)
                        val_part = val_part.strip()
                        pattern = rf"^(\s*{re.escape(k)}:[ \t]*)([^\n#]*?)((?:[ \t]*#.*)?)$"
                        new_content = re.sub(
                            pattern,
                            lambda m: f"{m.group(1).rstrip(' \t')} {val_part}{m.group(3)}",
                            new_content,
                            flags=re.MULTILINE,
                            count=1
                        )

            _inject(old_cfg)
            # 备份旧文件
            with open(config_path + ".old", "w", encoding="utf-8") as f:
                f.write(content)
            with open(config_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            print("[Config] 已升级 configs/config.yaml，添加注释并保留原有配置（旧文件已备份为 .old）")
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
    """将 .env 中的配置自动迁移到 configs/config.yaml（仅迁移 yaml 中缺失的值）"""
    env_path = ".env"
    if not os.path.exists(env_path):
        return False

    try:
        import yaml
    except ImportError:
        print("⚠️ PyYAML 未安装，跳过 .env 迁移。建议先安装依赖后再运行 setup.py")
        return False

    # 解析 .env
    env_data = {}
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env_data[key.strip()] = value.strip().strip('"').strip("'")

    if not env_data:
        return False

    cfg = _load_yaml()
    migrated = []

    # 1. API Keys
    api = cfg.setdefault("api", {})
    key_map = {
        "LLM_API_KEY": "llm_api_key",
        "BACKUP_API_KEY": "backup_api_key",
        "IMAGE_PROCESS_API_KEY": "image_process_api_key",
    }
    for env_key, yaml_key in key_map.items():
        val = env_data.get(env_key)
        if val and not api.get(yaml_key):
            api[yaml_key] = val
            migrated.append(f"api.{yaml_key}")

    # DEEPSEEK_API_KEY 作为 backup_api_key 的兜底迁移
    if not api.get("backup_api_key") and env_data.get("DEEPSEEK_API_KEY"):
        api["backup_api_key"] = env_data["DEEPSEEK_API_KEY"]
        migrated.append("api.backup_api_key (from DEEPSEEK_API_KEY)")

    # 2. 连接配置
    connection = cfg.setdefault("connection", {})
    if env_data.get("NAPCAT_WS_URL") and not connection.get("napcat_ws_url"):
        connection["napcat_ws_url"] = env_data["NAPCAT_WS_URL"]
        migrated.append("connection.napcat_ws_url")

    # 3. 机器人身份（允许覆盖默认值，因为旧版 setup.py 中这些值通常是用户自定义的）
    if env_data.get("ROBOT_NAME"):
        cfg["robot_name"] = env_data["ROBOT_NAME"]
        migrated.append("robot_name")
    if env_data.get("MASTER_NAME"):
        cfg["master_name"] = env_data["MASTER_NAME"]
        migrated.append("master_name")

    # 4. 目标 QQ
    target = cfg.setdefault("target", {})
    if env_data.get("TARGET_QQ") and not target.get("qq"):
        try:
            target["qq"] = int(env_data["TARGET_QQ"])
            migrated.append("target.qq")
        except ValueError:
            pass

    if env_data.get("TARGET_GROUPS") and not target.get("groups"):
        try:
            groups = [int(g.strip()) for g in env_data["TARGET_GROUPS"].split(",") if g.strip()]
            target["groups"] = groups
            migrated.append("target.groups")
        except ValueError:
            pass

    if migrated:
        _save_yaml(cfg)
        print(f"[迁移] 检测到 .env 文件，已自动迁移 {len(migrated)} 项配置到 configs/config.yaml:")
        for item in migrated:
            print(f"   - {item}")
        print("   (.env 文件已保留，可作为备份)")
        return True
    return False

def _load_yaml():
    import yaml
    path = "configs/config.yaml"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}

def _save_yaml(data):
    """保存 yaml，尽可能保留现有注释（只替换变更的值）"""
    import yaml
    import re
    path = "configs/config.yaml"

    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        return

    with open(path, "r", encoding="utf-8") as f:
        original = f.read()

    def _replace_values(d, indent=0):
        nonlocal original
        spaces = "  " * indent
        for k, v in d.items():
            if isinstance(v, dict):
                _replace_values(v, indent + 1)
            else:
                # 生成 yaml 格式的值字符串
                if isinstance(v, list):
                    # 列表直接用流式风格 [a, b]
                    val_part = yaml.dump(v, allow_unicode=True, default_flow_style=True).strip()
                else:
                    val_yaml = yaml.dump({k: v}, allow_unicode=True, default_flow_style=False, sort_keys=False).strip()
                    _, val_part = val_yaml.split(":", 1)
                    val_part = val_part.strip()

                # 匹配并替换（保留行尾注释）
                # 使用 [ \t]* 替代 \s*，防止 \s 跨过换行符匹配下一行
                pattern = rf"^({spaces}{re.escape(k)}:[ \t]*)([^\n#]*?)((?:[ \t]*#.*)?)$"
                new_original = re.sub(
                    pattern,
                    lambda m: f"{m.group(1).rstrip(' \t')} {val_part}{m.group(3)}",
                    original,
                    flags=re.MULTILINE,
                    count=1
                )
                if new_original != original:
                    original = new_original
                    # 如果是列表，删除后续残留的块样式列表项（- 开头且缩进相同的行）
                    if isinstance(v, list):
                        lines = original.split("\n")
                        result = []
                        found_key = False
                        for line in lines:
                            if found_key:
                                # 遇到缩进小于当前层级的行，停止删除
                                if line and not line.startswith(spaces) and not line.startswith(spaces + "-"):
                                    found_key = False
                                    result.append(line)
                                    continue
                                # 跳过残留的列表项和空行
                                if line.startswith(spaces + "-") or (line.strip() == "" and result and result[-1].startswith(spaces + "-")):
                                    continue
                                result.append(line)
                            else:
                                if line.startswith(f"{spaces}{k}:"):
                                    found_key = True
                                result.append(line)
                        original = "\n".join(result)
                else:
                    # 键不存在。嵌套键追加到文件末尾会产生无效 YAML（缺少父节点），
                    # 因此仅顶层键允许兜底追加；嵌套键缺失说明配置文件不完整。
                    if indent == 0:
                        original += f"\n{spaces}{k}: {val_part}"
                    else:
                        print(f"⚠️  configs/config.yaml 中缺少 '{k}'（位于嵌套层级 {indent}），跳过追加。"
                              f"建议删除 config.yaml 后重新运行 setup.py 生成完整配置。")

    _replace_values(data)

    with open(path, "w", encoding="utf-8") as f:
        f.write(original)

def config_yaml(mode):
    """交互式配置 configs/config.yaml"""
    try:
        import yaml
    except ImportError:
        print("⚠️ PyYAML 未安装，无法自动修改 configs/config.yaml")
        print("   请先安装依赖，或手动编辑 configs/config.yaml")
        return

    cfg = _load_yaml()
    changed = False

    # 1. API Keys
    print("\n--- 配置 API 密钥 ---")
    api = cfg.setdefault("api", {})
    keys = [
        ("llm_api_key", "请输入首选 LLM API Key: "),
        ("backup_api_key", "请输入备选 LLM API Key（不需要可留空）: "),
        ("image_process_api_key", "请输入图像处理 API Key: "),
    ]
    for key, prompt in keys:
        if mode == 1 or not api.get(key):
            value = input(prompt).strip()
            if value:
                api[key] = value
                changed = True
                print(f"  ✓ api.{key} 已设置")
            elif mode == 1 and key in api:
                del api[key]
                changed = True
        else:
            print(f"  api.{key} 已存在，跳过")

    # 2. 目标 QQ
    print("\n--- 配置目标 QQ ---")
    target = cfg.setdefault("target", {})
    settings = [
        ("qq", "请输入私聊用 QQ 号: ", int),
        ("groups", "请输入目标群聊 QQ 号 (多个用逗号隔开，不需要可留空): ", None),
    ]
    for key, prompt, cast in settings:
        if mode == 1 or not target.get(key):
            value = input(prompt).strip()
            if value:
                if key == "groups":
                    target[key] = [int(g.strip()) for g in value.split(",") if g.strip()]
                else:
                    target[key] = int(value) if cast == int else value
                changed = True
                print(f"  ✓ target.{key} 已设置")
            elif mode == 1 and key in target:
                del target[key]
                changed = True
        else:
            print(f"  target.{key} 已存在，跳过")

    if changed:
        _save_yaml(cfg)
        print("\n📄 配置已保存到 configs/config.yaml")
    else:
        print("\n配置无变化")

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
