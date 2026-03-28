"""
日志工具模块
"""
import sys
from pathlib import Path
from loguru import logger

from config.settings import LOG_LEVEL, LOG_FILE


def setup_logger():
    """配置日志器"""
    # 移除默认处理器
    logger.remove()
    
    # 添加控制台处理器
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=LOG_LEVEL,
        colorize=True
    )
    
    # 添加文件处理器
    log_dir = Path(LOG_FILE).parent
    log_dir.mkdir(exist_ok=True)
    
    logger.add(
        LOG_FILE,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
        level=LOG_LEVEL,
        rotation="500 MB",
        retention="30 days",
        compression="zip"
    )
    
    return logger


# 初始化日志器
logger = setup_logger()