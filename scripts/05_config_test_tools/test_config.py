# scripts/test_config.py
"""
Config 模块测试脚本
功能：验证配置加载、热重载检测、自愈备份回退等核心功能
"""

import os
import sys
import time
import shutil
from pathlib import Path

# 将项目根目录加入路径以导入 config
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import yaml
from config import cfg, Config, generate_default_config, _ATTR_MAP

CONFIG_PATH = os.path.join(Path(__file__).resolve().parents[2], "configs", "config.yaml")
BAK_PATH = CONFIG_PATH + ".bak"


def _read_config_raw():
    """读取当前 config.yaml 的原始文本"""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return f.read()


def _write_config_raw(content):
    """直接写入 config.yaml 原始文本"""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write(content)


def test_generate_default_config():
    """测试 generate_default_config() 动态生成默认配置"""
    print("\n[测试 1/5] 动态生成默认配置...")
    content = generate_default_config()
    assert isinstance(content, str), "应返回字符串"
    assert len(content) > 0, "不应为空"
    assert "# Yuki-Chan Bot 配置文件" in content, "应包含头部注释"

    # 验证是有效的 YAML
    parsed = yaml.safe_load(content)
    assert isinstance(parsed, dict), "应解析为字典"

    # 验证包含所有核心配置项
    assert parsed.get("robot_name") == "yuki", "robot_name 默认值应为 yuki"
    assert parsed.get("master_name") == "主人", "master_name 默认值应为主人"
    assert "api" in parsed, "应包含 api 节点"
    assert parsed["api"].get("llm_base_url") == "https://api.deepseek.com/v1", "llm_base_url 默认值不对"
    assert "model" in parsed, "应包含 model 节点"
    assert "connection" in parsed, "应包含 connection 节点"
    assert "target" in parsed, "应包含 target 节点"
    assert "paths" in parsed, "应包含 paths 节点"
    assert "timing" in parsed and "request_timeout" in parsed["timing"], "应包含 timing.request_timeout"
    assert "attention" in parsed and "keywords" in parsed["attention"], "应包含 attention.keywords"
    assert "energy" in parsed, "应包含 energy 节点"
    assert parsed.get("debug") is True, "debug 默认值应为 True"

    # 验证注释存在
    assert "# ================= API 配置 =================" in content, "应包含 section 注释头"
    assert "# 单条消息最大长度，防止 token 炸弹" in content, "应包含行尾注释"
    assert "# 首选 LLM API Key" in content, "应包含 api 行尾注释"
    assert "# 均为相对项目根目录的路径" in content, "应包含 paths 多行注释头"

    # 验证 _ATTR_MAP 结构正确（每个条目应为三元组）
    for name, item in _ATTR_MAP.items():
        assert isinstance(item, tuple) and len(item) == 3, f"_ATTR_MAP['{name}'] 应为 (path, default, comment) 三元组"
        path, default, comment = item
        assert isinstance(path, tuple), f"_ATTR_MAP['{name}'] 路径应为元组"
        assert comment is None or isinstance(comment, str), f"_ATTR_MAP['{name}'] 注释应为 str 或 None"

    print("  [OK] 默认配置生成正确，_ATTR_MAP 结构完整，包含所有预期字段和注释")


def test_basic_read():
    """测试基本配置读取"""
    print("\n[测试 2/5] 基本配置读取...")
    assert cfg.DEBUG in (True, False), "DEBUG 应为布尔值"
    assert isinstance(cfg.MAX_MESSAGE_LENGTH, int), "MAX_MESSAGE_LENGTH 应为整数"
    assert cfg.MAX_MESSAGE_LENGTH > 0, "MAX_MESSAGE_LENGTH 应大于 0"
    assert isinstance(cfg.LLM_BASE_URL, str), "LLM_BASE_URL 应为字符串"
    assert isinstance(cfg.TARGET_QQ, int), "TARGET_QQ 应为整数"
    print("  [OK] 基本配置读取正常")


