#!/bin/bash
# ChatBI系统部署脚本

echo "开始部署ChatBI系统..."

# 1. 安装依赖
echo "安装Python依赖..."
pip install -r requirements.txt

# 2. 创建必要目录
echo "创建目录结构..."
mkdir -p data/chroma_db
mkdir -p data/synonyms
mkdir -p data/templates
mkdir -p logs

# 3. 初始化同义词库（示例）
echo "初始化同义词库..."
cat > data/synonyms/business_synonyms.json << EOF
{
    "销售额": ["gmv", "销售收入", "成交金额", "sales_amt"],
    "用户数": ["uv", "活跃用户", "用户量", "user_count"],
    "订单量": ["订单数", "下单量", "交易笔数", "order_count"],
    "利润": ["毛利", "净利润", "profit"],
    "城市": ["city", "地区", "区域"],
    "日期": ["date", "day", "时间", "order_date"],
    "商品": ["产品", "item", "product"],
    "渠道": ["channel", "来源", "source"]
}
EOF

# 4. 初始化SQL模板
echo "初始化SQL模板..."
cat > data/templates/sql_templates.yaml << EOF
维度统计查询: "SELECT [维度字段], [聚合函数(指标)] FROM [表名] GROUP BY [维度字段]"
时序统计查询: "SELECT [时间字段], [聚合函数(指标)] FROM [表名] WHERE [时间范围条件] GROUP BY [时间字段]"
时序分组统计查询: "SELECT [时间字段], [维度字段], [聚合函数(指标)] FROM [表名] WHERE [时间范围条件] GROUP BY [时间字段], [维度字段]"
窗口统计查询: "SELECT [字段列表], [窗口函数] OVER (PARTITION BY [分组字段] ORDER BY [排序字段]) AS [别名] FROM [表名]"
分组窗口统计查询: "SELECT [字段列表], [窗口函数] OVER (PARTITION BY [分组字段] ORDER BY [排序字段]) AS [别名] FROM [表名] GROUP BY [字段列表]"
时序分组窗口统计查询: "SELECT [时间字段], [维度字段], [窗口函数] OVER (PARTITION BY [维度字段] ORDER BY [时间字段]) AS [别名] FROM [表名] WHERE [时间范围条件]"
EOF

# 5. 初始化Echarts模板
echo "初始化Echarts模板..."
cat > data/templates/echarts_templates.yaml << EOF
bar_chart:
  title:
    text: "柱状图"
  tooltip:
    trigger: "axis"
  xAxis:
    type: "category"
  yAxis:
    type: "value"
  series:
    - type: "bar"

line_chart:
  title:
    text: "折线图"
  tooltip:
    trigger: "axis"
  xAxis:
    type: "category"
  yAxis:
    type: "value"
  series:
    - type: "line"
      smooth: true

pie_chart:
  title:
    text: "饼图"
  tooltip:
    trigger: "item"
  series:
    - type: "pie"
      radius: "50%"
EOF

# 6. 初始化向量数据库
echo "初始化向量数据库..."
python scripts/init_vector_db.py

# 7. 启动vLLM服务（如果使用本地模型）
echo "启动vLLM服务..."
# 请根据实际模型路径修改
# vllm serve /path/to/chatglm3-6b --port 8000 --max-model-len 4096 &

# 8. 启动FastAPI服务
echo "启动FastAPI服务..."
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

echo "部署完成！"