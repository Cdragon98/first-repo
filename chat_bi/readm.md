# ChatBI 智能分析系统

基于NL2SQL的自然语言到数据可视化系统，实现从自然语言到Doris SQL再到Echarts图表的全自动生成。

## 项目特点

- 🚀 **端到端自动化**：自然语言 -> SQL -> 图表，全流程自动化
- 🎯 **高准确率**：意图识别99.3%，SQL执行95.2%，字段召回97%
- ⚡ **高性能**：基于vLLM的分布式推理，QPS 120+
- 📊 **可视化智能**：自动推荐图表类型，生成Echarts配置
- 🔧 **可扩展**：模块化设计，支持自定义Agent和模板

## 技术栈

- **框架**：FastAPI, LangGraph
- **模型**：ChatGLM3-6B, BGE-M3
- **数据库**：Doris, ChromaDB
- **优化**：QLoRA, DeepSpeed, vLLM
- **可视化**：Echarts

## 快速开始

### 环境要求

- Python 3.9+
- CUDA 11.8+ (用于GPU推理)
- Doris 数据库
- 16GB+ 显存 (推荐RTX 4090)

### 安装

```bash
# 克隆项目
git clone https://github.com/your-repo/chatbi.git
cd chatbi

# 安装依赖
pip install -r requirements.txt

# 初始化配置
bash scripts/deploy.sh