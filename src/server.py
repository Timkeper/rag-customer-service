# -*- coding: utf-8 -*-
"""
智答 v2 服务端（FastAPI + SSE）
功能：
  - 买家端：订单验证 / 多轮对话（SSE 流式推送工具进度与最终回复）
  - 坐席台：登录 / 工单列表与接管 / 查看对话 / 回复 / 解决
  - 洞察页：审计日志 / 运营统计 / LLM 生成商家改进周报

运行：python server.py  →  http://127.0.0.1:8000
"""

import sys
# 编码保险丝：容器环境 stdout 可能为 ASCII，中文/emoji print 会炸（UnicodeEncodeError）
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

# 终极保险：全局替换 print，编码错误降级为替换字符，绝不抛异常
import builtins
_orig_print = builtins.print
def _safe_print(*args, **kwargs):
    try:
        _orig_print(*args, **kwargs)
    except UnicodeEncodeError:
        try:
            _orig_print(*(str(a).encode("ascii", "replace").decode("ascii") for a in args), **kwargs)
        except Exception:
            pass
builtins.print = _safe_print

import json
import hashlib
import threading
import queue
from datetime import datetime

from fastapi import FastAPI, Request, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse, JSONResponse

import session_store
import ticket_service
import policy_engine
from config import AGENT_CONSOLE_PASSWORD, SQLITE_DB_PATH

app = FastAPI(title="智答 · 电商售后 Agent v2")

# ---------- Agent 单例（RAG 初始化一次；演示规模用锁串行化对话） ----------
_agent = None
_chat_lock = threading.Lock()


def get_agent():
    global _agent
    if _agent is None:
        from agent import CustomerServiceAgent
        _agent = CustomerServiceAgent()
    return _agent


@app.on_event("startup")
async def startup():
    """首次启动自动初始化数据库（幂等）；Agent 懒加载——页面立即可用，密钥缺失时对话返回明确提示"""
    import init_db
    conn = init_db.init_database()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM orders")
    if cur.fetchone()[0] == 0:
        init_db.insert_mock_data(conn)
        print("📦 首次启动：已灌入演示订单数据")
    conn.close()


BUILD_TAG = "20260912-a"  # 部署版本标记（排查线上跑的是哪版代码）


@app.get("/api/health")
async def health():
    """健康检查：数据库/页面立即可用；Agent 状态单独报告"""
    import traceback
    try:
        get_agent()
        agent_status = "ready"
    except Exception as e:
        agent_status = "not_ready：" + repr(e)[:150] + " || TB: " + traceback.format_exc()[-350:].replace("\n", " | ")
    return {"status": "ok", "build": BUILD_TAG, "agent": agent_status.split("：")[0], "detail": agent_status}


def _db():
    import sqlite3
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ---------- 坐席台鉴权（演示级：固定 token） ----------
def console_token() -> str:
    return hashlib.sha256(AGENT_CONSOLE_PASSWORD.encode()).hexdigest()[:16]


def check_console(x_token: str) -> bool:
    return x_token == console_token()


# ============================================================
# 买家端
# ============================================================
@app.post("/api/verify")
async def verify(req: Request):
    """买家自助验证：手机号后四位 + 订单号 → 创建会话"""
    data = await req.json()
    return session_store.verify_and_create_session(
        str(data.get("phone_last4", "")).strip(),
        str(data.get("order_id", "")).strip()
    )


@app.get("/api/orders/{session_id}")
async def orders(session_id: str):
    s = session_store.get_session(session_id)
    if not s:
        return JSONResponse({"error": "会话不存在"}, status_code=404)
    return {"orders": session_store.get_user_orders(s["user_id"])}


@app.get("/api/messages/{session_id}")
async def messages(session_id: str):
    """会话完整消息（坐席台 + 买家断线重连用）"""
    return {"messages": session_store.get_history(session_id, window=200)}


