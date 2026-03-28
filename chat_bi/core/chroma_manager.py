
"""
ChromaDB管理器
负责向量数据库的初始化和维护
"""
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import json
from loguru import logger

from config.settings import CHROMA_CONFIG, DORIS_CONFIG
from core.sql_executor import DorisExecutor


class ChromaManager:
    """
    ChromaDB向量库管理器
    负责从Doris同步schema信息并向量化存储
    """
    
    def __init__(self):
        """初始化管理器"""
        self.chroma_config = CHROMA_CONFIG
        self.doris_executor = DorisExecutor()
        
        # 初始化BGE-M3 embedding模型
        self.embedding_model = SentenceTransformer('BAAI/bge-m3')
        
        # 初始化ChromaDB客户端
        self.client = chromadb.PersistentClient(
            path=self.chroma_config["persist_directory"]
        )
        
        # 获取或创建集合
        self.collection = self.client.get_or_create_collection(
            name=self.chroma_config["collection_name"],
            metadata={"hnsw:space": "cosine"}
        )
        
        logger.info(f"ChromaDB管理器初始化完成: {self.chroma_config['persist_directory']}")
    
    def sync_schema_from_doris(self):
        """
        从Doris同步所有表的schema信息
        """
        logger.info("开始从Doris同步schema信息")
        
        # 获取所有表
        tables = self.doris_executor.get_all_tables()
        
        schema_items = []
        
        for table in tables:
            # 获取表结构
            fields = self.doris_executor.get_table_schema(table)
            
            for field in fields:
                # 构建schema项
                item = {
                    "table": table,
                    "column": field["Field"],
                    "type": field["Type"],
                    "comment": field.get("Comment", ""),
                    "nullable": field.get("Null", "YES") == "YES",
                    "key": field.get("Key", "")
                }
                schema_items.append(item)
        
        logger.info(f"从Doris获取到{len(schema_items)}个字段")
        
        # 准备向量化数据
        ids = []
        documents = []
        metadatas = []
        embeddings = []
        
        for i, item in enumerate(schema_items):
            # 生成唯一ID
            item_id = f"{item['table']}_{item['column']}_{i}"
            ids.append(item_id)
            
            # 构建文档文本
            doc_parts = [
                f"表名: {item['table']}",
                f"字段名: {item['column']}",
                f"类型: {item['type']}",
                f"注释: {item['comment']}"
            ]
            doc_text = "\n".join(doc_parts)
            documents.append(doc_text)
            
            # 元数据
            metadatas.append({
                "table": item['table'],
                "column": item['column'],
                "type": item['type'],
                "comment": item['comment']
            })
            
            # 生成向量
            emb = self.embedding_model.encode(doc_text).tolist()
            embeddings.append(emb)
        
        # 清空原有集合
        self.client.delete_collection(self.chroma_config["collection_name"])
        self.collection = self.client.create_collection(
            name=self.chroma_config["collection_name"],
            metadata={"hnsw:space": "cosine"}
        )
        
        # 批量添加
        batch_size = 100
        for i in range(0, len(ids), batch_size):
            end = min(i + batch_size, len(ids))
            self.collection.add(
                embeddings=embeddings[i:end],
                documents=documents[i:end],
                metadatas=metadatas[i:end],
                ids=ids[i:end]
            )
            logger.info(f"已添加 {end}/{len(ids)} 条记录")
        
        logger.info(f"Schema同步完成，共{len(ids)}条记录")
        
        # 保存元数据信息供查询
        self._save_metadata(schema_items)
    
    def _save_metadata(self, schema_items: List[Dict]):
        """保存元数据到JSON文件供查询"""
        metadata_file = "./data/schema_metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(schema_items, f, ensure_ascii=False, indent=2)
        logger.info(f"元数据已保存到: {metadata_file}")
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """
        获取集合统计信息
        
        Returns:
            统计信息字典
        """
        count = self.collection.count()
        
        # 获取样本
        if count > 0:
            sample = self.collection.peek()
        else:
            sample = None
        
        return {
            "total_count": count,
            "collection_name": self.chroma_config["collection_name"],
            "sample": sample
        }