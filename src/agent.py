"""
Agent 模块（Function Calling 调度）- 原生tool_calls版
功能：
  1. 让大模型自主决策：该查知识库？还是调工具？
  2. 执行工具调用，把结果喂回大模型生成最终回答
  3. 处理转人工逻辑（金额超限/情绪激烈/退款失败）

这是 RAG版 → Agent版 的核心升级。
用原生 tool_calls 循环（不依赖 initialize_agent），工具调用100%可控。
"""

import json
from langchain_openai import ChatOpenAI
from rag_engine import RAGEngine
import db_tools
from config import (
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, MODEL_NAME,
    SYSTEM_PROMPT, HUMAN_KEYWORDS, HUMAN_ESCALATION_AMOUNT
)


class CustomerServiceAgent:
    """电商售后客服Agent"""

    def __init__(self):
        self.llm = ChatOpenAI(
            model=MODEL_NAME,
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
            temperature=0.3,
            max_tokens=1000
        )
        self.rag = RAGEngine()
        self.rag.initialize()
        # 工具定义（OpenAI function calling 格式）
        self.tools_schema = self._build_tools_schema()
        # 工具执行函数映射
        self.tool_functions = self._build_tool_functions()

    def _build_tools_schema(self):
        """构建工具的JSON Schema（告诉大模型有哪些工具可用）"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "query_order_status",
                    "description": "查询用户订单的物流状态。当用户询问订单到哪了、什么时候到货、物流进度、包裹在哪、快递状态时必须调用此工具。必须传入订单号。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "order_id": {
                                "type": "string",
                                "description": "订单编号，格式为字母A开头加6位数字，例如 A100001"
                            }
                        },
                        "required": ["order_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "query_return_policy",
                    "description": "查询电商平台的退货、换货、退款政策。当用户询问能不能退货、退货期限几天、什么情况不能退、退货流程、换货规则、保修政策时必须调用此工具。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "question": {
                                "type": "string",
                                "description": "用户关于退货政策的原始问题"
                            }
                        },
                        "required": ["question"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "submit_return_request",
                    "description": "提交退货或换货申请。当用户明确表示要退货、要换货、要申请售后时必须调用此工具。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "order_id": {"type": "string", "description": "要退货的订单编号"},
                            "request_type": {"type": "string", "enum": ["退货", "换货"], "description": "申请类型"},
                            "reason": {"type": "string", "description": "退货原因"}
                        },
                        "required": ["order_id", "request_type"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "check_refund_progress",
                    "description": "查询退款进度和退款到账情况。当用户询问退款到账了吗、退款多久到、退款进度、钱什么时候退时必须调用此工具。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "order_id": {"type": "string", "description": "订单编号"}
                        },
                        "required": ["order_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "escalate_to_human",
                    "description": "将对话转接给人工客服。在以下情况调用：退货金额超过500元需人工确认、退款失败需人工介入。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "reason": {"type": "string", "description": "转人工原因"}
                        },
                        "required": ["reason"]
                    }
                }
            }
        ]

    def _build_tool_functions(self):
        """工具名 → 执行函数的映射"""
        def _query_order(order_id: str) -> str:
            result = db_tools.query_order_status(order_id)
            if "error" in result:
                return result["error"]
            return (f"订单{result['order_id']}（{result['item']}，金额¥{result['amount']}）"
                    f"状态：{result['status']}，快递：{result['carrier']}（{result['tracking_no']}），"
                    f"当前位置：{result['current_location']}，预计：{result['eta']}")

        def _query_policy(question: str) -> str:
            result = self.rag.answer_with_rag(question)
            return result["answer"]

        def _submit_return(order_id: str, request_type: str, reason: str = "") -> str:
            result = db_tools.submit_return_request(order_id, request_type, reason)
            # 返回完整JSON，让大模型知道是否需要转人工
            return json.dumps(result, ensure_ascii=False)

        def _check_refund(order_id: str) -> str:
            result = db_tools.check_refund_progress(order_id)
            return json.dumps(result, ensure_ascii=False)

        def _escalate(reason: str) -> str:
            result = db_tools.escalate_to_human(reason)
            return result["message"]

        return {
            "query_order_status": _query_order,
            "query_return_policy": _query_policy,
            "submit_return_request": _submit_return,
            "check_refund_progress": _check_refund,
            "escalate_to_human": _escalate,
        }

    def chat(self, user_input: str) -> dict:
        """
        主对话入口 - 原生tool_calls循环
        返回：{reply, tool_used, escalated}
        """
        # === 第0步：情绪检测（优先级最高，直接转人工）===
        if self._detect_negative_emotion(user_input):
            result = db_tools.escalate_to_human("用户情绪激烈", "紧急")
            return {
                "reply": result["message"],
                "tool_used": "escalate_to_human",
                "escalated": True
            }

        # === 构建消息 ===
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_input}
        ]

        tools_used = []
        escalated = False
        max_iterations = 5  # 防止死循环

        try:
            for iteration in range(max_iterations):
                # 第1步：问大模型"要不要调工具"
                response = self.llm.invoke(messages, tools=self.tools_schema)

                # 第2步：如果模型决定调工具
                if response.tool_calls:
                    messages.append(response)  # 把模型的tool_call决定加入对话

                    for tool_call in response.tool_calls:
                        tool_name = tool_call["name"]
                        tool_args = tool_call["args"]
                        tools_used.append({"name": tool_name, "args": tool_args})

                        print(f"  🔧 调用工具: {tool_name}({tool_args})")

                        # 执行工具
                        if tool_name in self.tool_functions:
                            try:
                                tool_result = self.tool_functions[tool_name](**tool_args)
                            except Exception as e:
                                tool_result = f"工具执行出错：{e}"
                        else:
                            tool_result = f"未知工具：{tool_name}"

                        # 检查工具结果是否触发转人工
                        if "need_human" in str(tool_result) or "转人工" in str(tool_result) or "转接" in str(tool_result):
                            escalated = True

                        # 把工具结果喂回大模型
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "content": str(tool_result)
                        })

                    # 继续循环，让大模型基于工具结果生成回答（或继续调更多工具）
                    continue

                else:
                    # 模型不再调工具，直接返回最终回答
                    return {
                        "reply": response.content,
                        "tool_used": tools_used[0]["name"] if tools_used else "none",
                        "tools_used": [t["name"] for t in tools_used],
                        "escalated": escalated
                    }

            # 超过最大迭代次数
            return {
                "reply": "抱歉，处理您的问题时遇到异常，已为您转接人工客服。",
                "tool_used": "max_iter",
                "escalated": True
            }

        except Exception as e:
            return {
                "reply": f"抱歉，处理您的问题时出现异常，已为您转接人工客服。",
                "tool_used": "error",
                "escalated": True,
                "error": str(e)
            }

    def _detect_negative_emotion(self, text: str) -> bool:
        """情绪检测：是否包含愤怒/投诉关键词"""
        return any(kw in text for kw in HUMAN_KEYWORDS)


# ============================================
# 命令行测试
# ============================================
if __name__ == "__main__":
    print("=" * 60)
    print("客服Agent 命令行测试（输入quit退出）")
    print("=" * 60)

    agent = CustomerServiceAgent()

    while True:
        user_input = input("\n👤 你：").strip()
        if user_input.lower() in ["quit", "exit", "退出"]:
            break
        if not user_input:
            continue

        result = agent.chat(user_input)
        print(f"\n🤖 小答：{result['reply']}")
        if result.get("escalated"):
            print("   （已触发转人工）")


# ============================================
# 三种模式的统一接口（供评测脚本调用）
# ============================================
class BaselineChat:
    """裸模型版（不加RAG不加Agent，用于对比基线）"""
    def __init__(self):
        self.llm = ChatOpenAI(
            model=MODEL_NAME, api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL, temperature=0.3
        )

    def chat(self, user_input: str) -> dict:
        from langchain.prompts import ChatPromptTemplate
        prompt = ChatPromptTemplate.from_messages([
            ("system", "你是一名电商售后客服。回答用户问题。"),
            ("human", "{input}")
        ])
        reply = (prompt | self.llm).invoke({"input": user_input})
        return {"reply": reply.content, "tool_used": "none", "escalated": False}


class RAGChat:
    """纯RAG版（只查知识库，不调工具）"""
    def __init__(self):
        self.rag = RAGEngine()
        self.rag.initialize()

    def chat(self, user_input: str) -> dict:
        result = self.rag.answer_with_rag(user_input)
        return {"reply": result["answer"], "tool_used": "rag", "escalated": False}
