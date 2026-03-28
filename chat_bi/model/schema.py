"""
Pydantic数据模型定义
定义了系统中所有数据结构和API接口的格式
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Union
from enum import Enum
from datetime import datetime


class SQLType(str, Enum):
    """SQL查询类型枚举"""
    DETAIL_QUERY = "明细查询"  # 简单明细查询
    DIMENSION_STAT = "维度统计查询"  # 按维度统计
    TIME_SERIES_STAT = "时序统计查询"  # 时间序列统计
    TIME_SERIES_GROUP = "时序分组统计查询"  # 时序分组统计
    WINDOW_STAT = "窗口统计查询"  # 窗口函数统计
    GROUP_WINDOW = "分组窗口统计查询"  # 分组窗口统计
    TIME_WINDOW = "时序分组窗口统计查询"  # 时序窗口统计


class ChartType(str, Enum):
    """图表类型枚举"""
    BAR = "bar_chart"  # 柱状图
    LINE = "line_chart"  # 折线图
    PIE = "pie_chart"  # 饼图
    SCATTER = "scatter_chart"  # 散点图
    TABLE = "table"  # 表格


class Metric(BaseModel):
    """指标定义"""
    name: str = Field(description="指标名称，如 'total_sales'")
    operation: str = Field(description="聚合操作，如 'SUM(amount)'")
    alias: Optional[str] = Field(None, description="别名")


class IntentElements(BaseModel):
    """意图识别提取的要素"""
    sql_type: SQLType = Field(description="SQL操作类型")
    table_name: str = Field(description="主表名")
    fields: List[str] = Field(default_factory=list, description="查询字段")
    metrics: List[Metric] = Field(default_factory=list, description="指标及计算规则")
    time_range: Optional[str] = Field(None, description="时间范围，如'最近7天'")
    filters: Optional[List[Dict[str, Any]]] = Field(None, description="过滤条件")
    group_by: Optional[List[str]] = Field(None, description="分组字段")
    chart_type: ChartType = Field(ChartType.TABLE, description="推荐图表类型")
    
    class Config:
        use_enum_values = True


class SQLResult(BaseModel):
    """SQL执行结果"""
    sql_query: str = Field(description="生成的SQL语句")
    sql_result: List[Dict[str, Any]] = Field(description="查询结果数据")
    columns: List[str] = Field(description="列名")
    row_count: int = Field(description="行数")
    execution_time_ms: float = Field(description="执行耗时(ms)")


class EchartsConfig(BaseModel):
    """Echarts图表配置"""
    title: Optional[Dict[str, Any]] = Field(None, description="标题配置")
    tooltip: Dict[str, Any] = Field(default={"trigger": "axis"}, description="提示框配置")
    xAxis: Optional[Dict[str, Any]] = Field(None, description="X轴配置")
    yAxis: Optional[Dict[str, Any]] = Field(None, description="Y轴配置")
    series: List[Dict[str, Any]] = Field(..., description="数据系列")
    legend: Optional[Dict[str, Any]] = Field(None, description="图例")
    grid: Optional[Dict[str, Any]] = Field(None, description="网格配置")
    color: Optional[List[str]] = Field(None, description="主题配色")


class ReportResponse(BaseModel):
    """最终报表响应"""
    original_question: str = Field(description="用户原始问题")
    sql_query: str = Field(description="生成的SQL语句")
    sql_result_preview: List[Dict[str, Any]] = Field(description="数据预览(前5条)")
    echarts_config: Optional[Dict[str, Any]] = Field(None, description="Echarts配置")
    status: str = Field(description="状态: success/error")
    error_message: Optional[str] = Field(None, description="错误信息")
    processing_time_ms: float = Field(description="总处理耗时(ms)")


class UserQuery(BaseModel):
    """用户查询请求"""
    question: str = Field(..., description="自然语言问题", min_length=1, max_length=500)
    user_id: Optional[str] = Field(None, description="用户ID")
    prefer_chart: Optional[ChartType] = Field(None, description="用户偏好的图表类型")
    
    @validator('question')
    def question_not_empty(cls, v):
        if not v or v.strip() == '':
            raise ValueError('问题不能为空')
        return v.strip()