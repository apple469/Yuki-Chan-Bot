# scripts/test_env_migration.py
"""
.env → configs/config.yaml 迁移功能测试脚本
功能：模拟旧版 .env 环境，验证 migrate_from_env() 的迁移逻辑
"""

import os
import sys
import tempfile
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def _migrate_from_env(env_path: Path, config_path: Path) -> list:
    """复制 setup.py 中的 migrate_from_env 核心逻辑，支持自定义路径"""
    migrated = []

    if not env_path.exists():
        return migrated

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
        return migrated

    # 加载现有 yaml（或空配置）
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    else:
        cfg = {}

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

    # DEEPSEEK_API_KEY 兜底
    if not api.get("backup_api_key") and env_data.get("DEEPSEEK_API_KEY"):
        api["backup_api_key"] = env_data["DEEPSEEK_API_KEY"]
        migrated.append("api.backup_api_key (from DEEPSEEK_API_KEY)")

    # 2. 连接配置
    connection = cfg.setdefault("connection", {})
    if env_data.get("NAPCAT_WS_URL") and not connection.get("napcat_ws_url"):
        connection["napcat_ws_url"] = env_data["NAPCAT_WS_URL"]
        migrated.append("connection.napcat_ws_url")

    # 3. 机器人身份（允许覆盖）
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

    # 保存
    if migrated:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    return migrated


def test_full_migration():
    """测试完整 .env 迁移到空 config.yaml"""
    print("\n[测试 1/3] 完整迁移（空 config.yaml）...")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        env_path = tmpdir / ".env"
        config_path = tmpdir / "configs" / "config.yaml"

        # 写入模拟的 .env（旧版格式）
        env_path.write_text(
            "# Yuki-Chan Configuration\n"
            "LLM_API_KEY=sk-test-llm\n"
            "BACKUP_API_KEY=sk-test-backup\n"
            "IMAGE_PROCESS_API_KEY=sk-test-image\n"
            "NAPCAT_WS_URL=ws://127.0.0.1:3001\n"
            "ROBOT_NAME=test_bot\n"
            "MASTER_NAME=test_master\n"
            "TARGET_QQ=123456789\n"
            "TARGET_GROUPS=111111,222222\n",
            encoding="utf-8",
        )

        # 空 config.yaml
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text("{}", encoding="utf-8")

        migrated = _migrate_from_env(env_path, config_path)

        # 验证
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)

        assert cfg["api"]["llm_api_key"] == "sk-test-llm", "LLM_API_KEY 迁移失败"
        assert cfg["api"]["backup_api_key"] == "sk-test-backup", "BACKUP_API_KEY 迁移失败"
        assert cfg["api"]["image_process_api_key"] == "sk-test-image", "IMAGE_PROCESS_API_KEY 迁移失败"
        assert cfg["connection"]["napcat_ws_url"] == "ws://127.0.0.1:3001", "NAPCAT_WS_URL 迁移失败"
        assert cfg["robot_name"] == "test_bot", "ROBOT_NAME 迁移失败"
        assert cfg["master_name"] == "test_master", "MASTER_NAME 迁移失败"
        assert cfg["target"]["qq"] == 123456789, "TARGET_QQ 迁移失败"
        assert cfg["target"]["groups"] == [111111, 222222], "TARGET_GROUPS 迁移失败"
        assert len(migrated) == 8, f"应迁移 8 项，实际迁移 {len(migrated)} 项"

        print(f"  [OK] 迁移 {len(migrated)} 项成功")
        for item in migrated:
            print(f"      - {item}")


def test_partial_migration():
    """测试部分迁移（config.yaml 中已有部分值）"""
    print("\n[测试 2/3] 部分迁移（已有值不覆盖）...")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        env_path = tmpdir / ".env"
        config_path = tmpdir / "configs" / "config.yaml"

        env_path.write_text(
            "LLM_API_KEY=sk-from-env\n"
            "ROBOT_NAME=env_bot\n",
            encoding="utf-8",
        )

        # config.yaml 中 llm_api_key 已存在，robot_name 不存在
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            "api:\n  llm_api_key: sk-existing\n",
            encoding="utf-8",
        )

        migrated = _migrate_from_env(env_path, config_path)

        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)

        # 已有值不应被覆盖
        assert cfg["api"]["llm_api_key"] == "sk-existing", "已有值不应被覆盖"
        # 缺失值应被填充
        assert cfg["robot_name"] == "env_bot", "缺失值应被迁移"
        assert len(migrated) == 1, f"应只迁移 1 项，实际迁移 {len(migrated)} 项"

        print(f"  [OK] 已有值保留，缺失值填充，迁移 {len(migrated)} 项")


def test_deepseek_fallback():
    """测试 DEEPSEEK_API_KEY 兜底迁移"""
    print("\n[测试 3/3] DEEPSEEK_API_KEY 兜底迁移...")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        env_path = tmpdir / ".env"
        config_path = tmpdir / "configs" / "config.yaml"

        env_path.write_text(
            "LLM_API_KEY=sk-llm\n"
            "DEEPSEEK_API_KEY=sk-deepseek\n",
            encoding="utf-8",
        )

        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text("{}", encoding="utf-8")

        migrated = _migrate_from_env(env_path, config_path)

        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)

        assert cfg["api"]["llm_api_key"] == "sk-llm", "LLM_API_KEY 迁移失败"
        assert cfg["api"]["backup_api_key"] == "sk-deepseek", "DEEPSEEK_API_KEY 应作为 backup_api_key 兜底"

        print(f"  [OK] 兜底迁移成功")
        for item in migrated:
            print(f"      - {item}")


def main():
    print("=== .env → config.yaml 迁移测试开始 ===")

    try:
        test_full_migration()
        test_partial_migration()
        test_deepseek_fallback()
        print("\n=== 全部测试通过 [PASS] ===")
    except AssertionError as e:
        print(f"\n[FAIL] 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[FAIL] 测试异常: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