@app.post("/api/chat")
async def chat(req: Request):
    """多轮对话（SSE）：推送工具进度事件 + 最终结果"""
    data = await req.json()
    session_id = data.get("session_id", "")
    message = str(data.get("message", "")).strip()
    if not message:
        return JSONResponse({"error": "消息为空"}, status_code=400)
    if not session_store.get_session(session_id):
        return JSONResponse({"error": "会话不存在，请先验证订单"}, status_code=404)

    q: queue.Queue = queue.Queue()

    def worker():
        try:
            agent = get_agent()
        except Exception as e:
            q.put({"type": "final", "data": {
                "reply": "抱歉，AI 服务暂未就绪（密钥未配置）。请在云托管控制台为服务配置环境变量 DEEPSEEK_API_KEY 与 ZHIPU_API_KEY 后重试。",
                "tool_used": "error", "escalated": False, "error": str(e)[:200]}})
            q.put(None)
            return
        with _chat_lock:
            agent.on_event = lambda evt: q.put(evt)
            try:
                result = agent.chat(message, session_id=session_id)
                q.put({"type": "final", "data": result})
            except Exception as e:
                import traceback
                q.put({"type": "final", "data": {"reply": f"服务异常：{e}", "tool_used": "error", "escalated": True,
                                                 "tb": traceback.format_exc()[-500:]}})
            finally:
                agent.on_event = None
                q.put(None)

    threading.Thread(target=worker, daemon=True).start()

    def gen():
        yield f"data: {json.dumps({'type': 'start'}, ensure_ascii=False)}\n\n"
        while True:
            try:
                evt = q.get(timeout=180)
            except queue.Empty:
                yield f"data: {json.dumps({'type': 'timeout'}, ensure_ascii=False)}\n\n"
                return
            if evt is None:
                return
            yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ============================================================
# 坐席台
# ============================================================
@app.post("/api/console/login")
async def console_login(req: Request):
    data = await req.json()
    if data.get("password") != AGENT_CONSOLE_PASSWORD:
        return JSONResponse({"error": "密码错误"}, status_code=401)
    return {"token": console_token(), "agent_name": data.get("agent_name", "坐席")}


@app.get("/api/tickets")
async def list_tickets(status: str = None, x_token: str = Header(None)):
    if not check_console(x_token):
        return JSONResponse({"error": "未授权"}, status_code=401)
    return {"tickets": ticket_service.list_tickets(status)}


@app.post("/api/tickets/take")
async def take_ticket(req: Request, x_token: str = Header(None)):
    if not check_console(x_token):
        return JSONResponse({"error": "未授权"}, status_code=401)
    data = await req.json()
    return ticket_service.take_ticket(data["ticket_id"], data.get("agent_name", "坐席"))


@app.post("/api/tickets/reply")
async def ticket_reply(req: Request, x_token: str = Header(None)):
    if not check_console(x_token):
        return JSONResponse({"error": "未授权"}, status_code=401)
    data = await req.json()
    t = ticket_service.get_ticket(data["ticket_id"])
    if not t or not t.get("session_id"):
        return JSONResponse({"error": "工单不存在"}, status_code=404)
    ticket_service.agent_reply(t["session_id"], data.get("agent_name", "坐席"), data["content"])
    return {"success": True}


@app.post("/api/tickets/resolve")
async def resolve_ticket(req: Request, x_token: str = Header(None)):
    if not check_console(x_token):
        return JSONResponse({"error": "未授权"}, status_code=401)
    data = await req.json()
    return ticket_service.resolve_ticket(data["ticket_id"])


# ============================================================
# 洞察页：审计 + 统计 + LLM 周报
# ============================================================
@app.get("/api/audit")
async def audit(x_token: str = Header(None)):
    if not check_console(x_token):
        return JSONResponse({"error": "未授权"}, status_code=401)
    return {"audit": policy_engine.list_audit(100)}


