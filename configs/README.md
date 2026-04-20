# Yuki-Chan Bot 配置系统说明

## 架构概览

本项目采用 **YAML 单文件配置 + 运行时热重载** 架构。所有配置项统一从 `configs/config.yaml` 读取，修改后无需重启即可生效（部分模块级常量除外）。

```
┌─────────────────┐     读取/热重载      ┌─────────────────┐
│  configs/       │  ◄─────────────────  │  config.py      │
│  config.yaml    │                      │  Config 类      │
│  (运行时配置)    │                      │  (cfg 单例)     │
└─────────────────┘                      └────────┬────────┘
       ▲                                          │
       │ 动态生成初始配置                           │ cfg.XXX
       │ (generate_default_config)                 ▼
       │                                ┌─────────────────┐
       │                                │  core/ modules/ │
       │                                │  network/ ...   │
       │                                │  (业务模块)      │
       │                                └─────────────────┘
       │
┌─────────────────┐
│  _ATTR_MAP      │
│  (配置定义源)    │
└─────────────────┘
```

## 目录结构

```
configs/
├── README.md              # 本文档
└── config.yaml            # 用户实际运行时配置（.gitignore 忽略，不提交）
```

| 文件 | 作用 | 是否提交到 Git |
|------|------|---------------|
| `config.yaml` | 用户实际使用的配置文件，包含 API Key 等敏感信息 | ❌ 否 |

## 使用方式

### 在业务模块中读取配置

```python
from config import cfg

# 读取简单配置
print(cfg.MAX_MESSAGE_LENGTH)      # 150
print(cfg.LLM_MODEL)               # "deepseek-chat"

# 读取嵌套配置（等效写法）
print(cfg.LLM_API_KEY)             # 通过 _ATTR_MAP 自动映射
print(cfg.get("api", "llm_api_key", default=""))  # 显式路径访问

# 读取计算属性
print(cfg.REQUEST_TIMEOUT)         # aiohttp.ClientTimeout 对象
print(cfg.TARGET_GROUPS)           # [123456, 789012]（自动做类型转换）
print(cfg.keywords)                # ["主人", "哥哥", "yuki"]（自动追加 ROBOT_NAME）
```

### 手动热重载

```python
from config import cfg

# 用户修改了 configs/config.yaml 后，立即生效
cfg.reload()
```

> 实际上无需手动调用：Config 类在每次访问配置时会自动检查文件修改时间（最多每秒一次），有变更则自动 reload。

## 添加新配置（开发者指南）

只需在 **`config.py`** 的 `_ATTR_MAP` 字典中添加一行映射：

```python
_ATTR_MAP = {
    # ... 已有配置 ...

    # 新增配置
    "MY_NEW_SETTING": (("section", "key"), "default_value", "字段说明注释"),
    #     ↑ 属性名          ↑ yaml 路径        ↑ 默认值        ↑ 注释（可选）
}
```

| 参数 | 说明 | 示例 |
|------|------|------|
| 属性名 | 业务模块中通过 `cfg.XXX` 访问的名字 | `"MAX_MESSAGE_LENGTH"` |
| yaml 路径 | 元组形式的路径，支持嵌套 | `("diary", "idle_seconds")` |
| 默认值 | 当 yaml 中缺失该字段时的 fallback | `120` |
| 注释 | 生成 `config.yaml` 时添加在字段后的行尾注释，`None` 表示不添加 | `"单条消息最大长度"` |

**会自动完成的事：**
- 程序启动时，`_auto_fill()` 会自动把缺失的新字段及其默认值写入 `configs/config.yaml`
- 首次运行 `setup.py` 时，`generate_default_config()` 会根据 `_ATTR_MAP` 动态生成带注释的完整初始 `config.yaml`
- 业务模块即刻通过 `cfg.MY_NEW_SETTING` 访问

**需要手动处理的情况（计算属性）：**
如果新配置需要动态构造（如类型转换、对象构造、路径解析），需要在 `Config` 类中添加 `@property`：

```python
@property
def MY_NEW_SETTING(self):
    self._check()  # 触发热重载检查
    raw_value = self._raw.get("section", {}).get("key", "default")
    # 做额外的转换/构造
    return transformed_value
```

## 配置优先级

```
configs/config.yaml 中用户自定义的值
        ↓
_ATTR_MAP / @property 中定义的默认值
```

- 环境变量（`.env`）已彻底移除，所有配置统一走 YAML
- 老用户运行 `python setup.py` 时，`migrate_from_env()` 会自动将 `.env` 中的数据迁移到 `configs/config.yaml`

## 热重载限制

以下情况 **不支持** 热重载，修改后需重启 Bot：

| 场景 | 原因 |
|------|------|
| `core/prompts.py` 中的 `ROBOT_NAME` / `MASTER_NAME` | prompt 字符串在模块导入时即求值为常量 |
| 新增/删除 Python 模块 | 需要重新导入模块 |
| 修改 `config.py` 本身的代码逻辑 | 需要重新加载 Python 模块 |

> 绝大多数运行时参数（模型名、API Key、阈值、超时、路径等）均支持热重载。

## setup.py 中的配置交互

```bash
python setup.py
```

步骤说明：
1. **建立文件夹结构** —— 创建 `models/`、`data/`、`yuki_memory/`、`logs/`
2. **安装依赖** —— `uv sync` 或 `pip install`
3. **迁移旧版 .env** —— 如有 `.env` 文件，自动迁移到 `configs/config.yaml`
4. **交互式配置** —— 引导填写 API Key、QQ 号等必填项
5. **下载 RAG 嵌入模型**

## 常见问题

**Q: 为什么 `configs/config.yaml` 被 .gitignore 忽略了？**  
A: 因为该文件包含 API Key、QQ 号等敏感信息。首次运行 `setup.py` 时，`config.py` 中的 `generate_default_config()` 会根据 `_ATTR_MAP` 动态生成完整的初始 `config.yaml`。

**Q: 我手动修改了 `configs/config.yaml`，重启后配置会丢失吗？**  
A: 不会。`config.py` 只会**补全缺失字段**，绝不会覆盖用户已手动修改的值。

**Q: 我删除了 `configs/config.yaml` 中的某个字段，程序还会自动把它加回来吗？**  
A: 会。`_auto_fill()` 会在启动时自动检测 `_ATTR_MAP` 中定义了但 yaml 中缺失的字段，并把默认值写回。这是为了让新配置项能自动推送到老用户的配置文件中。
