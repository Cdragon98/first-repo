"""
监控指标工具
"""
from prometheus_client import Counter, Histogram, Gauge
import time
from contextlib import contextmanager


# 定义指标
request_count = Counter('chatbi_requests_total', 'Total requests', ['endpoint'])
request_duration = Histogram('chatbi_request_duration_seconds', 'Request duration', ['endpoint'])
error_count = Counter('chatbi_errors_total', 'Total errors', ['type'])
active_queries = Gauge('chatbi_active_queries', 'Active queries')


@contextmanager
def track_request(endpoint: str):
    """
    跟踪请求的上下文管理器
    
    Args:
        endpoint: API端点
    """
    request_count.labels(endpoint=endpoint).inc()
    active_queries.inc()
    
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        request_duration.labels(endpoint=endpoint).observe(duration)
        active_queries.dec()


def track_error(error_type: str):
    """
    记录错误
    
    Args:
        error_type: 错误类型
    """
    error_count.labels(type=error_type).inc()