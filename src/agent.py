"""
Agent 模块 v2 —— 多轮会话 + 鉴权 + Agentic 办结 + 工单落地
功能：
  1. 多轮对话：携带会话历史（session_store），支持"那退款呢"这类指代
  2. 查询改写：检索前把指代句改写为独立完整问题（多轮 RAG 的必要件）
  3. 订单归属校验：会话模式下，工具只允许操作绑定用户名下的订单（越权=0）
  4. Agentic 办结：execute_service_action 走策略引擎（额度/条件/审计/回执）
  5. 转人工真落地：5 条路径统一创建工单 + AI 生成对话摘要

兼容性：chat(user_input) 不传 session_id 时为单轮模式（评测脚本沿用）。
"""

import re
import json
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from rag_engine import RAGEngine
import db_tools
import session_store
import ticket_service
import policy_engine
from config import (
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, MODEL_NAME,
    SYSTEM_PROMPT, HUMAN_KEYWORDS, SESSION_HISTORY_WINDOW
)

# 撤销指令识别：如 "撤销 ACT20260825123456AB12"
UNDO_PATTERN = re.compile(r"撤销\s*(ACT[A-Za-z0-9]+)")

# 办结确认门：问句（能退吗？）不允许直接办结，必须是明确的办理意愿
QUESTION_PATTERN = re.compile(r"吗|\?|？|能不能|可不可以|是否|能不能退")
INTENT_PATTERN = re.compile(r"确认|确定|帮我|申请|办|退了|我要|就是要|直接")


