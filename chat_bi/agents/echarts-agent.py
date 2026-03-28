"""
Echarts Agent - 图表配置生成
根据SQL执行结果生成Echarts图表配置
对应文档中的"Echarts数据生成"模块
"""
import json
from typing import Dict, Any, List, Optional
import yaml
import re

from agents.base_agent import BaseAgent
from models.schemas import SQLResult, ChartType, EchartsConfig
from utils.logger import logger
from config.settings import ECHARTS_TEMPLATES_PATH


class EchartsAgent(BaseAgent):
    """
    图表生成Agent
    基于Echarts模板和微调模型生成可视化配置
    """
    
    def __init__(self, **kwargs):
        super().__init__(name="EchartsAgent", **kwargs)
        
        # 加载Echarts模板
        self.templates = self._load_templates()
        
        # 系统提示词（对应文档中的Echarts Agent提示词）
        self.system_prompt = """
你是一位专业的数据可视化工程师，能够根据SQL查询结果和指定的图表类型，生成符合Echarts标准的配置JSON。

请按照以下步骤操作：
1. 根据输入的图表类型选择对应的Echarts图表配置模板
2. 从SQL结果中提取X轴数据（如时间、分类字段）和Y轴数据（如数值指标）
3. 确保数据格式符合Echarts要求
4. 应用配置模板，补充通用配置项（标题、工具提示、图例等）
5. 输出符合Echarts规范的配置对象

图表类型说明：
- bar_chart: 柱状图，适合分类对比
- line_chart: 折线图，适合趋势展示
- pie_chart: 饼图，适合占比分析
- scatter_chart: 散点图，适合相关性分析
"""
    
    def _load_templates(self) -> Dict[str, Dict]:
        """加载Echarts模板"""
        try:
            with open(ECHARTS_TEMPLATES_PATH, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logger.warning(f"Echarts模板文件不存在: {ECHARTS_TEMPLATES_PATH}，使用内置模板")
            # 内置模板（对应文档中的模板）
            return {
                "bar_chart": {
                    "title": {"text": "数据分布"},
                    "tooltip": {"trigger": "axis"},
                    "xAxis": {"type": "category"},
                    "yAxis": {"type": "value"},
                    "series": [{"type": "bar"}]
                },
                "line_chart": {
                    "title": {"text": "趋势变化"},
                    "tooltip": {"trigger": "axis"},
                    "xAxis": {"type": "category"},
                    "yAxis": {"type": "value"},
                    "series": [{"type": "line", "smooth": True}]
                },
                "pie_chart": {
                    "title": {"text": "占比分析"},
                    "tooltip": {"trigger": "item"},
                    "series": [{"type": "pie", "radius": "50%"}]
                }
            }
    
    def _infer_chart_type(self, sql_result: SQLResult) -> ChartType:
        """
        根据数据特征推断图表类型
        
        Args:
            sql_result: SQL执行结果
            
        Returns:
            推荐的图表类型
        """
        if not sql_result.sql_result:
            return ChartType.TABLE
        
        # 检查是否有时间序列字段
        time_fields = ['date', 'day', 'month', 'year', 'time', 'order_date', 'sale_date']
        has_time = any(
            any(t in col.lower() for t in time_fields)
            for col in sql_result.columns
        )
        
        # 检查是否有分类字段
        categorical_fields = len(sql_result.columns) >= 2
        
        # 检查数据量
        data_size = sql_result.row_count
        
        if has_time and data_size > 1:
            return ChartType.LINE
        elif categorical_fields and data_size <= 10:
            return ChartType.PIE
        elif categorical_fields:
            return ChartType.BAR
        else:
            return ChartType.TABLE
    
    def _transform_data(self, sql_result: SQLResult, chart_type: ChartType) -> Dict[str, Any]:
        """
        转换数据格式以适应图表类型
        
        Args:
            sql_result: SQL执行结果
            chart_type: 图表类型
            
        Returns:
            转换后的数据
        """
        data = sql_result.sql_result
        
        if chart_type == ChartType.PIE:
            # 饼图数据格式: [{name: '分类', value: 数值}]
            pie_data = []
            for row in data[:10]:  # 饼图只取前10个
                values = list(row.values())
                if len(values) >= 2:
                    pie_data.append({
                        "name": str(values[0]),
                        "value": values[1] if isinstance(values[1], (int, float)) else 0
                    })
            return {"data": pie_data}
        
        elif chart_type in [ChartType.BAR, ChartType.LINE]:
            # 柱状图/折线图: x轴和y轴分离
            x_data = []
            y_data = []
            
            for row in data:
                values = list(row.values())
                if len(values) >= 2:
                    x_data.append(str(values[0]))
                    y_val = values[1] if isinstance(values[1], (int, float)) else 0
                    y_data.append(y_val)
            
            return {
                "xAxis": {"data": x_data},
                "series": [{"data": y_data}]
            }
        
        return {"raw_data": data}
    
    def _build_prompt(self, sql_result: SQLResult, chart_type: ChartType) -> list:
        """
        构建图表生成提示词
        
        Args:
            sql_result: SQL执行结果
            chart_type: 图表类型
            
        Returns:
            消息列表
        """
        messages = [
            {"role": "system", "content": self.system_prompt}
        ]
        
        # 添加示例
        examples = [
            {
                "data": [{"region": "华东", "total_sales": 300}, {"region": "华南", "total_sales": 250}],
                "chart_type": "pie_chart",
                "template": self.templates["pie_chart"],
                "output": {
                    "title": {"text": "地区销售额占比"},
                    "tooltip": {"trigger": "item"},
                    "series": [{
                        "name": "销售额",
                        "type": "pie",
                        "radius": "50%",
                        "data": [
                            {"value": 300, "name": "华东"},
                            {"value": 250, "name": "华南"}
                        ]
                    }]
                }
            }
        ]
        
        for ex in examples:
            messages.append({"role": "user", "content": json.dumps({
                "数据结果": ex["data"],
                "图表模板": ex["template"],
                "图表类型": ex["chart_type"]
            }, ensure_ascii=False)})
            messages.append({"role": "assistant", "content": json.dumps(ex["output"], ensure_ascii=False)})
        
        # 当前请求
        transformed_data = self._transform_data(sql_result, chart_type)
        
        messages.append({"role": "user", "content": json.dumps({
            "数据结果": sql_result.sql_result[:5],  # 预览前5条
            "图表模板": self.templates.get(chart_type, {}),
            "图表类型": chart_type
        }, ensure_ascii=False)})
        
        return messages
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成Echarts配置
        
        Args:
            input_data: 包含sql_result和可选的chart_type
            
        Returns:
            包含echarts_config的字典
        """
        sql_result = input_data.get("sql_result")
        chart_type = input_data.get("chart_type")
        
        self.log_step("开始图表生成", {"chart_type": chart_type})
        
        if not sql_result or not sql_result.sql_result:
            return {"error": "没有数据可生成图表"}
        
        # 如果没有指定图表类型，自动推断
        if not chart_type:
            chart_type = self._infer_chart_type(sql_result)
            self.log_step("自动推断图表类型", {"inferred": chart_type})
        
        # 构建提示词并调用LLM
        messages = self._build_prompt(sql_result, chart_type)
        response = await self.call_llm(messages, temperature=0.2)
        
        # 解析响应
        try:
            # 提取JSON部分
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                config = json.loads(json_match.group())
            else:
                config = json.loads(response)
            
            self.log_step("图表配置生成完成")
            
            return {
                "echarts_config": config,
                "chart_type": chart_type
            }
            
        except Exception as e:
            logger.error(f"解析图表配置失败: {str(e)}")
            
            # 返回基础配置
            base_config = {
                "title": {"text": "数据可视化"},
                "tooltip": {"trigger": "axis"},
                "xAxis": {"type": "category", "data": []},
                "yAxis": {"type": "value"},
                "series": [{"type": chart_type.replace("_chart", ""), "data": []}]
            }
            
            return {
                "echarts_config": base_config,
                "chart_type": chart_type,
                "error": str(e)
            }