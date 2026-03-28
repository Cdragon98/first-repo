"""
系统常量定义
"""
from enum import Enum


# Doris 数据库配置
DORIS_CONFIG = {
    "host": "localhost",
    "port": 9030,
    "user": "root",
    "password": "",
    "database": "ads"
}

# ChromaDB 配置
CHROMA_CONFIG = {
    "persist_directory": "./data/chroma_db",
    "collection_name": "schema_knowledge"
}

# 模型配置
MODEL_CONFIG = {
    "embedding_model": "BAAI/bge-m3",  # 用于向量化的模型
    "llm_model": "/path/to/chatglm3-6b",  # 微调后的模型路径
    "llm_base_url": "http://localhost:8000/v1",  # vLLM服务地址
    "temperature": 0.1,
    "max_tokens": 2048
}

# 同义词库路径
SYNONYMS_PATH = "./data/synonyms/business_synonyms.json"

# SQL模板路径
SQL_TEMPLATES_PATH = "./data/templates/sql_templates.yaml"
ECHARTS_TEMPLATES_PATH = "./data/templates/echarts_templates.yaml"

# 缓存配置
REDIS_CONFIG = {
    "host": "localhost",
    "port": 6379,
    "db": 0,
    "ttl": 3600  # 缓存1小时
}

# 监控指标配置
METRICS_PORT = 8001


class SQLTemplateType(str, Enum):
    """SQL模板类型，对应models/schemas.py中的SQLType"""
    DIMENSION_STAT = "维度统计查询"
    TIME_SERIES_STAT = "时序统计查询"
    TIME_SERIES_GROUP = "时序分组统计查询"
    WINDOW_STAT = "窗口统计查询"
    GROUP_WINDOW = "分组窗口统计查询"
    TIME_WINDOW = "时序分组窗口统计查询"
    DETAIL_QUERY = "明细查询"


class BusinessMetrics(str, Enum):
    """业务指标同义词映射"""
    SALES = "销售额"
    GMV = "gmv"
    ORDER_COUNT = "订单量"
    USER_COUNT = "用户数"
    ACTIVE_USERS = "活跃用户"
    ARPPU = "arppu"
    CONVERSION_RATE = "转化率"
    RETENTION_RATE = "留存率"