class CustomerServiceAgent:
    """电商售后客服 Agent v2（能办事、可审计、有兜底）"""

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
        self.tools_schema = self._build_tools_schema()
        self.tool_functions = self._build_tool_functions()
        # 当前会话上下文（chat() 进入时设置；评测单轮模式为 None）
        self._current_session = None
        self._current_history = []
        # SSE 事件回调（server 注入，用于流式推送工具进度）
        self.on_event = None

    def _emit(self, evt: dict):
        if self.on_event:
            try:
                self.on_event(evt)
            except Exception:
                pass

    # ============================================================
    # 工具 Schema（v2：新增 execute_service_action / undo_service_action）
    # ============================================================
    def _build_tools_schema(self):
        base_tools = [
            {
                "type": "function",
                "function": {
                    "name": "query_order_status",
                    "description": "查询用户订单的物流状态。当用户询问订单到哪了、什么时候到货、物流进度、包裹在哪、快递状态时必须调用此工具。必须传入订单号。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "order_id": {"type": "string", "description": "订单编号，格式为字母A开头加6位数字，例如 A100001"}
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
                            "question": {"type": "string", "description": "用户关于退货政策的原始问题"}
                        },
                        "required": ["question"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "submit_return_request",
                    "description": "提交退货或换货申请（仅提交申请单，不直接退款）。当用户明确表示要退货、要换货、要申请售后时调用此工具。",
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
                    "name": "execute_service_action",
                    "description": "【Agentic办结】在策略额度内直接为用户办事：自动退款（单笔≤500元）、补发商品、修改收货地址（仅待发货订单）。必须在用户明确确认办理意愿并核实订单信息后调用。返回办结回执（含可撤销期限）或拒绝原因（denied/need_human）。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {"type": "string", "enum": ["auto_refund", "reship", "change_address"], "description": "办结动作：auto_refund=自动退款 reship=补发 change_address=改地址"},
                            "order_id": {"type": "string", "description": "目标订单编号"},
                            "reason": {"type": "string", "description": "办理理由（将写入审计日志）"},
                            "new_address": {"type": "string", "description": "新收货地址（仅 change_address 需要）"}
                        },
                        "required": ["action", "order_id", "reason"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "undo_service_action",
                    "description": "撤销一个已办结的动作（24小时撤销窗口内）。当用户回复「撤销 ACTxxx」时调用。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action_id": {"type": "string", "description": "办结动作ID，格式 ACT 开头"}
                        },
                        "required": ["action_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "escalate_to_human",
                    "description": "将对话转接给人工客服（自动创建工单并附带对话摘要）。在以下情况调用：金额超过自动办理额度、退款失败、用户明确要求人工、情绪激烈。",
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
        return base_tools

    # ============================================================
    # 工具实现（会话模式下注入归属校验）
    # ============================================================
    def _assert_ownership(self, order_id: str) -> str | None:
        """订单归属校验：会话模式下，非绑定用户的订单一律拒绝。返回错误信息或 None（通过）"""
        if not self._current_session:
            return None  # 评测单轮模式：跳过（评测集显式给订单号）
        import sqlite3
        from config import SQLITE_DB_PATH
        conn = sqlite3.connect(SQLITE_DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM orders WHERE order_id = ?", (order_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None  # 订单不存在交给下游工具正常报错
        if row["user_id"] != self._current_session.get("user_id"):
            return json.dumps({
                "error": "越权：该订单不属于当前会话绑定的用户，已拒绝操作并转人工",
                "need_human": True
            }, ensure_ascii=False)
        return None

    def _build_tool_functions(self):
        agent = self

        def _query_order(order_id: str) -> str:
            denied = agent._assert_ownership(order_id)
            if denied:
                return denied
            result = db_tools.query_order_status(order_id)
            if "error" in result:
                return result["error"]
            return (f"订单{result['order_id']}（{result['item']}，金额¥{result['amount']}）"
                    f"状态：{result['status']}，快递：{result['carrier']}（{result['tracking_no']}），"
                    f"当前位置：{result['current_location']}，预计：{result['eta']}")

        def _query_policy(question: str) -> str:
            # 多轮指代改写：如"那换货呢" → "换货的政策是什么"
            if agent._current_history:
                question = agent._rewrite_query(agent._current_history, question)
            result = agent.rag.answer_with_rag(question)
            return result["answer"]

        def _submit_return(order_id: str, request_type: str, reason: str = "") -> str:
            denied = agent._assert_ownership(order_id)
            if denied:
                return denied
            result = db_tools.submit_return_request(order_id, request_type, reason)
            return json.dumps(result, ensure_ascii=False)

        def _check_refund(order_id: str) -> str:
            denied = agent._assert_ownership(order_id)
            if denied:
                return denied
            result = db_tools.check_refund_progress(order_id)
            return json.dumps(result, ensure_ascii=False)

        def _execute_action(action: str, order_id: str, reason: str, new_address: str = None) -> str:
            # Agentic 办结：策略引擎统一做 校验/执行/审计/回执
            if not agent._current_session:
                return json.dumps({"approved": False, "need_human": True,
                                   "reason": "请先验证订单后再办理"}, ensure_ascii=False)
            # 确认门：用户还在问"能退吗"，不允许直接办结——先答政策、等明确确认
            msg = getattr(agent, "_current_user_input", "") or ""
            if QUESTION_PATTERN.search(msg) and not INTENT_PATTERN.search(msg):
                return json.dumps({"approved": False, "need_confirm": True,
                                   "reason": "用户尚在询问而非确认办理。请先解答政策并复述订单信息（订单号/商品/金额），待用户明确回复确认后再执行办结。"},
                                  ensure_ascii=False)
            result = policy_engine.evaluate_and_execute(
                agent._current_session, action, order_id, reason,
                params={"new_address": new_address} if new_address else {}
            )
            if result.get("approved"):
                agent._last_receipt = result  # 暂存回执，chat() 返回时带给前端
            return json.dumps(result, ensure_ascii=False)

        def _undo_action(action_id: str) -> str:
            if not agent._current_session:
                return json.dumps({"success": False, "error": "请先验证订单"}, ensure_ascii=False)
            result = policy_engine.undo_action(action_id, agent._current_session)
            return json.dumps(result, ensure_ascii=False)

        def _escalate(reason: str) -> str:
            return agent._escalate_with_ticket(reason)["message"]

        return {
            "query_order_status": _query_order,
            "query_return_policy": _query_policy,
            "submit_return_request": _submit_return,
            "check_refund_progress": _check_refund,
            "execute_service_action": _execute_action,
            "undo_service_action": _undo_action,
            "escalate_to_human": _escalate,
        }

    # ============================================================
    # LLM 辅助：查询改写（多轮 RAG 必要件）
    # ============================================================
    def _rewrite_query(self, history: list, latest: str) -> str:
        """把依赖上下文的问句改写为独立完整的问句（检索前执行）"""
        try:
            hist_text = "\n".join(f"{'用户' if m['role'] == 'user' else '客服'}：{m['content'][:80]}"
                                  for m in history[-6:])
            prompt = ChatPromptTemplate.from_messages([
                ("system", """根据对话历史，把用户的最新问题改写为一个独立、完整、无指代的检索查询。
只输出改写后的问题本身，不要任何解释。若最新问题已完整，原样输出。
示例：历史在聊退货，最新消息"那退款呢" → "退款多久到账、退款流程是什么" """),
                ("human", "【对话历史】\n{history}\n\n【最新消息】{latest}")
            ])
            resp = (prompt | self.llm).invoke({"history": hist_text, "latest": latest})
            return resp.content.strip()
        except Exception:
            return latest  # 改写失败降级为原句

    # ============================================================
    # LLM 辅助：转人工前的对话摘要（坐席 10 秒接手）
    # ============================================================
    def _summarize_for_ticket(self, reason: str) -> str:
        history = self._current_history or []
        if not history:
            return f"转人工原因：{reason}（会话刚开始即转人工）"
        try:
            hist_text = "\n".join(f"{'用户' if m['role'] == 'user' else m['role']}：{m['content'][:150]}"
                                  for m in history[-10:])
            prompt = ChatPromptTemplate.from_messages([
                ("system", """用3句话以内为人工坐席总结这段客服对话：用户是谁、要办什么事、AI已做了什么/卡在哪。直接输出摘要。"""),
                ("human", "【转人工原因】{reason}\n\n【对话记录】\n{history}")
            ])
            resp = (prompt | self.llm).invoke({"reason": reason, "history": hist_text})
            return resp.content.strip()
        except Exception:
            return f"转人工原因：{reason}（摘要生成失败，请坐席查看原始对话）"

    # ============================================================
    # 转人工（5 条路径统一走这里：情绪/金额超限/退款失败/越权/超迭代）
    # ============================================================
    def _escalate_with_ticket(self, reason: str, priority: str = "普通") -> dict:
        if self._current_session:
            summary = self._summarize_for_ticket(reason)
            result = ticket_service.create_ticket(
                session_id=self._current_session["session_id"],
                reason=reason, priority=priority, summary=summary
            )
            return result
        # 评测单轮模式：保持 v1 行为
        return db_tools.escalate_to_human(reason, priority)

    # ============================================================
    # 上下文信封：把会话绑定信息注入 system（模型可见但不可篡改服务端校验）
    # ============================================================
    def _context_envelope(self) -> str:
        if not self._current_session:
            return ""
        orders = session_store.get_user_orders(self._current_session["user_id"])
        order_lines = "\n".join(
            f"- {o['order_id']}（{o['item']}，¥{o['amount']}，{o['order_status']}，{'可退' if o['returnable'] else '不可退'}）"
            for o in orders
        )
        return (f"\n\n【当前会话信息（服务端注入）】\n"
                f"已验证用户：{self._current_session['user_id']}\n"
                f"名下订单：\n{order_lines}\n"
                f"注意：优先操作以上名下订单（用户说\"我的订单\"时直接使用，无需反问）；只能查询/操作以上订单，其他订单会被系统拒绝。")

    # ============================================================
    # 主入口
    # ============================================================
    def chat(self, user_input: str, session_id: str = None) -> dict:
        """
        返回：{reply, tool_used, tools_used, escalated, session_id?, ticket_id?, receipt?}
        """
        self._last_receipt = None
        ticket_id = None

        # === 会话加载 ===
        if session_id:
            session = session_store.get_session(session_id)
            if not session or not session.get("verified"):
                return {"reply": "请先通过订单验证（手机号后四位 + 订单号）后再咨询。", "tool_used": "auth", "escalated": False}
            self._current_session = session
            self._current_history = session_store.get_history(session_id)
            self._current_user_input = user_input
            session_store.append_message(session_id, "user", user_input)
        else:
            self._current_session = None
            self._current_history = []
            self._current_user_input = user_input

        # === 快捷路径0：撤销指令（正则优先，不进 LLM）===
        if session_id:
            m = UNDO_PATTERN.search(user_input)
            if m:
                undo_result = policy_engine.undo_action(m.group(1), self._current_session)
                session_store.append_message(session_id, "assistant", undo_result.get("message", str(undo_result)))
                return {"reply": undo_result.get("message", str(undo_result)),
                        "tool_used": "undo_service_action", "escalated": False,
                        "session_id": session_id}

        # === 快捷路径1：情绪/要求人工关键词（优先级最高）===
        if any(kw in user_input for kw in HUMAN_KEYWORDS):
            priority = "紧急" if any(k in user_input for k in ["投诉", "曝光", "报警", "315"]) else "普通"
            result = self._escalate_with_ticket("用户情绪激烈或明确要求人工", priority)
            reply = result["message"]
            if session_id:
                session_store.append_message(session_id, "assistant", reply)
            return {"reply": reply, "tool_used": "escalate_to_human", "escalated": True,
                    "session_id": session_id, "ticket_id": result.get("ticket_id")}

        # === 构建消息：system + 信封 + 历史 + 本轮输入 ===
        messages = [{"role": "system", "content": SYSTEM_PROMPT + self._context_envelope()}]
        for h in self._current_history:
            messages.append({"role": "user" if h["role"] in ("user",) else "assistant",
                             "content": h["content"]})
        messages.append({"role": "user", "content": user_input})

        tools_used = []
        escalated = False
        max_iterations = 5

        try:
            for iteration in range(max_iterations):
                response = self.llm.invoke(messages, tools=self.tools_schema)

                if response.tool_calls:
                    messages.append(response)
                    for tool_call in response.tool_calls:
                        tool_name = tool_call["name"]
                        tool_args = tool_call["args"]
                        tools_used.append({"name": tool_name, "args": tool_args})
                        print(f"  🔧 调用工具: {tool_name}({tool_args})")
                        self._emit({"type": "tool", "name": tool_name, "args": tool_args})

                        if tool_name in self.tool_functions:
                            try:
                                tool_result = self.tool_functions[tool_name](**tool_args)
                            except Exception as e:
                                tool_result = f"工具执行出错：{e}"
                        else:
                            tool_result = f"未知工具：{tool_name}"

                        result_str = str(tool_result)
                        if "need_human" in result_str or "转人工" in result_str or "转接" in result_str:
                            escalated = True
                            # 工具结果要求转人工 → 落工单（带摘要）
                            if self._current_session:
                                tick = self._escalate_with_ticket(f"工具结果触发转人工：{tool_name}")
                                ticket_id = tick.get("ticket_id")

                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "content": result_str
                        })
                    continue

                else:
                    reply = response.content
                    if session_id:
                        session_store.append_message(session_id, "assistant", reply, tools_used=tools_used)
                    return {
                        "reply": reply,
                        "tool_used": tools_used[0]["name"] if tools_used else "none",
                        "tools_used": [t["name"] for t in tools_used],
                        "escalated": escalated,
                        "session_id": session_id,
                        "ticket_id": ticket_id,
                        "receipt": self._last_receipt,
                    }

            # 超过最大迭代
            result = self._escalate_with_ticket("多轮工具调用超限", "紧急")
            if session_id:
                session_store.append_message(session_id, "assistant", result["message"])
            return {"reply": result["message"], "tool_used": "max_iter", "escalated": True,
                    "session_id": session_id, "ticket_id": result.get("ticket_id")}

        except Exception as e:
            import traceback
            return {
                "reply": "抱歉，处理您的问题时出现异常，已为您转接人工客服。",
                "tool_used": "error", "escalated": True,
                "error": str(e), "tb": traceback.format_exc()[-600:]
            }


# ============================================
# 命令行测试（多轮会话模式）
# ============================================
if __name__ == "__main__":
    print("=" * 60)
    print("客服Agent v2 命令行测试（多轮会话模式）")
    print("=" * 60)

    # 模拟：先用 A100002 + 尾号8002 验证
    phone = input("\n📱 手机号后四位（回车默认8002）: ").strip() or "8002"
    order = input("📦 订单号（回车默认A100002）: ").strip() or "A100002"

    v = session_store.verify_and_create_session(phone, order)
    if not v.get("success"):
        print("❌ 验证失败：", v["error"])
        exit()
    session_id = v["session_id"]
    print(f"✅ 验证成功，会话 {session_id}，名下订单：{[o['order_id'] for o in v['orders']]}")

    agent = CustomerServiceAgent()

    while True:
        user_input = input("\n👤 你：").strip()
        if user_input.lower() in ["quit", "exit", "退出"]:
            break
        if not user_input:
            continue
        result = agent.chat(user_input, session_id=session_id)
        print(f"\n🤖 小答：{result['reply']}")
        if result.get("receipt"):
            print(f"   📋 办结回执：{result['receipt'].get('action_id')}（{result['receipt'].get('undo_deadline')} 前可撤销）")
        if result.get("ticket_id"):
            print(f"   🎫 工单：{result['ticket_id']}")


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
