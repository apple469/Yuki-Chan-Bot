# memory_rag.py
import os
# 必须在 import sentence_transformers 之前设置，确保完全离线运行
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['HF_DATASETS_OFFLINE'] = '1'

import chromadb
import jieba.analyse  # 确保你的环境里有 jieba
from sentence_transformers import SentenceTransformer
import datetime
import json
from config import VECTOR_DB_PATH, EMBED_MODEL, RETRIEVAL_TOP_K


class MemoryRAG:
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        print("[RAG] 初始化记忆库...")
        self.model = SentenceTransformer(EMBED_MODEL)
        self.client = chromadb.PersistentClient(path=VECTOR_DB_PATH)
        self.collection = self.client.get_or_create_collection(
            name="diaries",
            metadata={"hnsw:space": "cosine"} # 使用余弦相似度进行向量匹配
        )
        print("[RAG] 记忆库初始化完成")

    def save_diary(self, content, chat_id=None, people=None, emotion=None):
        """保存日记到向量库，包含自动去重逻辑"""
        
        # 1. 24小时内内容级去重检查
        where_filter = {}
        if chat_id is not None:
            where_filter["chat_id"] = str(chat_id)
        
        # 检查最近24小时内是否已有完全相同的内容
        time_threshold = datetime.datetime.now().timestamp() - 86400 
        where_filter["timestamp"] = {"$gte": time_threshold}
        
        try:
            existing = self.collection.get(where=where_filter)
            if existing and 'documents' in existing and existing['documents']:
                if content in existing['documents']:
                    print(f"[RAG] 检测到24小时内重复内容，跳过保存")
                    return
        except Exception as e:
            print(f"[RAG] 去重检查跳过: {e}")

        # 2. 正常保存逻辑
        embedding = self.model.encode(content).tolist()
        doc_id = f"diary_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(content) % 10000:04d}"
        metadata = {"timestamp": datetime.datetime.now().timestamp()}
        
        if chat_id is not None:
            metadata["chat_id"] = str(chat_id)
        if people:
            metadata["people"] = json.dumps(people, ensure_ascii=False)
        if emotion:
            metadata["emotion"] = emotion
            
        self.collection.add(
            documents=[content],
            embeddings=[embedding],
            metadatas=[metadata],
            ids=[doc_id]
        )
        print(f"[RAG] 日记已存入 (chat_id={chat_id}): {content[:50]}...")

    def search_memory(self, query, chat_id=None, top_k=RETRIEVAL_TOP_K, threshold=1.0):
        """混合检索：支持当前群聊 + 手动录入的记忆"""
        if not query.strip():
            return []
            
        query_emb = self.model.encode(query).tolist()
        where_filter = {}
        if chat_id is not None:
            # 融合检索逻辑：检索当前 chat_id 或全局 manual_record
            where_filter["chat_id"] = {"$in": [str(chat_id), "manual_record"]}
            
        results = self.collection.query(
            query_embeddings=[query_emb],
            n_results=top_k,
            where=where_filter,
            include=["documents", "distances"]
        )
        
        if results['documents'] and results['documents'][0]:
            docs = results['documents'][0]
            distances = results['distances'][0]
            # 根据相似度阈值过滤并进行结果集去重
            filtered = []
            seen = set()
            for doc, dist in zip(docs, distances):
                if dist <= threshold and doc not in seen:
                    filtered.append(doc)
                    seen.add(doc)
            return filtered
        return []

    def search_diaries(self, query_text, chat_id=None, n_results=20):
        """
        升级版搜索：返回日记对象列表，加入黑名单过滤
        """
        print(f"\n[RAG-Debug] 🔍 唤起记忆检索: '{query_text}'")
        
        # 0. 基础检查
        total_count = self.collection.count()
        if total_count == 0:
            return []

        # 1. 显式编码向量 (解决 768 vs 384 维度报错)
        query_embedding = self.model.encode(query_text).tolist()

        # 2. 向量粗筛 (全局检索以确保拿满 20 条)
        actual_n = min(n_results, total_count)
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=actual_n
        )

        if not results or not results['documents'][0]:
            return []

        documents = results['documents'][0]
        metadatas = results['metadatas'][0]
        distances = results['distances'][0]

        # 3. 提取高熵关键词并过滤黑名单
        # 我们把名字等高频词去掉，让 Yuki 关注真正的“事儿”
        raw_keywords = jieba.analyse.extract_tags(query_text, topK=5, withWeight=True)
        # name_blacklist = ['池宇健', 'yuki', '主人', '人家', '人家是', '哥哥']
        name_blacklist = []
        keywords_with_weight = [
            (kw, weight) for kw, weight in raw_keywords 
            if kw.lower() not in name_blacklist
        ]
        print(f"[RAG-Debug] 💎 过滤后的核心锚点: {keywords_with_weight}")

        scored_results = []
        for i in range(len(documents)):
            # 基础语义分
            semantic_score = 1.0 - distances[i]
            
            # 关键词补偿
            keyword_boost = 0.0
            matched_words = []
            for kw, weight in keywords_with_weight:
                if kw in documents[i]:
                    # weight 是 IDF 值，代表信息量
                    keyword_boost += weight * 0.1 
                    matched_words.append(kw)
            
            final_score = semantic_score + keyword_boost
            
            # 构造返回对象
            scored_results.append({
                "content": documents[i],
                "metadata": metadatas[i],
                "score": final_score,
                "debug": f"语义:{semantic_score:.2f} + 补偿:{keyword_boost:.2f} (匹配:{matched_words})"
            })

        # 4. 排序并返回完整列表
        scored_results.sort(key=lambda x: x['score'], reverse=True)

        # 简单的 Top 3 调试打印
        for i, res in enumerate(scored_results[:3]):
            print(f"[RAG-Debug] Top {i+1} | 总分 {res['score']:.4f} | {res['debug']}")

        return scored_results
    def clean_duplicate_diaries(self, dry_run=False):
        """物理清理数据库中所有的重复项（保留最新的一条）"""
        print("[RAG] 正在扫描全局重复记录...")
        all_data = self.collection.get()
        
        if not all_data or not all_data['documents']:
            return
        
        seen = {} # (content, chat_id) -> (id, timestamp)
        to_delete = []
        
        for doc, meta, id in zip(all_data['documents'], all_data['metadatas'], all_data['ids']):
            key = (doc, meta.get('chat_id', 'None'))
            timestamp = meta.get('timestamp', 0)
            
            if key in seen:
                old_id, old_ts = seen[key]
                if timestamp > old_ts:
                    to_delete.append(old_id)
                    seen[key] = (id, timestamp)
                else:
                    to_delete.append(id)
            else:
                seen[key] = (id, timestamp)
        
        if dry_run:
            print(f"[RAG] 预览：发现 {len(to_delete)} 条重复记录")
            return to_delete
            
        if to_delete:
            # 分批删除防止内存溢出
            for i in range(0, len(to_delete), 100):
                self.collection.delete(ids=to_delete[i:i+100])
            print(f"[RAG] 清理完成，已删除 {len(to_delete)} 条重复记录")
        else:
            print("[RAG] 未发现重复记录")

# --- 维护工具入口 ---
if __name__ == "__main__":
    rag = MemoryRAG()
    print("\n--- Yuki 记忆库核心维护 ---")
    print("1. 查看库状态 | 2. 预览重复项 | 3. 物理清理重复")
    
    cmd = input("> ").strip()
    if cmd == "1":
        res = rag.collection.get()
        print(f"当前总条数: {len(res['ids'])}")
    elif cmd == "2":
        rag.clean_duplicate_diaries(dry_run=True)
    elif cmd == "3":
        if input("确认清理？(y/n): ").lower() == 'y':
            rag.clean_duplicate_diaries(dry_run=False)