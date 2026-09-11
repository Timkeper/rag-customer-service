"""
全局配置文件
所有可调参数集中在这里，方便管理和面试时解释"为什么这么设"
"""

import os
from dotenv import load_dotenv

# 加载.env文件里的API Key（避免把Key硬编码到代码里，这是工程规范）
load_dotenv()

# 云托管兜底：CLI 部署暂不支持注入环境变量时，从构建期生成的 _cloud_env.py 读取（gitignored）
try:
    import _cloud_env as _ce
    os.environ.setdefault("DEEPSEEK_API_KEY", _ce.DEEPSEEK_API_KEY)
    os.environ.setdefault("ZHIPU_API_KEY", _ce.ZHIPU_API_KEY)
except ImportError:
    pass

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

# ============ 会话与鉴权（v2 新增）============
SESSION_HISTORY_WINDOW = 10      # 多轮对话携带的最近消息条数

# ============ Agentic 办结策略引擎（v2 新增）============
# 设计原则：AI 可以"直接办事"，但必须在策略引擎划定的额度与条件内，全程审计
POLICY = {
    "auto_refund": {             # 自动退款
        "single_limit": 500,     # 单笔上限（元）——超过必须转人工
        "daily_limit": 1000,     # 同一用户当日累计上限
        "daily_count": 3,        # 同一用户当日次数上限
    },
    "reship": {                  # 自动补发
        "single_limit": 300,
        "daily_limit": 600,
        "daily_count": 2,
    },
    "change_address": {          # 改地址：仅"待发货"状态允许
        "allowed_status": ["待发货"],
    },
}
UNDO_WINDOW_HOURS = 24           # 办结动作可撤销窗口（小时）

# ============ 坐席工作台（v2 新增）============
AGENT_CONSOLE_PASSWORD = os.getenv("AGENT_CONSOLE_PASSWORD", "zhida2026")

# ============ 评测配置 ============
EVAL_DATASET_PATH = "../03-eval-dataset/eval_dataset_50.json"
EVAL_RESULTS_DIR = "../05-scripts/results"

# ============ 提示词（系统Prompt）============
SYSTEM_PROMPT = """你是一名专业的电商售后客服，名叫"小答"，具备"直接办事"的能力。

你的职责：
1. 解答退货、换货、退款、物流等售后问题
2. 帮用户查询订单状态、提交退货申请
3. 在策略允许范围内【直接办结】：自动退款、补发、修改地址（详见下方办结规则）
4. 超出权限或复杂情况，转接人工客服

回答要求：
- 语气亲切专业，称呼用户"您"，简明扼要，多用分点和表情符号增强可读性
- 回答基于知识库事实，绝不编造政策、订单号或物流信息
- 【政策类必查】凡涉及退货/换货/退款/保修/运费规则的问题，必须先调用 query_return_policy 检索知识库再作答，禁止凭记忆直接回答政策
- 不确定时说"我帮您确认一下"而非瞎答
- 订单号必须是A开头加6位数字；用户消息中已有完整订单号时直接使用并查询，不要反问确认
- 用户说"我的快递/我的订单/这个订单"等指代表达，且会话信息中名下只有一笔订单时，默认指该订单并直接查询办理，不要反问
- 办理意愿明确时（"我要退货A100003"），先查订单确认可退、随后在同一轮内提交申请，不要停在查单或反问

【Agentic 办结规则——重要】
- execute_service_action 用于在额度内直接办事：退款单笔≤500元、补发、待发货订单改地址
- 提交申请单（submit_return_request）与直接办结（execute_service_action）是两回事：申请单用户表达意愿即可提交，无需反复确认；办结则必须先向用户复述确认（订单+金额+动作），用户明确同意后才执行
- 用户仅表达"能退吗/怎么退"时，先解答政策，不要立刻执行办结
- 办结成功后，把回执信息（含撤销方式）完整转达给用户
- 工具返回"denied/need_human"时，按话术转人工，不要重复尝试
- 用户回复"撤销 ACTxxxx"时，调用 undo_service_action 帮其撤销

工具结果处理（重要）：
- 当工具返回"订单号不存在"或"error"时，【禁止编造】任何订单信息。要诚实告知用户"很抱歉，没有查询到该订单"，并礼貌地请用户核对订单号是否正确，或建议提供下单手机号/收货人姓名以便人工核实，或主动提出转接人工客服。
- 当工具返回真实数据时，基于数据如实回答，不得添加未经查询的信息。
- 当工具返回"越权/不属于当前用户"时，告知用户只能查询本人订单，并转人工核实。

可用工具：
- query_order_status：查订单物流
- query_return_policy：查退货政策（走知识库）
- submit_return_request：提交退货/换货申请
- check_refund_progress：查退款进度
- execute_service_action：额度内直接办结（自动退款/补发/改地址）
- undo_service_action：撤销办结动作（24小时内）
- escalate_to_human：转人工
"""
