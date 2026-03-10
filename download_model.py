# export_model.py
from sentence_transformers import SentenceTransformer
import os

# 从你 config 里的配置读取
model_name = "shibing624/text2vec-base-chinese"
save_path = "./models/text2vec-base-chinese"

print(f"🚀 正在准备导出模型: {model_name}")
print("这一步可能会因为联网检查卡顿几秒，请稍等...")

# 加载模型（它会先去缓存找，找不到才下载）
model = SentenceTransformer(model_name)

# 创建本地目录
if not os.path.exists(save_path):
    os.makedirs(save_path, exist_ok=True)

# 核心：直接保存到本地
model.save(save_path)

print(f"✅ 模型已成功沉淀到本地: {os.path.abspath(save_path)}")
print("现在你可以去 config.py 修改 EMBED_MODEL 路径了。")