# 智答：电商售后智能客服 Agent

一个面向电商售后场景的 AI 客服 Agent 作品集项目：用 Function Calling 做工具调度，用 RAG 回答政策类问题，用 SQLite 承载订单/退款数据，并对"裸模型 / RAG / Agent"三组方案做了对比评测。

## 项目亮点

- 5 个可落地工具：查订单状态、查售后政策、提交退货申请、查退款进度、转人工
- RAG + Chroma 知识库：22 条 FAQ，回答政策类问题
- Agent 调度：情绪检测转人工、错误兜底、工具参数校验
- 评测体系：50 题评测集，覆盖 RAG 准确性/相关性/完整性/安全性、Agent 工具选择/参数/任务完成率/误调用率、系统响应延迟
- 三组对比评测：baseline（裸模型）vs RAG vs Agent，CSV 结果与图表已归档

## 目录结构

```text
src/                   Python 源码（Agent、RAG、数据库、Gradio 界面、评测脚本）
01-tools/              Agent 工具 Schema
03-eval-dataset/       50 题评测集
04-rubric/             评分标准
05-scripts/            结果分析与图表生成
06-knowledge-base/     FAQ 知识库
portfolio-build/       作品集 PDF 与对比图表
day1-2-learning/       产品调研与 Prompt 学习资料
```

## 快速开始

```bash
cd src
pip install -r requirements.txt
cp .env.example .env   # 填入 DeepSeek API Key
python init_db.py      # 初始化 SQLite
python rag_engine.py   # 初始化向量库
python agent.py        # 命令行测试 Agent
python app.py          # 启动 Web 界面 http://localhost:7860
```

## 评测数据

- `05-scripts/results/eval_baseline_20260729_1037.csv`：裸模型基线
- `05-scripts/results/eval_rag_20260729_1040.csv`：RAG 方案
- `05-scripts/results/eval_agent_20260729_1050.csv`：Agent 方案
- `05-scripts/results/charts/`：对比图表

## 免责说明

- `src/.env` 与本地数据文件不入库，请自行配置密钥
- 项目定位为 AI 产品经理作品集，包含产品文档、评测体系与可运行实现
