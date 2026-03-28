#!/usr/bin/env python
"""
初始化向量数据库脚本
从Doris同步schema并存入ChromaDB
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.append(str(Path(__file__).parent.parent))

from core.chroma_manager import ChromaManager
from utils.logger import logger


async def main():
    """主函数"""
    logger.info("开始初始化向量数据库")
    
    try:
        # 创建ChromaDB管理器
        manager = ChromaManager()
        
        # 同步schema
        manager.sync_schema_from_doris()
        
        # 获取统计信息
        stats = manager.get_collection_stats()
        logger.info(f"向量数据库初始化完成: {stats}")
        
    except Exception as e:
        logger.exception(f"初始化失败: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())