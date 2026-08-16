"""
数据库工具模块
功能：封装对SQLite的查询操作，供Agent的5个工具调用
每个函数对应一个Agent工具的实际执行逻辑

面试亮点：这5个函数就是Function Calling的"工具实现"，
面试官问"你的工具怎么工作的"，指的就是这里
"""

import sqlite3
from datetime import datetime
from config import SQLITE_DB_PATH, HUMAN_ESCALATION_AMOUNT


def get_connection():
    """获取数据库连接（每个操作独立连接，避免并发问题）"""
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row  # 让查询结果可以用列名访问
    return conn


# ============================================
# 工具1：查询订单物流状态
# 对应Agent工具：query_order_status
# ============================================
def query_order_status(order_id: str) -> dict:
    """
    查询订单的物流信息
    返回：{status, item, carrier, location, eta} 或 {error}
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT order_id, item, amount, order_status, carrier,
               tracking_no, current_location, eta
        FROM orders WHERE order_id = ?
    """, (order_id,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return {"error": f"订单号 {order_id} 不存在，请核实订单号是否正确"}

    return {
        "order_id": row["order_id"],
        "item": row["item"],
        "amount": row["amount"],
        "status": row["order_status"],
        "carrier": row["carrier"],
        "tracking_no": row["tracking_no"],
        "current_location": row["current_location"],
        "eta": row["eta"]
    }


# ============================================
# 工具3：提交退货/换货申请
# 对应Agent工具：submit_return_request
# ============================================
def submit_return_request(order_id: str, request_type: str, reason: str = "") -> dict:
    """
    提交退货或换货申请
    重要业务规则：金额超过500元必须转人工，不能直接提交
    """
    conn = get_connection()
    cursor = conn.cursor()

    # 先查订单是否存在 + 金额
    cursor.execute("SELECT item, amount, returnable FROM orders WHERE order_id = ?", (order_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return {"error": f"订单号 {order_id} 不存在"}

    # ⚠️ 关键业务规则：金额超限必须转人工
    if row["amount"] > HUMAN_ESCALATION_AMOUNT:
        conn.close()
        return {
            "need_human": True,
            "reason": f"订单{order_id}（{row['item']}）金额¥{row['amount']}超过¥{HUMAN_ESCALATION_AMOUNT}，需转人工确认后才能办理",
            "message": f"⚠️ 您的订单金额超过¥{HUMAN_ESCALATION_AMOUNT}，为保障您的权益，需要人工客服确认后才能办理{request_type}。已为您转接人工。"
        }

    # 检查是否可退
    if not row["returnable"]:
        conn.close()
        return {"error": f"订单{order_id}当前状态不支持{request_type}（可能已退货或已退款）"}

    # 生成申请单号
    request_id = f"R{datetime.now().strftime('%Y%m%d%H%M%S')}"

    # 写入数据库
    cursor.execute("""
        INSERT INTO return_requests (request_id, order_id, request_type, reason, status, created_at)
        VALUES (?, ?, ?, ?, '已受理', ?)
    """, (request_id, order_id, request_type, reason, datetime.now().strftime("%Y-%m-%d")))

    conn.commit()
    conn.close()

    return {
        "success": True,
        "request_id": request_id,
        "order_id": order_id,
        "type": request_type,
        "message": f"已受理您的{request_type}申请。申请单号：{request_id}，订单：{order_id}（{row['item']}）。我们将在1-3个工作日内处理。"
    }


# ============================================
# 工具4：查询退款进度
# 对应Agent工具：check_refund_progress
# ============================================
def check_refund_progress(order_id: str) -> dict:
    """
    查询退款状态
    特殊处理：退款失败时返回need_human标记
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT r.refund_status, r.refund_amount, r.refund_method, r.eta, r.fail_reason,
               o.item
        FROM refunds r
        JOIN orders o ON r.order_id = o.order_id
        WHERE r.order_id = ?
    """, (order_id,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return {"error": f"订单 {order_id} 暂无退款记录"}

    result = {
        "order_id": order_id,
        "item": row["item"],
        "refund_status": row["refund_status"],
        "amount": row["refund_amount"],
        "method": row["refund_method"],
        "eta": row["eta"]
    }

    # ⚠️ 退款失败 → 触发转人工
    if row["refund_status"] == "退款失败":
        result["need_human"] = True
        result["message"] = f"⚠️ 订单{order_id}的退款失败，原因：{row['fail_reason']}。已为您转接人工客服处理。"

    return result


# ============================================
# 工具5：转人工
# 对应Agent工具：escalate_to_human
# ============================================
def escalate_to_human(reason: str, priority: str = "普通") -> dict:
    """
    记录转人工请求（实际系统会接入工单系统）
    """
    return {
        "escalated": True,
        "reason": reason,
        "priority": priority,
        "message": f"已为您转接人工客服（{priority}），预计等待时长1-3分钟。紧急工单将优先处理。"
    }


# ============================================
# 扩展功能：模拟下单（形成「下单→查询→退货」闭环）
# 说明：真实系统下单走交易中心API，这里用SQLite模拟，便于Demo演示
# ============================================
def create_order(item: str, amount: float) -> dict:
    """
    模拟下单：输入商品名+金额，生成一个新订单
    真实系统对应交易中心的 createOrder API
    返回新生成的订单号，之后即可查询/退货该订单
    """
    conn = get_connection()
    cursor = conn.cursor()

    # 生成订单号：A + 当前时间戳后6位（保证唯一）
    order_id = f"A{datetime.now().strftime('%H%M%S')}"

    cursor.execute("""
        INSERT INTO orders (order_id, user_id, item, amount, order_status,
                           carrier, tracking_no, current_location, eta, returnable)
        VALUES (?, ?, ?, ?, '待发货', '待分配', '-', '仓库打包中', '预计3个工作日内发货', 1)
    """, (order_id, "U9999", item, amount))

    conn.commit()
    conn.close()

    return {
        "success": True,
        "order_id": order_id,
        "item": item,
        "amount": amount,
        "status": "待发货",
        "message": f"下单成功！订单号：{order_id}（{item}，¥{amount}）。状态：待发货，预计3个工作日内发货。您现在可以用这个订单号查询物流或办理退货。"
    }


# ============================================
# 测试：直接运行这个文件可以验证工具是否正常
# ============================================
if __name__ == "__main__":
    print("=" * 60)
    print("测试数据库工具")
    print("=" * 60)

    print("\n1️⃣ 查订单 A100001（运输中）:")
    print(query_order_status("A100001"))

    print("\n2️⃣ 查订单 A100999（不存在）:")
    print(query_order_status("A100999"))

    print("\n3️⃣ 退货 A100002（金额29.9，可退）:")
    print(submit_return_request("A100002", "退货", "不喜欢"))

    print("\n4️⃣ 退货 A100004（金额3990，超限应转人工）:")
    print(submit_return_request("A100004", "退货", "尺寸不合"))

    print("\n5️⃣ 查退款 A100003（处理中）:")
    print(check_refund_progress("A100003"))

    print("\n6️⃣ 查退款 A100007（失败，应转人工）:")
    print(check_refund_progress("A100007"))

    print("\n✅ 工具测试完成！")
