"""
Instruction Agent - 意图识别与要素提取
负责从用户自然语言问题中提取SQL类型、表名、字段、指标和图表类型
对应文档中的"意图识别——要素提取"模块
"""
import json
from typing import Dict, Any, Optional
import re

from agents.base_agent import BaseAgent
from models.schemas import IntentElements, SQLType, ChartType, Metric
from utils.logger import logger
from config.settings import SYNONYMS_PATH
import yaml


class InstructionAgent(BaseAgent):
    """
    意图识别Agent
    基于Few-shot Prompt和微调的ChatGLM3-6B模型
    准确率达99.3%（文档数据）
    """
    
    def __init__(self, **kwargs):
        super().__init__(name="InstructionAgent", **kwargs)
        
        # 加载同义词库
        self.synonyms = self._load_synonyms()
        
        # Few-shot示例
        self.few_shot_examples = [
            {
                "question": "统计每个地区2023年的总销售额",
                "output": {
                    "sql_type": "时序分组统计查询",
                    "table_name": "sales_records",
                    "fields": ["region", "sale_date"],
                    "metrics": [{"name": "total_sales", "operation": "SUM(amount)"}],
                    "time_range": "2023年",
                    "chart_type": "bar_chart"
                }
            },
            {
                "question": "查看过去7天每天的订单数量变化趋势",
                "output": {
                    "sql_type": "时序统计查询",
                    "table_name": "orders",
                    "fields": ["order_date"],
                    "metrics": [{"name": "order_count", "operation": "COUNT(order_id)"}],
                    "time_range": "过去7天",
                    "chart_type": "line_chart"
                }
            },
            {
                "question": "查询上个月销售额Top10的商品",
                "output": {
                    "sql_type": "维度统计查询",
                    "table_name": "sales_detail",
                    "fields": ["product_name"],
                    "metrics": [{"name": "total_sales", "operation": "SUM(amount)"}],
                    "time_range": "上个月",
                    "filters": [{"field": "product_name", "op": "is not null"}],
                    "chart_type": "bar_chart"
                }
            },
            {
                "question": "对比各渠道的ARPPU和付费率",
                "output": {
                    "sql_type": "维度统计查询",
                    "table_name": "user_payments",
                    "fields": ["channel"],
                    "metrics": [
                        {"name": "arppu", "operation": "SUM(payment)/COUNT(DISTINCT user_id)"},
                        {"name": "pay_rate", "operation": "COUNT(DISTINCT payer_id)/COUNT(DISTINCT user_id)"}
                    ],
                    "chart_type": "bar_chart"
                }
            }
        ]
        
        # 系统提示词模板（对应文档中的InstructionAgent提示词）
        self.system_prompt = """
你是一位高级问题理解专家，擅长对用户问题进行意图识别并可以挖掘用户问题的潜在信息做要素提取，之后并将其转为规范的新指令：

1. SQL类型：从问题中识别出用户请求的SQL操作类型。可能的类型包括：
- 明细查询：用于检索表中的详细记录。
- 维度统计查询：基于一个或多个维度对数据进行汇总统计。
- 时序统计查询：针对时间序列数据进行统计分析。
- 时序分组统计查询：按时间段对时间序列数据进行分组统计。
- 窗口统计查询：在不使用GROUP BY的情况下，对查询结果集的一部分进行进行计算。
- 分组窗口统计查询：结合窗口函数与GROUP BY语句来执行复杂的数据分析。
- 时序分组窗口统计查询：专门处理时间序列数据的高级统计分析。

2. 表名：识别用户提问中提及的主要数据库表名称。

3. 字段名：找出所有相关字段名或列标识符。

4. 指标名及计算规则：如果适用，请指出用户希望计算的指标及其计算方法（如SUM， AVG等）。

5. 图表类型建议：根据用户的查询需求，推荐一种最适合展示结果的图表类型（如柱状图、饼图、折线图等）。

请严格按照JSON格式返回结果。
"""
    
    def _load_synonyms(self) -> Dict[str, list]:
        """加载业务同义词库"""
        try:
            with open(SYNONYMS_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"同义词库不存在: {SYNONYMS_PATH}，使用空字典")
            return {}
    
    def _apply_synonym_enhancement(self, question: str) -> str:
        """
        同义词增强
        将问题中的业务术语扩展为完整形式
        
        Args:
            question: 原始问题
            
        Returns:
            增强后的问题
        """
        enhanced = question
        
        # 应用同义词替换（从文档中的同义词库）
        synonym_map = {
            r'\bDAU\b': '日活跃用户数',
            r'\bARPPU\b': '每付费用户平均收入',
            r'\bGMV\b': '商品交易总额',
            r'\bLTV\b': '用户生命周期价值',
            r'\b次留\b': '次日留存率',
            r'\b7留\b': '7日留存率'
        }
        
        for pattern, replacement in synonym_map.items():
            enhanced = re.sub(pattern, f"{replacement}({pattern})", enhanced)
        
        return enhanced
    
    def _build_prompt(self, question: str) -> list:
        """
        构建Few-shot提示词
        
        Args:
            question: 用户问题
            
        Returns:
            消息列表
        """
        messages = [
            {"role": "system", "content": self.system_prompt}
        ]
        
        # 添加Few-shot示例
        for example in self.few_shot_examples:
            messages.append({"role": "user", "content": example["question"]})
            messages.append({"role": "assistant", "content": json.dumps(example["output"], ensure_ascii=False)})
        
        # 添加当前问题
        enhanced_question = self._apply_synonym_enhancement(question)
        messages.append({"role": "user", "content": enhanced_question})
        
        return messages
    
    def _parse_response(self, response: str) -> IntentElements:
        """
        解析模型响应为结构化对象
        
        Args:
            response: 模型返回的JSON字符串
            
        Returns:
            IntentElements对象
        """
        try:
            # 提取JSON部分（处理模型可能返回的额外文本）
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                data = json.loads(json_str)
            else:
                data = json.loads(response)
            
            # 转换指标列表
            metrics = []
            for m in data.get('metrics', []):
                if isinstance(m, dict):
                    metrics.append(Metric(**m))
                elif isinstance(m, str):
                    # 处理简单字符串格式
                    metrics.append(Metric(name=m, operation=m))
            
            # 创建IntentElements对象
            return IntentElements(
                sql_type=data.get('sql_type', SQLType.DETAIL_QUERY),
                table_name=data.get('table_name', ''),
                fields=data.get('fields', []),
                metrics=metrics,
                time_range=data.get('time_range'),
                filters=data.get('filters'),
                group_by=data.get('group_by'),
                chart_type=data.get('chart_type', ChartType.TABLE)
            )
            
        except Exception as e:
            logger.error(f"解析意图识别结果失败: {str(e)}, response: {response}")
            # 返回默认值
            return IntentElements(
                sql_type=SQLType.DETAIL_QUERY,
                table_name="unknown",
                chart_type=ChartType.TABLE
            )
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理用户问题，提取意图要素
        
        Args:
            input_data: 包含"question"字段的字典
            
        Returns:
            包含意图要素的字典
        """
        self.log_step("开始意图识别", {"question": input_data.get("question")})
        
        question = input_data.get("question", "")
        if not question:
            return {"error": "问题不能为空"}
        
        # 构建提示词并调用LLM
        messages = self._build_prompt(question)
        response = await self.call_llm(messages)
        
        # 解析响应
        elements = self._parse_response(response)
        
        # 记录识别结果
        self.log_step("意图识别完成", {
            "sql_type": elements.sql_type,
            "table": elements.table_name,
            "chart_type": elements.chart_type
        })
        
        return {
            "elements": elements,
            "raw_response": response
        }