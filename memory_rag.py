# memory_rag.py
import os
# 必须在 import sentence_transformers 之前设置，确保完全离线运行
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['HF_DATASETS_OFFLINE'] = '1'

import chromadb
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