"""
SQL执行器
负责连接Doris数据库执行SQL并返回结果
"""
from typing import List, Dict, Any
import pymysql
from sqlalchemy import create_engine, text
import pandas as pd
from loguru import logger

from models.schemas import SQLResult
from config.settings import DORIS_CONFIG


class DorisExecutor:
    """
    Doris SQL执行器
    支持连接池、超时控制、结果格式化
    """
    
    def __init__(self):
        """初始化Doris连接"""
        self.config = DORIS_CONFIG
        
        # 创建SQLAlchemy引擎
        conn_str = f"mysql+pymysql://{self.config['user']}:{self.config['password']}@{self.config['host']}:{self.config['port']}/{self.config['database']}"
        self.engine = create_engine(
            conn_str,
            pool_size=5,
            pool_recycle=3600,
            connect_args={
                "charset": "utf8mb4",
                "connect_timeout": 10
            }
        )
        
        logger.info(f"Doris执行器初始化完成: {self.config['host']}:{self.config['port']}/{self.config['database']}")
    
    def execute(self, sql: str, timeout: int = 30) -> SQLResult:
        """
        执行SQL并返回结果
        
        Args:
            sql: SQL语句
            timeout: 超时时间(秒)
            
        Returns:
            SQLResult对象
        """
        logger.info(f"执行SQL: {sql}")
        
        try:
            # 使用pandas读取数据
            with self.engine.connect() as conn:
                # 设置超时
                conn.execute(text(f"SET query_timeout = {timeout}"))
                
                # 执行查询
                df = pd.read_sql(sql, conn)
                
                # 转换为字典列表
                result_data = df.to_dict(orient='records')
                
                return SQLResult(
                    sql_query=sql,
                    sql_result=result_data,
                    columns=df.columns.tolist(),
                    row_count=len(df),
                    execution_time_ms=0  # 由调用方设置
                )
                
        except Exception as e:
            logger.error(f"SQL执行失败: {str(e)}, SQL: {sql}")
            raise
    
    def test_connection(self) -> bool:
        """测试数据库连接"""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"数据库连接测试失败: {str(e)}")
            return False
    
    def get_table_schema(self, table_name: str) -> List[Dict]:
        """
        获取表结构信息
        
        Args:
            table_name: 表名
            
        Returns:
            字段信息列表
        """
        sql = f"DESCRIBE {table_name}"
        result = self.execute(sql)
        return result.sql_result
    
    def get_all_tables(self) -> List[str]:
        """
        获取所有表名
        
        Returns:
            表名列表
        """
        sql = "SHOW TABLES"
        result = self.execute(sql)
        tables = []
        for row in result.sql_result:
            tables.append(list(row.values())[0])
        return tables