@app.get("/api/insights")
async def insights(x_token: str = Header(None)):
    if not check_console(x_token):
        return JSONResponse({"error": "未授权"}, status_code=401)
    conn = _db()
    cur = conn.cursor()

    stats = {}
    cur.execute("SELECT COUNT(*) FROM sessions"); stats["sessions"] = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM messages"); stats["messages"] = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM tickets"); stats["tickets"] = cur.fetchone()[0]
    cur.execute("""SELECT decision, COUNT(*) c, COALESCE(SUM(amount),0) amt FROM audit_log GROUP BY decision""")
    stats["agentic"] = {r["decision"]: {"count": r["c"], "amount": r["amt"]} for r in cur.fetchall()}

    # 工具调用分布（从 messages.tools_used 聚合）
    cur.execute("SELECT tools_used FROM messages WHERE tools_used IS NOT NULL")
    from collections import Counter
    counter = Counter()
    for (tj,) in cur.fetchall():
        try:
            for t in json.loads(tj):
                counter[t["name"]] += 1
        except Exception:
            pass
    stats["tool_usage"] = dict(counter.most_common(10))

    # 用户问题主题分布（简单关键词分桶，周报的输入）
    cur.execute("SELECT content FROM messages WHERE role='user' ORDER BY id DESC LIMIT 200")
    buckets = Counter()
    keywords = {"退货": "退货", "退款": "退款", "换货": "换货", "物流": "物流/快递", "快递": "物流/快递",
                "到哪": "物流/快递", "地址": "地址", "人工": "要求人工", "投诉": "情绪/投诉", "保修": "保修",
                "政策": "政策咨询", "多久": "时效咨询"}
    for (c,) in cur.fetchall():
        hit = False
        for k, v in keywords.items():
            if k in c:
                buckets[v] += 1
                hit = True
                break
        if not hit:
            buckets["其他"] += 1
    stats["topics"] = dict(buckets.most_common())
    conn.close()
    return {"stats": stats, "generated_at": _now()}


@app.get("/api/insights/report")
async def insights_report(x_token: str = Header(None)):
    """LLM 生成商家改进周报（客服即洞察）"""
    if not check_console(x_token):
        return JSONResponse({"error": "未授权"}, status_code=401)

    conn = _db()
    cur = conn.cursor()
    cur.execute("""
        SELECT role, content FROM messages WHERE role='user'
        ORDER BY id DESC LIMIT 100
    """)
    user_msgs = [r["content"] for r in cur.fetchall()]
    cur.execute("SELECT reason, COUNT(*) c FROM tickets GROUP BY reason ORDER BY c DESC LIMIT 8")
    ticket_reasons = [f"{r['reason']}（{r['c']}次）" for r in cur.fetchall()]
    conn.close()

    from langchain_openai import ChatOpenAI
    from langchain.prompts import ChatPromptTemplate
    from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, MODEL_NAME

    llm = ChatOpenAI(model=MODEL_NAME, api_key=DEEPSEEK_API_KEY,
                     base_url=DEEPSEEK_BASE_URL, temperature=0.3)
    prompt = ChatPromptTemplate.from_messages([
        ("system", """你是一名电商运营分析师。基于客服对话记录和工单统计，输出一份给商家的改进周报（Markdown），结构：
## 一、本周客服概览（用数据说话）
## 二、用户咨询 Top 主题与根因分析（重点：哪些问题可以归因到商品详情页/流程设计的缺陷）
## 三、建议动作（按优先级，可执行）
要求：具体、可执行，直接关联到对话中的真实证据。不超过 500 字。"""),
        ("human", "【工单统计】\n{tickets}\n\n【近期用户消息样本】\n{msgs}")
    ])
    resp = (prompt | llm).invoke({
        "tickets": "\n".join(ticket_reasons) or "暂无工单",
        "msgs": "\n".join(f"- {m[:60]}" for m in user_msgs[:50]) or "暂无对话"
    })
    return {"report": resp.content, "generated_at": _now()}


# ============================================================
# 静态页面
# ============================================================
app.mount("/", StaticFiles(directory="static", html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    print("=" * 60)
    print("智答 v2 启动中...")
    print("买家端:   http://127.0.0.1:8000/")
    print("坐席台:   http://127.0.0.1:8000/console.html")
    print("洞察页:   http://127.0.0.1:8000/insights.html")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8000)
