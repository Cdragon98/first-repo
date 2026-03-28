"""
系统配置文件
"""
import os
from pathlib import Path

# 项目根目录
BASE_DIR = Path(__file__).parent.parent

# Doris 数据库配置
DORIS_CONFIG = {
    "host": os.getenv("DORIS_HOST", "localhost"),
    "port": int(os.getenv("DORIS_PORT", 9030)),
    "user": os.getenv("DORIS_USER", "root"),
    "password": os.getenv("DORIS_PASSWORD", ""),
    "database": os.getenv("DORIS_DATABASE", "ads")
}

# ChromaDB 配置
CHROMA_CONFIG = {
    "persist_directory": str(BASE_DIR / "data" / "chroma_db"),
    "collection_name": "schema_knowledge"
}

# 模型配置
MODEL_CONFIG = {
    "embedding_model": "BAAI/bge-m3",
    "llm_model": os.getenv("LLM_MODEL_PATH", "/data/models/chatglm3-6b"),
    "llm_base_url": os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1"),
    "temperature": 0.1,
    "max_tokens": 2048
}

# 文件路径
SYNONYMS_PATH = BASE_DIR / "data" / "synonyms" / "business_synonyms.json"
SQL_TEMPLATES_PATH = BASE_DIR / "data" / "templates" / "sql_templates.yaml"
ECHARTS_TEMPLATES_PATH = BASE_DIR / "data" / "templates" / "echarts_templates.yaml"

# Redis配置（用于缓存）
REDIS_CONFIG = {
    "host": os.getenv("REDIS_HOST", "localhost"),
    "port": int(os.getenv("REDIS_PORT", 6379)),
    "db": int(os.getenv("REDIS_DB", 0)),
    "ttl": 3600,  # 缓存1小时
    "enabled": os.getenv("REDIS_ENABLED", "false").lower() == "true"
}

# 监控配置
METRICS_PORT = int(os.getenv("METRICS_PORT", 8001))

# 日志配置
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = BASE_DIR / "logs" / "chatbi.log"

# 性能配置
MAX_CONCURRENT_QUERIES = int(os.getenv("MAX_CONCURRENT_QUERIES", 50))
QUERY_TIMEOUT_SECONDS = int(os.getenv("QUERY_TIMEOUT_SECONDS", 30))
SQL_RESULT_LIMIT = int(os.getenv("SQL_RESULT_LIMIT", 1000))