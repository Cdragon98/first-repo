"""
FastAPI应用入口
提供RESTful API服务
对应文档中的"基于FastAPI应用的部署及上线"
"""
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time
from typing import Dict, Any
import asyncio
from contextlib import asynccontextmanager
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

from models.schemas import UserQuery, ReportResponse
from agents.supervisor_agent import SupervisorAgent
from utils.logger import logger
from config.settings import METRICS_PORT


# 监控指标
REQUESTS_TOTAL = Counter('chatbi_requests_total', 'Total requests')
QUERY_DURATION = Histogram('chatbi_query_duration_seconds', 'Query duration in seconds')
ERRORS_TOTAL = Counter('chatbi_errors_total', 'Total errors')


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理
    启动时初始化Agent，关闭时清理资源
    """
    # 启动时
    logger.info("启动ChatBI服务...")
    app.state.supervisor = SupervisorAgent()
    
    # 健康检查
    health = await app.state.supervisor.health_check()
    logger.info(f"初始健康状态: {health}")
    
    yield
    
    # 关闭时
    logger.info("关闭ChatBI服务...")


# 创建FastAPI应用
app = FastAPI(
    title="ChatBI智能分析系统",
    description="基于NL2SQL的自然语言到数据可视化系统",
    version="1.0.0",
    lifespan=lifespan
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """请求处理时间中间件"""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


@app.get("/")
async def root():
    """根路径"""
    return {
        "service": "ChatBI智能分析系统",
        "version": "1.0.0",
        "status": "running"
    }


@app.post("/api/query", response_model=ReportResponse)
async def query(user_query: UserQuery):
    """
    处理自然语言查询
    返回SQL、数据和图表配置
    """
    REQUESTS_TOTAL.inc()
    
    logger.info(f"收到查询请求: {user_query.question}")
    
    try:
        with QUERY_DURATION.time():
            # 调用Supervisor Agent处理
            result = await app.state.supervisor.process(user_query.dict())
        
        if result["status"] == "error":
            ERRORS_TOTAL.inc()
        
        return result
        
    except Exception as e:
        ERRORS_TOTAL.inc()
        logger.exception(f"处理查询失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/health")
async def health_check():
    """健康检查接口"""
    health = await app.state.supervisor.health_check()
    return health


@app.get("/api/metrics")
async def get_metrics():
    """Prometheus监控指标接口"""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/api/schema/info")
async def get_schema_info():
    """获取数据库schema信息"""
    try:
        retriever = app.state.supervisor.schema_retriever
        stats = retriever.chroma_client.get_collection_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/schema/sync")
async def sync_schema():
    """手动触发schema同步"""
    try:
        from core.chroma_manager import ChromaManager
        manager = ChromaManager()
        manager.sync_schema_from_doris()
        return {"status": "success", "message": "Schema同步完成"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/examples")
async def get_examples():
    """获取示例问题"""
    examples = [
        "统计每个地区2023年的总销售额",
        "查看过去7天每天的订单数量变化趋势",
        "查询上个月销售额Top10的商品",
        "对比各渠道的ARPPU和付费率",
        "分析最近30天用户活跃时段分布"
    ]
    return {"examples": examples}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )