"""
工单服务模块（v2 新增）
功能：
  1. 转人工 → 真实工单落库（v1 只返回话术，是存根）
  2. AI 自动生成对话摘要（坐席 10 秒接手，不用重读全程）
  3. 坐席操作：接管 / 回复（买家侧无缝切人工）/ 解决

协作设计：摘要由 agent.py 用自己的 LLM 生成后传入（避免模块间共享 LLM 实例）
"""

import sqlite3
import uuid
from datetime import datetime
from config import SQLITE_DB_PATH
import session_store


def _conn():
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def create_ticket(session_id: str, reason: str, priority: str = "普通",
                  summary: str = "", order_id: str = "") -> dict:
    """
    创建工单（5 条转人工路径统一入口）
    返回：{ticket_id, message}
    """
    session = session_store.get_session(session_id) if session_id else None
    user_id = session["user_id"] if session else None
    # 时间戳精确到微秒 + 随机后缀，避免同秒并发撞号
    ticket_id = f"T{datetime.now().strftime('%Y%m%d%H%M%S%f')[:16]}{uuid.uuid4().hex[:3].upper()}"

    conn = _conn()
    conn.execute("""
        INSERT INTO tickets (ticket_id, session_id, user_id, order_id, reason,
                             priority, status, summary, created_at)
        VALUES (?, ?, ?, ?, ?, ?, '待接管', ?, ?)
    """, (ticket_id, session_id, user_id, order_id, reason, priority, summary, _now()))
    conn.commit()
    conn.close()

    return {
        "ticket_id": ticket_id,
        "message": f"已为您转接人工客服（{priority}），工单号 {ticket_id}。坐席将带着完整对话记录接入，无需重复描述问题。"
    }


def list_tickets(status: str = None) -> list:
    """工单列表（坐席工作台用）"""
    conn = _conn()
    cursor = conn.cursor()
    if status:
        cursor.execute("SELECT * FROM tickets WHERE status = ? ORDER BY created_at DESC", (status,))
    else:
        cursor.execute("SELECT * FROM tickets ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def take_ticket(ticket_id: str, agent_name: str) -> dict:
    """坐席接管工单"""
    conn = _conn()
    conn.execute("""
        UPDATE tickets SET status='处理中', assigned_to=? WHERE ticket_id=? AND status='待接管'
    """, (agent_name, ticket_id))
    conn.commit()
    updated = conn.total_changes
    conn.close()
    if updated:
        # 接管后给会话里发一条坐席消息，买家侧无缝切人工
        row = get_ticket(ticket_id)
        if row and row.get("session_id"):
            session_store.append_message(row["session_id"], "human_agent", f"您好，我是人工客服 {agent_name}，已接手您的工单。")
        return {"success": True, "message": f"工单 {ticket_id} 已由 {agent_name} 接管"}
    return {"success": False, "error": "工单不存在或已被接管"}


def get_ticket(ticket_id: str) -> dict:
    conn = _conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def agent_reply(session_id: str, agent_name: str, content: str) -> None:
    """坐席回复（直接写入会话，买家侧立即看到）"""
    session_store.append_message(session_id, "human_agent", f"[{agent_name}] {content}")


def resolve_ticket(ticket_id: str) -> dict:
    """解决工单"""
    conn = _conn()
    conn.execute("UPDATE tickets SET status='已解决', resolved_at=? WHERE ticket_id=?",
                 (_now(), ticket_id))
    conn.commit()
    conn.close()
    return {"success": True}


# ============================================
# 自测
# ============================================
if __name__ == "__main__":
    print("=" * 60)
    print("测试工单服务")
    print("=" * 60)

    print("\n1️⃣ 创建工单:")
    t = create_ticket("test-session-1", "退款失败需人工介入", "紧急",
                      summary="用户U8007订单A100007退款失败（原支付账户异常），已尝试自动处理未果，情绪平稳。")
    print(t)

    print("\n2️⃣ 工单列表:")
    print(list_tickets())

    print("\n3️⃣ 接管（坐席小王）:")
    print(take_ticket(t["ticket_id"], "小王"))

    print("\n4️⃣ 解决:")
    print(resolve_ticket(t["ticket_id"]))

    print("\n✅ 工单服务正常！")
