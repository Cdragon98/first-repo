"""
SQL Agent - SQL生成与执行
负责根据意图要素和字段召回结果生成Doris SQL，并执行查询
对应文档中的"SQL（Doris）生成"模块
"""
import json
from typing import Dict, Any, Optional
import yaml
import re
import time

from agents.base_agent import BaseAgent
from models.schemas import IntentElements, SQLResult
from core.schema_retriever import SchemaRetriever
from core.sql_executor import DorisExecutor
from core.syntax_validator import SyntaxValidator
from utils.logger import logger
from config.settings import SQL_TEMPLATES_PATH


class SQLAgent(BaseAgent):
    """
    SQL生成Agent
    基于SQL模板和微调的ChatGLM3-6B生成Doris SQL
    执行准确率达95.2%（文档数据）
    """
    
    def __init__(self, schema_retriever: SchemaRetriever = None, **kwargs):
        super().__init__(name="SQLAgent", **kwargs)
        
        # 初始化组件
        self.schema_retriever = schema_retriever or SchemaRetriever()
        self.sql_executor = DorisExecutor()
        self.syntax_validator = SyntaxValidator(dialect="mysql")
        
        # 加载SQL模板
        self.sql_templates = self._load_sql_templates()
        
        # Few-shot示例
        self.few_shot_examples = [
            {
                "user_question": "统计每个地区2023年的总销售额",
                "elements": {
                    "sql_type": "时序分组统计查询",
                    "table_name": "sales_records",
                    "fields": ["region", "sale_date"],
                    "metrics": [{"name": "total_sales", "operation": "SUM(amount)"}],
                    "time_range": "2023年"
                },
                "sql_template": "SELECT [维度字段], [聚合函数(指标)] FROM [表名] WHERE [时间范围条件] GROUP BY [维度字段]",
                "generated_sql": "SELECT region, SUM(amount) AS total_sales FROM sales_records WHERE sale_date BETWEEN '2023-01-01' AND '2023-12-31' GROUP BY region"
            },
            {
                "user_question": "查看过去7天每天的订单数量变化趋势",
                "elements": {
                    "sql_type": "时序统计查询",
                    "table_name": "orders",
                    "fields": ["order_date"],
                    "metrics": [{"name": "order_count", "operation": "COUNT(order_id)"}],
                    "time_range": "过去7天"
                },
                "sql_template": "SELECT [时间字段], [聚合函数(指标)] FROM [表名] WHERE [时间范围条件] GROUP BY [时间字段]",
                "generated_sql": "SELECT order_date, COUNT(order_id) AS order_count FROM orders WHERE order_date >= CURRENT_DATE - INTERVAL 7 DAY GROUP BY order_date ORDER BY order_date"
            }
        ]
        
        # 系统提示词
        self.system_prompt = """
你是一位高级SQL开发专家，擅长将提供的指令和sql模板编写出语法严谨，可精准执行的Doris SQL:

Doris SQL特点：
- 兼容MySQL协议
- 支持BITMAP精确去重：BITMAP_UNION(TO_BITMAP(column))
- 日期函数：DATE_FORMAT、DATE_TRUNC、INTERVAL
- 窗口函数：ROW_NUMBER()、RANK()、LAG()等

请严格按照提供的SQL模板格式生成SQL，确保语法正确。
"""
    
    def _load_sql_templates(self) -> Dict[str, str]:
        """加载SQL模板"""
        try:
            with open(SQL_TEMPLATES_PATH, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logger.warning(f"SQL模板文件不存在: {SQL_TEMPLATES_PATH}，使用内置模板")
            # 内置模板（对应文档中的SQL模板）
            return {
                "维度统计查询": "SELECT [维度字段], [聚合函数(指标)] FROM [表名] GROUP BY [维度字段]",
                "时序统计查询": "SELECT [时间字段], [聚合函数(指标)] FROM [表名] WHERE [时间范围条件] GROUP BY [时间字段]",
                "时序分组统计查询": "SELECT [时间字段], [维度字段], [聚合函数(指标)] FROM [表名] WHERE [时间范围条件] GROUP BY [时间字段], [维度字段]",
                "窗口统计查询": "SELECT [字段列表], [窗口函数] OVER (PARTITION BY [分组字段] ORDER BY [排序字段]) AS [别名] FROM [表名]",
                "分组窗口统计查询": "SELECT [字段列表], [窗口函数] OVER (PARTITION BY [分组字段] ORDER BY [排序字段]) AS [别名] FROM [表名] GROUP BY [字段列表]",
                "时序分组窗口统计查询": "SELECT [时间字段], [维度字段], [窗口函数] OVER (PARTITION BY [维度字段] ORDER BY [时间字段]) AS [别名] FROM [表名] WHERE [时间范围条件]"
            }
    
    def _build_prompt(self, question: str, elements: IntentElements, retrieved_fields: Dict) -> list:
        """
        构建SQL生成提示词
        
        Args:
            question: 原始问题
            elements: 意图要素
            retrieved_fields: 召回的字段信息
            
        Returns:
            消息列表
        """
        messages = [
            {"role": "system", "content": self.system_prompt}
        ]
        
        # 添加Few-shot示例
        for example in self.few_shot_examples:
            messages.append({"role": "user", "content": json.dumps({
                "用户问题": example["user_question"],
                "要素列表": example["elements"],
                "SQL模板": example["sql_template"]
            }, ensure_ascii=False)})
            messages.append({"role": "assistant", "content": example["generated_sql"]})
        
        # 获取SQL模板
        template = self.sql_templates.get(elements.sql_type, self.sql_templates["维度统计查询"])
        
        # 构建当前请求
        current_request = {
            "用户问题": question,
            "要素列表": elements.dict(),
            "SQL模板": template,
            "可用字段": retrieved_fields  # 提供字段信息帮助模型选择
        }
        
        messages.append({"role": "user", "content": json.dumps(current_request, ensure_ascii=False)})
        
        return messages
    
    def _apply_syntax_constraint(self, sql: str) -> str:
        """
        应用语法约束解码
        根据AST模板库动态检查和修复SQL
        
        Args:
            sql: 生成的SQL
            
        Returns:
            约束后的SQL
        """
        # 步骤1：验证AST
        validation = self.syntax_validator.validate_ast(sql)
        
        if validation["valid"]:
            return sql
        
        # 步骤2：尝试修复常见错误
        fixed_sql = self.syntax_validator.fix_common_errors(sql)
        
        # 步骤3：再次验证
        validation = self.syntax_validator.validate_ast(fixed_sql)
        if validation["valid"]:
            logger.info(f"SQL语法修复成功: {sql} -> {fixed_sql}")
            return fixed_sql
        
        # 步骤4：如果仍然无效，记录错误
        logger.error(f"SQL语法无法修复: {sql}, 错误: {validation.get('error')}")
        return sql  # 返回原SQL，让执行器处理
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成并执行SQL
        
        Args:
            input_data: 包含question、elements的字典
            
        Returns:
            包含SQL和结果的字典
        """
        start_time = time.time()
        
        question = input_data.get("question", "")
        elements = input_data.get("elements")
        
        self.log_step("开始SQL生成", {"question": question, "sql_type": elements.sql_type})
        
        if not elements:
            return {"error": "缺少意图要素"}
        
        # 步骤1：字段召回
        retrieved_fields = self.schema_retriever.retrieve_fields(elements)
        self.log_step("字段召回完成", {"tables": list(retrieved_fields["tables"].keys())})
        
        # 步骤2：生成SQL
        messages = self._build_prompt(question, elements, retrieved_fields)
        generated_sql = await self.call_llm(messages)
        
        # 步骤3：语法约束
        validated_sql = self._apply_syntax_constraint(generated_sql)
        
        self.log_step("SQL生成完成", {"sql": validated_sql})
        
        # 步骤4：执行SQL
        try:
            sql_result = self.sql_executor.execute(validated_sql)
            
            elapsed = (time.time() - start_time) * 1000
            sql_result.execution_time_ms = elapsed
            
            self.log_step("SQL执行完成", {
                "rows": sql_result.row_count,
                "time_ms": elapsed
            })
            
            return {
                "sql_query": validated_sql,
                "sql_result": sql_result,
                "retrieved_fields": retrieved_fields
            }
            
        except Exception as e:
            logger.error(f"SQL执行失败: {str(e)}")
            
            # 记录错误样本用于后续迭代训练（文档中的执行反馈闭环）
            self._record_error_sample(question, elements, validated_sql, str(e))
            
            return {
                "sql_query": validated_sql,
                "error": str(e),
                "sql_result": None
            }
    
    def _record_error_sample(self, question: str, elements: IntentElements, sql: str, error: str):
        """
        记录错误样本用于模型迭代训练
        对应文档中的"执行反馈闭环"
        """
        error_sample = {
            "question": question,
            "elements": elements.dict(),
            "sql": sql,
            "error": error,
            "timestamp": time.time()
        }
        
        # 实际项目中可以写入文件或数据库
        logger.info(f"记录错误样本: {error_sample}")
        # TODO: 实现错误样本存储