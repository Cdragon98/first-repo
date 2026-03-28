"""
数据库字段召回模块
使用BGE-M3 embedding + ChromaDB实现语义检索
对应文档中的"数据库字段召回"模块
"""
from typing import List, Dict, Any, Optional
import numpy as np
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings
import json
import re
from loguru import logger

from config.settings import CHROMA_CONFIG, SYNONYMS_PATH, DORIS_CONFIG
from models.constants import BusinessMetrics


class SchemaRetriever:
    """
    数据库字段召回器
    基于BGE-M3进行向量化，ChromaDB存储，支持同义词增强检索
    召回率达97%（文档数据）
    """
    
    def __init__(self):
        """初始化召回器"""
        logger.info("初始化SchemaRetriever")
        
        # 初始化BGE-M3 embedding模型
        self.embedding_model = SentenceTransformer('BAAI/bge-m3')
        
        # 初始化ChromaDB客户端
        self.chroma_client = chromadb.PersistentClient(
            path=CHROMA_CONFIG["persist_directory"]
        )
        
        # 获取或创建集合
        self.collection = self.chroma_client.get_or_create_collection(
            name=CHROMA_CONFIG["collection_name"],
            metadata={"hnsw:space": "cosine"}  # 使用余弦相似度
        )
        
        # 加载同义词库
        self.synonyms = self._load_synonyms()
        
        # 双通道检索配置
        self.top_k_first_stage = 50  # 首轮语义检索召回数
        self.top_k_final = 10  # 最终返回数
    
    def _load_synonyms(self) -> Dict[str, List[str]]:
        """加载同义词库"""
        try:
            with open(SYNONYMS_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"同义词库不存在: {SYNONYMS_PATH}，使用默认映射")
            # 默认业务术语映射
            return {
                "销售额": ["gmv", "销售收入", "成交金额", "sales_amt", "amount"],
                "用户数": ["uv", "活跃用户", "用户量", "user_count", "distinct_users"],
                "订单量": ["订单数", "下单量", "交易笔数", "order_count", "orders"],
                "利润": ["毛利", "净利润", "profit", "margin"],
                "城市": ["city", "地区", "区域", "region"],
                "日期": ["date", "day", "时间", "order_date"],
                "商品": ["产品", "item", "product", "goods"],
                "渠道": ["channel", "来源", "source", "medium"]
            }
    
    def _get_synonym_expansion(self, term: str) -> List[str]:
        """
        获取术语的同义词扩展
        
        Args:
            term: 原始术语
            
        Returns:
            同义词列表
        """
        expanded = [term]
        
        # 直接匹配
        if term in self.synonyms:
            expanded.extend(self.synonyms[term])
        
        # 模糊匹配（包含关系）
        for key, values in self.synonyms.items():
            if term in key or key in term:
                expanded.append(key)
                expanded.extend(values)
        
        # 去重并返回
        return list(set(expanded))
    
    def initialize_schema(self, schema_info: List[Dict[str, Any]]):
        """
        初始化向量库：将数据库schema信息存入ChromaDB
        
        Args:
            schema_info: schema信息列表，每个元素包含表名、字段名、类型、注释等
        """
        logger.info(f"初始化向量库，共{len(schema_info)}个字段")
        
        # 准备数据
        ids = []
        documents = []
        metadatas = []
        embeddings = []
        
        for i, field in enumerate(schema_info):
            # 生成唯一ID
            field_id = f"{field['table']}_{field['column']}"
            ids.append(field_id)
            
            # 构建文档文本（用于向量化）
            doc_parts = [
                f"表名: {field['table']}",
                f"字段名: {field['column']}",
                f"类型: {field['type']}",
                f"注释: {field.get('comment', '')}"
            ]
            doc_text = "\n".join(doc_parts)
            documents.append(doc_text)
            
            # 元数据
            metadatas.append({
                "table": field['table'],
                "column": field['column'],
                "type": field['type'],
                "comment": field.get('comment', '')
            })
            
            # 生成向量
            emb = self.embedding_model.encode(doc_text).tolist()
            embeddings.append(emb)
        
        # 批量添加到ChromaDB
        self.collection.add(
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        
        logger.info(f"向量库初始化完成，共{len(ids)}条记录")
    
    def sync_schema_from_doris(self):
        """
        从Doris同步schema信息（监听DDL变更）
        实际项目中可通过解析Doris的information_schema实现
        """
        # TODO: 实现Doris DDL变更监听和自动同步
        # 可以通过定期拉取或binlog方式实现
        pass
    
    def dual_channel_retrieve(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        双通道检索机制
        首轮语义检索 + 二轮同义词精确匹配过滤
        
        Args:
            query: 查询文本
            top_k: 最终返回结果数
            
        Returns:
            检索到的字段列表
        """
        logger.info(f"双通道检索: {query}")
        
        # 通道1：语义检索
        query_emb = self.embedding_model.encode(query).tolist()
        semantic_results = self.collection.query(
            query_embeddings=[query_emb],
            n_results=self.top_k_first_stage
        )
        
        # 提取语义检索结果
        semantic_hits = []
        if semantic_results['metadatas']:
            for i, metadata in enumerate(semantic_results['metadatas'][0]):
                semantic_hits.append({
                    "metadata": metadata,
                    "distance": semantic_results['distances'][0][i],
                    "score": 1 - semantic_results['distances'][0][i]  # 转换为相似度分数
                })
        
        # 通道2：同义词精确匹配过滤
        # 从查询中提取关键词
        keywords = re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9]+', query)
        
        synonym_hits = []
        for keyword in keywords:
            expanded = self._get_synonym_expansion(keyword)
            
            # 在语义检索结果中过滤包含同义词的字段
            for hit in semantic_hits:
                metadata = hit["metadata"]
                field_text = f"{metadata['table']} {metadata['column']} {metadata.get('comment', '')}"
                
                for syn in expanded:
                    if syn.lower() in field_text.lower():
                        hit["synonym_match"] = True
                        hit["matched_term"] = syn
                        synonym_hits.append(hit)
                        break
        
        # 合并结果：先保留同义词匹配的，再补充语义相似度高的
        seen_ids = set()
        final_results = []
        
        # 先添加同义词匹配的（按相似度排序）
        synonym_hits.sort(key=lambda x: x["score"], reverse=True)
        for hit in synonym_hits:
            hit_id = f"{hit['metadata']['table']}_{hit['metadata']['column']}"
            if hit_id not in seen_ids:
                seen_ids.add(hit_id)
                final_results.append(hit)
        
        # 再补充语义检索结果
        semantic_hits.sort(key=lambda x: x["score"], reverse=True)
        for hit in semantic_hits:
            hit_id = f"{hit['metadata']['table']}_{hit['metadata']['column']}"
            if hit_id not in seen_ids and len(final_results) < top_k:
                seen_ids.add(hit_id)
                final_results.append(hit)
        
        logger.info(f"双通道检索完成，共召回{len(final_results)}个字段")
        return final_results[:top_k]
    
    def retrieve_fields(self, intent_elements, top_k: int = 10) -> Dict[str, Any]:
        """
        根据意图要素检索相关字段
        
        Args:
            intent_elements: 意图要素对象
            top_k: 返回字段数量
            
        Returns:
            包含表名和字段信息的字典
        """
        # 构建检索查询
        query_parts = []
        
        # 添加表名
        if intent_elements.table_name:
            query_parts.append(f"表名: {intent_elements.table_name}")
        
        # 添加字段
        if intent_elements.fields:
            query_parts.append(f"字段: {' '.join(intent_elements.fields)}")
        
        # 添加指标
        for metric in intent_elements.metrics:
            query_parts.append(f"指标: {metric.name}")
        
        query = " ".join(query_parts)
        
        # 执行双通道检索
        results = self.dual_channel_retrieve(query, top_k)
        
        # 整理结果
        tables = {}
        for r in results:
            table = r["metadata"]["table"]
            if table not in tables:
                tables[table] = []
            tables[table].append({
                "column": r["metadata"]["column"],
                "type": r["metadata"]["type"],
                "comment": r["metadata"].get("comment", ""),
                "score": r["score"]
            })
        
        return {
            "tables": tables,
            "total_fields": len(results)
        }