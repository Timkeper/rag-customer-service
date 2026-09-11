# -*- coding: utf-8 -*-
"""Day1 端到端测试：鉴权 → 多轮 → 指代改写 → Agentic 办结 → 撤销 → 工单"""
import init_db
init_db.init_database()
init_db.insert_mock_data.__wrapped__ if hasattr(init_db.insert_mock_data, '__wrapped__') else None

import sqlite3
from config import SQLITE_DB_PATH
conn = sqlite3.connect(SQLITE_DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

import session_store, policy_engine, ticket_service
from agent import CustomerServiceAgent

print("=" * 60)
print("端到端测试：多轮会话 + Agentic 办结")
print("=" * 60)

# 1. 鉴权
v = session_store.verify_and_create_session("8002", "A100002")
assert v["success"], v
sid = v["session_id"]
print(f"\n[1] 鉴权通过：会话 {sid}，用户 {v['user_id']}")

agent = CustomerServiceAgent()

# 2. 第一轮：查物流
r1 = agent.chat("我的快递到哪了？", session_id=sid)
print(f"\n[2] 用户：我的快递到哪了？\n    小答：{r1['reply'][:120]}...")

# 3. 第二轮：指代追问（测试查询改写 + 多轮记忆）
r2 = agent.chat("那这个东西能退货吗？", session_id=sid)
print(f"\n[3] 用户：那这个东西能退货吗？（指代'这个东西'）\n    小答：{r2['reply'][:120]}...")

# 4. 第三轮：明确要求退款（Agentic 办结，¥29.9 ≤ 500 应自动办结）
r3 = agent.chat("我确定要退货退款，商品没用过，麻烦帮我办理", session_id=sid)
print(f"\n[4] 用户：我确定要退货退款...\n    小答：{r3['reply'][:150]}...")
print(f"    工具链：{r3.get('tools_used')}")
if r3.get("receipt"):
    print(f"    📋 回执：{r3['receipt']['action_id']}（{r3['receipt']['undo_deadline']} 前可撤销）")

# 5. 审计日志验证
cur.execute("SELECT decision, action, amount, policy_reason FROM audit_log ORDER BY audit_id DESC LIMIT 3")
print("\n[5] 审计日志（最近3条）：")
for row in cur.fetchall():
    print(f"    {row['decision']} | {row['action']} ¥{row['amount']} | {row['policy_reason']}")

# 6. 撤销测试（如果办结成功）
if r3.get("receipt"):
    aid = r3["receipt"]["action_id"]
    r4 = agent.chat(f"撤销 {aid}", session_id=sid)
    print(f"\n[6] 用户：撤销 {aid}\n    小答：{r4['reply'][:100]}")
    cur.execute("SELECT order_status, returnable FROM orders WHERE order_id='A100002'")
    row = cur.fetchone()
    print(f"    订单回滚后状态：{row['order_status']}，returnable={row['returnable']}")

# 7. 越权测试：会话内查询他人订单
r5 = agent.chat("帮我查一下订单 A100004 的物流", session_id=sid)
print(f"\n[7] 用户：帮我查一下订单 A100004 的物流（别人的订单）\n    小答：{r5['reply'][:120]}...")
print(f"    escalated={r5.get('escalated')}，ticket={r5.get('ticket_id')}")

# 8. 工单列表
print("\n[8] 工单列表：")
for t in ticket_service.list_tickets()[:3]:
    print(f"    {t['ticket_id']} [{t['status']}] {t['reason'][:30]} | 摘要：{(t['summary'] or '')[:50]}")

conn.close()
print("\n✅ 端到端测试完成！")
