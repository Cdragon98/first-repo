"""
Supervisor Agent - 总控协调Agent
负责整体链路设计，协调多个子Agent完成端到端任务
对应文档中的"LangGraph开发"和Supervisor Agent提示词
"""
from typing import Dict, Any, Optional
import time
import asyncio
from loguru import logger

from agents.base_agent import BaseAgent
from agents.instruction_agent import InstructionAgent
from agents.sql_agent import SQLAgent
from agents.echarts_agent import EchartsAgent
from core.schema_retriever import SchemaRetriever
from models.schemas import ReportResponse, UserQuery


class SupervisorAgent(BaseAgent):
    """
    总控Agent
    负责全局状态管理，协调任务流转与异常处理
    实现完整的Agent协作架构
    """
    
    def __init__(self, **kwargs):
        super().__init__(name="SupervisorAgent", **kwargs)
        
        # 初始化子Agent
        self.schema_retriever = SchemaRetriever()
        self.instruction_agent = InstructionAgent(**kwargs)
        self.sql_agent = SQLAgent(schema_retriever=self.schema_retriever, **kwargs)
        self.echarts_agent = EchartsAgent(**kwargs)
        
        # 状态管理
        self.current_state = {}
        
        # 系统提示词（对应文档中的Supervisor Agent提示词）
        self.system_prompt = """
你是一位智能报表生成系统的总控工程师，能够协调多个子Agent（Instruction Agent、SQL Agent、Echarts Agent）完成用户问题的自动化处理。

任务目标：
根据用户输入的自然语言问题，自动完成以下流程：
1. 意图解析：通过Instruction Agent提取SQL类型、表名、字段、指标及图表类型
2. SQL生成与执行：调用SQL Agent生成SQL语句并执行，获取数据结果
3. 可视化配置：通过Echarts Agent将数据结果与图表类型结合，生成Echarts配置JSON
4. 整合输出：将所有结果整合为最终报表（含SQL、数据预览、图表配置）

错误处理机制：
- 若Instruction Agent无法解析问题：返回错误提示并请求用户澄清
- 若SQL执行失败：返回错误信息，并提示修正建议
- 若Echarts配置异常：检查数据格式与图表类型是否匹配，返回错误提示
"""
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理用户请求的主流程
        
        Args:
            input_data: 包含用户问题的字典
            
        Returns:
            最终报表结果
        """
        start_time = time.time()
        
        question = input_data.get("question", "")
        user_id = input_data.get("user_id", "anonymous")
        prefer_chart = input_data.get("prefer_chart")
        
        self.log_step("开始处理用户请求", {
            "question": question,
            "user_id": user_id
        })
        
        # 初始化状态
        state = {
            "question": question,
            "user_id": user_id,
            "prefer_chart": prefer_chart,
            "start_time": start_time,
            "steps": []
        }
        
        try:
            # 步骤1：意图识别
            self.log_step("步骤1: 意图识别")
            instruction_result = await self.instruction_agent.process({"question": question})
            state["steps"].append({"step": "instruction", "result": instruction_result})
            
            if "error" in instruction_result:
                return self._build_error_response(
                    question=question,
                    error=instruction_result["error"],
                    step="instruction",
                    start_time=start_time
                )
            
            elements = instruction_result["elements"]
            
            # 如果用户指定了图表类型，覆盖推荐
            if prefer_chart:
                elements.chart_type = prefer_chart
            
            # 步骤2：SQL生成与执行
            self.log_step("步骤2: SQL生成与执行")
            sql_result = await self.sql_agent.process({
                "question": question,
                "elements": elements
            })
            state["steps"].append({"step": "sql", "result": sql_result})
            
            if "error" in sql_result:
                return self._build_error_response(
                    question=question,
                    error=sql_result["error"],
                    step="sql",
                    start_time=start_time,
                    sql_query=sql_result.get("sql_query")
                )
            
            # 步骤3：图表生成
            self.log_step("步骤3: 图表生成")
            chart_result = await self.echarts_agent.process({
                "sql_result": sql_result["sql_result"],
                "chart_type": elements.chart_type
            })
            state["steps"].append({"step": "echarts", "result": chart_result})
            
            # 步骤4：整合输出
            total_time = (time.time() - start_time) * 1000
            
            response = ReportResponse(
                original_question=question,
                sql_query=sql_result["sql_query"],
                sql_result_preview=sql_result["sql_result"].sql_result[:5],  # 预览前5条
                echarts_config=chart_result.get("echarts_config"),
                status="success",
                processing_time_ms=total_time
            )
            
            self.log_step("处理完成", {
                "total_time_ms": total_time,
                "row_count": sql_result["sql_result"].row_count
            })
            
            return response.dict()
            
        except Exception as e:
            logger.exception(f"处理过程中发生异常: {str(e)}")
            total_time = (time.time() - start_time) * 1000
            
            return self._build_error_response(
                question=question,
                error=f"系统内部错误: {str(e)}",
                step="system",
                start_time=start_time
            )
    
    def _build_error_response(self, question: str, error: str, step: str, 
                              start_time: float, sql_query: Optional[str] = None) -> Dict:
        """
        构建错误响应
        
        Args:
            question: 原始问题
            error: 错误信息
            step: 出错步骤
            start_time: 开始时间
            sql_query: 可能生成的SQL
            
        Returns:
            错误响应字典
        """
        total_time = (time.time() - start_time) * 1000
        
        response = ReportResponse(
            original_question=question,
            sql_query=sql_query or "",
            sql_result_preview=[],
            status="error",
            error_message=f"[{step}] {error}",
            processing_time_ms=total_time
        )
        
        return response.dict()
    
    async def health_check(self) -> Dict[str, Any]:
        """
        健康检查
        
        Returns:
            各组件健康状态
        """
        health_status = {
            "status": "healthy",
            "components": {}
        }
        
        # 检查ChromaDB连接
        try:
            self.schema_retriever.collection.count()
            health_status["components"]["chromadb"] = "healthy"
        except Exception as e:
            health_status["components"]["chromadb"] = f"unhealthy: {str(e)}"
            health_status["status"] = "degraded"
        
        # 检查vLLM服务
        try:
            await self.call_llm([{"role": "user", "content": "ping"}])
            health_status["components"]["vllm"] = "healthy"
        except Exception as e:
            health_status["components"]["vllm"] = f"unhealthy: {str(e)}"
            health_status["status"] = "degraded"
        
        # 检查Doris连接
        try:
            self.sql_agent.sql_executor.test_connection()
            health_status["components"]["doris"] = "healthy"
        except Exception as e:
            health_status["components"]["doris"] = f"unhealthy: {str(e)}"
            health_status["status"] = "degraded"
        
        return health_status    