def test_hot_reload():
    """测试热重载：修改配置文件后触发 _check 自动刷新"""
    print("\n[测试 3/5] 热重载检测...")
    original_content = _read_config_raw()

    # 修改 debug 值（True ↔ False）
    import re
    old_debug = cfg.DEBUG
    new_debug_value = "false" if old_debug else "true"
    # 使用正则匹配，兼容冒号后多个空格的情况
    new_content = re.sub(
        rf"^debug:\s+{str(old_debug).lower()}\b",
        f"debug: {new_debug_value}",
        original_content,
        flags=re.MULTILINE,
        count=1
    )

    # 写入修改后的配置
    _write_config_raw(new_content)

    # 强制触发检查（绕过 1 秒 debounce）
    cfg._last_check = 0
    cfg._check()

    # 验证配置已刷新
    time.sleep(0.1)
    assert cfg.DEBUG != old_debug, f"热重载后 debug 应从 {old_debug} 变为 {not old_debug}"
    print(f"  [OK] 热重载成功: debug {old_debug} → {cfg.DEBUG}")

    # 恢复原配置
    _write_config_raw(original_content)
    cfg._last_check = 0
    cfg._check()
    assert cfg.DEBUG == old_debug, "恢复原配置后 debug 应恢复"
    print("  [OK] 原配置已恢复")


def test_self_healing():
    """测试自愈功能：写入非法 YAML，验证备份生成和配置回退"""
    print("\n[测试 4/5] 自愈功能（非法 YAML 回退）...")
    original_content = _read_config_raw()

    # 清理可能存在的旧 bak
    if os.path.exists(BAK_PATH):
        os.remove(BAK_PATH)

    # 写入非法 YAML
    bad_content = original_content + "\ninvalid_yaml: [broken"
    _write_config_raw(bad_content)

    # 强制触发检查
    cfg._last_check = 0
    cfg._check()

    # 验证 bak 文件已生成
    assert os.path.exists(BAK_PATH), "非法 YAML 应触发备份，生成 .bak 文件"
    with open(BAK_PATH, "r", encoding="utf-8") as f:
        bak_content = f.read()
    assert "[broken" in bak_content, ".bak 文件应包含非法内容"
    print("  [OK] 备份文件已生成")

    # 验证原配置已恢复（允许 _auto_fill 添加的默认值存在）
    current_content = _read_config_raw()
    assert "invalid_yaml" not in current_content, "非法 YAML 应被恢复"
    assert yaml.safe_load(current_content), "恢复后应为有效 YAML"
    print("  [OK] 原配置已自动恢复")

    # 清理 bak
    os.remove(BAK_PATH)


def test_auto_fill():
    """测试缺失字段自动补全（仅内存，不丢注释）"""
    print("\n[测试 5/5] 缺失字段自动补全...")
    original_content = _read_config_raw()

    # 删除一个已知字段（如 debug）
    import re
    stripped_content = re.sub(
        rf"^debug:\s+{str(cfg.DEBUG).lower()}\b.*$",
        "",
        original_content,
        flags=re.MULTILINE
    )
    _write_config_raw(stripped_content)

    # 强制 reload 触发 auto_fill
    cfg.reload()

    # 验证字段已在内存中补全
    assert "debug" in cfg._raw, "缺失的 debug 字段应在内存中被自动补全"
    # 验证文件注释未被覆盖（文件内容应与 stripped_content 一致，因为 _auto_fill 不写磁盘）
    current_file = _read_config_raw()
    assert current_file == stripped_content, "_auto_fill 不应写入磁盘，以免丢失注释"
    print("  [OK] 缺失字段已在内存中补全，文件注释未丢失")

    # 恢复原配置
    _write_config_raw(original_content)
    cfg.reload()


def main():
    print("=== Config 模块测试开始 ===")
    print(f"配置文件路径: {CONFIG_PATH}")

    try:
        test_generate_default_config()
        test_basic_read()
        test_hot_reload()
        test_self_healing()
        test_auto_fill()
        print("\n=== 全部测试通过 [PASS] ===")
    except AssertionError as e:
        print(f"\n[FAIL] 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[FAIL] 测试异常: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
