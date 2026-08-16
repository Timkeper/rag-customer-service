"""
全局配置文件
所有可调参数集中在这里，方便管理和面试时解释"为什么这么设"
"""

import os
from dotenv import load_dotenv

# 加载.env文件里的API Key（避免把Key硬编码到代码里，这是工程规范）
load_dotenv()

# ============ 大模型配置 ============
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "sk-在这里填你的key")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"  # DeepSeek的API地址
MODEL_NAME = "deepseek-chat"                     # DeepSeek的对话模型

# 备选：通义千问（如果DeepSeek额度用完）
# BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
# MODEL_NAME = "qwen-plus"

# ============ 智谱配置（用于Embedding，国内免费额度足够）============
# 说明：DeepSeek不提供Embedding接口，用智谱做向量化
# 注册 https://open.bigmodel.cn 即送免费额度，本项目花费为0
ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY", "在这里填智谱的key")
ZHIPU_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
EMBEDDING_MODEL = "embedding-2"  # 智谱的Embedding模型，中文效果好

# ============ 生成参数（面试会问"为什么这么设"）============
TEMPERATURE = 0.3    # 温度：客服场景要准确，所以设低（0=最确定，1=最随机）
MAX_TOKENS = 1000    # 单次回复最大长度
TOP_P = 0.9          # 核采样：和温度配合控制随机性

# ============ RAG配置 ============
CHUNK_SIZE = 300          # 知识库分块大小（字）。太小丢上下文，太大召回不准
CHUNK_OVERLAP = 50        # 分块重叠（字），避免切断关键信息
RETRIEVAL_TOP_K = 3       # 召回前K条最相关的FAQ。K越大信息越全但可能引入噪音

# ============ 向量库配置 ============
CHROMA_PERSIST_DIR = "./data/chroma_db"  # Chroma数据存这里（会自动创建）

# ============ 业务数据库 ============
SQLITE_DB_PATH = "./data/orders.db"      # SQLite数据库文件路径

# ============ 知识库 ============
FAQ_FILE = "../06-knowledge-base/faq_knowledge_base.md"  # FAQ源文件

# ============ Agent配置 ============
HUMAN_ESCALATION_AMOUNT = 500  # 退货金额超过这个值要转人工（元）
HUMAN_KEYWORDS = [              # 触发转人工的关键词（情绪类 + 主动要求类）
    # 情绪激烈类
    "投诉", "曝光", "315", "差评", "气死", "垃圾", "破烂", "骗子", "报警",
    # 主动要求转人工类（优化点：用户明确要求应直接转，不再追问原因）
    "转人工", "找人工", "人工客服", "找人", "转接人工", "真人"
]
MAX_RETRY_BEFORE_HUMAN = 2      # 同一问题失败几次后转人工

# ============ 评测配置 ============
EVAL_DATASET_PATH = "../03-eval-dataset/eval_dataset_50.json"
EVAL_RESULTS_DIR = "../05-scripts/results"

# ============ 提示词（系统Prompt）============
SYSTEM_PROMPT = """你是一名专业的电商售后客服，名叫"小答"。

你的职责：
1. 解答退货、换货、退款、物流等售后问题
2. 帮用户查询订单状态、提交退货申请
3. 必要时转接人工客服

回答要求：
- 语气亲切专业，称呼用户"您"，简明扼要，多用分点和表情符号增强可读性
- 回答基于知识库事实，绝不编造政策、订单号或物流信息
- 不确定时说"我帮您确认一下"而非瞎答
- 涉及金额超过500元的退货，提示需人工确认
- 订单号必须是A开头加6位数字，不完整时请向用户确认

工具结果处理（重要）：
- 当工具返回"订单号不存在"或"error"时，【禁止编造】任何订单信息。要诚实告知用户"很抱歉，没有查询到该订单"，并礼貌地请用户核对订单号是否正确，或建议提供下单手机号/收货人姓名以便人工核实，或主动提出转接人工客服。
- 当工具返回真实数据时，基于数据如实回答，不得添加未经查询的信息。

可用工具：
- query_order_status：查订单物流
- query_return_policy：查退货政策（走知识库）
- submit_return_request：提交退货/换货
- check_refund_progress：查退款进度
- escalate_to_human：转人工
"""
