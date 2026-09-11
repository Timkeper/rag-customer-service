"""
会话存储模块（v2 新增）
功能：
  1. 买家自助鉴权：手机号后四位 + 订单号 → 创建会话并绑定用户
  2. 多轮消息的读写（会话历史窗口）
  3. 会话生命周期管理

设计要点（面试讲信任边界）：
  - 鉴权发生在服务端：会话只信 session_id，不信客户端传来的任何用户身份
  - 工具层校验订单归属：会话绑定的 user_id 之外的订单一律拒绝（越权动作必须为 0）
"""

import uuid
import sqlite3
from datetime import datetime
from config import SQLITE_DB_PATH, SESSION_HISTORY_WINDOW


def _conn():
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ============================================
# 鉴权：手机号后四位 + 订单号 → 绑定会话
# ============================================
def verify_and_create_session(phone_last4: str, order_id: str) -> dict:
    """
    买家自助验证：订单号存在 且 订单手机号尾号匹配 → 创建已验证会话
    返回：{success, session_id, user_id, orders:[...]} 或 {success: False, error}
    """
    conn = _conn()
    cursor = conn.cursor()

    # 订单号 + 手机尾号双重校验
    cursor.execute(
        "SELECT user_id, phone, item, order_status, amount FROM orders WHERE order_id = ?",
        (order_id,)
    )
    row = cursor.fetchone()

    if not row:
        conn.close()
        return {"success": False, "error": f"订单号 {order_id} 不存在，请核对"}

    if not row["phone"] or not row["phone"].endswith(phone_last4):
        conn.close()
        return {"success": False, "error": "手机号后四位与订单不匹配，请核对（如遗忘可转人工核实）"}

    user_id = row["user_id"]
    session_id = uuid.uuid4().hex[:16]

    cursor.execute("""
        INSERT INTO sessions (session_id, user_id, phone_last4, verified, created_at, last_active_at)
        VALUES (?, ?, ?, 1, ?, ?)
    """, (session_id, user_id, phone_last4, _now(), _now()))
    conn.commit()

    # 返回该用户名下全部订单（同一 user 可能有多单）
    cursor.execute("""
        SELECT order_id, item, amount, order_status FROM orders
        WHERE user_id = ? ORDER BY order_id
    """, (user_id,))
    orders = [dict(r) for r in cursor.fetchall()]
    conn.close()

    return {"success": True, "session_id": session_id, "user_id": user_id, "orders": orders}


def get_session(session_id: str) -> dict:
    """获取会话信息（含验证状态）"""
    conn = _conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


# ============================================
# 消息读写：多轮对话的载体
# ============================================
def append_message(session_id: str, role: str, content: str, tools_used: list = None) -> None:
    """写入一条消息。role: user / assistant / human_agent"""
    import json
    conn = _conn()
    conn.execute("""
        INSERT INTO messages (session_id, role, content, tools_used, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (session_id, role, content, json.dumps(tools_used, ensure_ascii=False) if tools_used else None, _now()))
    conn.commit()
    conn.close()


def get_history(session_id: str, window: int = SESSION_HISTORY_WINDOW) -> list:
    """取最近 N 条消息，按时间正序返回（供拼进 LLM messages）"""
    conn = _conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT role, content FROM messages
        WHERE session_id = ? AND role IN ('user', 'assistant', 'human_agent')
        ORDER BY id DESC LIMIT ?
    """, (session_id, window))
    rows = cursor.fetchall()
    conn.close()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def get_user_orders(user_id: str) -> list:
    """会话绑定用户的名下订单（拼进上下文信封）"""
    conn = _conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT order_id, item, amount, order_status, returnable FROM orders
        WHERE user_id = ? ORDER BY order_id
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ============================================
# 自测
# ============================================
if __name__ == "__main__":
    print("=" * 60)
    print("测试会话存储与鉴权")
    print("=" * 60)

    print("\n1️⃣ 正确验证（A100002 + 尾号8002）:")
    r = verify_and_create_session("8002", "A100002")
    print(r)

    print("\n2️⃣ 错误验证（A100002 + 尾号9999）:")
    print(verify_and_create_session("9999", "A100002"))

    if r.get("success"):
        sid = r["session_id"]
        append_message(sid, "user", "我的快递到哪了")
        append_message(sid, "assistant", "您的订单已签收～", tools_used=["query_order_status"])
        print("\n3️⃣ 多轮历史:")
        print(get_history(sid))

    print("\n✅ 会话模块正常！")
