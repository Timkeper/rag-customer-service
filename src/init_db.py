"""
SQLite 数据库初始化脚本
功能：
  1. 创建订单表、退款记录表、退货申请表
  2. 灌入10条Mock订单数据（覆盖运输中/已签收/退货中/退款完成/退款失败/金额超限等场景）
  3. 验证数据写入成功

运行：python init_db.py
面试亮点：你用的是真实关系型数据库，不是JSON文件
"""

import sqlite3
import os
from config import SQLITE_DB_PATH

# 确保data目录存在
os.makedirs(os.path.dirname(SQLITE_DB_PATH), exist_ok=True)


def init_database():
    """创建数据库和所有表"""
    # 连接（如果db文件不存在会自动创建）
    conn = sqlite3.connect(SQLITE_DB_PATH)
    cursor = conn.cursor()

    # === 表1：订单表 ===
    # 面试会问"为什么这么设计字段"——每个字段都有业务含义
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        order_id        TEXT PRIMARY KEY,           -- 订单号（主键）
        user_id         TEXT NOT NULL,              -- 用户ID
        item            TEXT NOT NULL,              -- 商品名
        amount          REAL NOT NULL,              -- 金额（REAL=浮点）
        order_status    TEXT NOT NULL,              -- 订单状态：运输中/已签收/待发货等
        carrier         TEXT,                       -- 快递公司
        tracking_no     TEXT,                       -- 物流单号
        current_location TEXT,                      -- 当前位置
        eta             TEXT,                       -- 预计到达
        returnable      INTEGER DEFAULT 1,          -- 是否可退（0不可/1可）
        special_note    TEXT                        -- 特殊备注（如金额超限）
    )
    """)

    # === 表2：退款记录表（1对1关联订单）===
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS refunds (
        order_id        TEXT PRIMARY KEY,           -- 关联订单号
        refund_status   TEXT NOT NULL,              -- 处理中/已退款/退款失败
        refund_amount   REAL NOT NULL,              -- 退款金额
        refund_method   TEXT,                       -- 退款方式
        eta             TEXT,                       -- 预计到账
        fail_reason     TEXT,                       -- 失败原因（若有）
        FOREIGN KEY (order_id) REFERENCES orders(order_id)
    )
    """)

    # === 表3：退货申请表（1对多，一个订单可能多次申请）===
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS return_requests (
        request_id      TEXT PRIMARY KEY,           -- 申请单号
        order_id        TEXT NOT NULL,              -- 关联订单
        request_type    TEXT NOT NULL,              -- 退货/换货
        reason          TEXT,                       -- 原因
        status          TEXT DEFAULT '已受理',       -- 状态
        created_at      TEXT,                       -- 创建时间
        FOREIGN KEY (order_id) REFERENCES orders(order_id)
    )
    """)

    conn.commit()
    print("✅ 3张表创建成功：orders / refunds / return_requests")
    return conn


def insert_mock_data(conn):
    """灌入10条Mock订单 + 退款记录 + 退货申请"""
    cursor = conn.cursor()

    # 清空旧数据（重复运行也不会报错）
    cursor.execute("DELETE FROM orders")
    cursor.execute("DELETE FROM refunds")
    cursor.execute("DELETE FROM return_requests")

    # === 10条订单数据（覆盖各类测试场景）===
    orders = [
        # (order_id, user_id, item, amount, status, carrier, tracking, location, eta, returnable, note)
        ("A100001", "U8001", "索尼WH-1000XM5 降噪耳机", 1899.00, "运输中", "顺丰速运", "SF1234567890", "成都转运中心", "明天下午18:00前", 1, "金额超500，退货转人工"),
        ("A100002", "U8002", "小米14 手机壳（透明）", 29.90, "已签收", "中通快递", "ZT9876543210", "已送达", "已于2026-07-26送达", 1, None),
        ("A100003", "U8003", "Anker 65W氮化镓充电器", 159.00, "退货处理中", "京东物流", "JD5566778899", "退货商品已揽收", "退款3个工作日到账", 0, None),
        ("A100004", "U8004", "戴森V12 吸尘器", 3990.00, "已签收", "顺丰速运", "SF2233445566", "已送达", "已于2026-07-20送达", 1, "金额超500，退货转人工"),
        ("A100005", "U8005", "罗技MX Master 3S 鼠标", 699.00, "退款已完成", "-", "-", "-", "-", 0, None),
        ("A100006", "U8006", "飞利浦电动牙刷 HX9911", 899.00, "待发货", "待分配", "-", "仓库打包中", "预计2026-07-29发货", 0, None),
        ("A100007", "U8007", "可口可乐 330ml×24罐", 49.90, "退款失败", "-", "-", "-", "-", 0, "退款失败，应转人工"),
        ("A100008", "U8008", "华为Watch GT4 手表", 1488.00, "运输中", "京东物流", "JD1122334455", "武汉转运中心", "后天2026-07-30送达", 1, "金额超500，退货转人工"),
        ("A100009", "U8009", "Lego 21333 梵高《星月夜》", 1499.00, "已签收", "顺丰速运", "SF6677889900", "已送达", "已于2026-07-22送达", 1, "金额超500，退货转人工"),
        ("A100010", "U8010", "三只松鼠坚果礼盒 1.5kg", 89.90, "运输中", "圆通速递", "YT3344556677", "分拨中心", "明天上午12:00前", 1, None),
    ]
    cursor.executemany("""
        INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, orders)

    # === 退款记录（A100003处理中、A100005已完成、A100007失败）===
    refunds = [
        ("A100003", "处理中", 159.00, "原路退回（微信支付）", "预计2026-07-30前到账", None),
        ("A100005", "已退款", 699.00, "原路退回（支付宝）", "2026-07-25已完成", None),
        ("A100007", "退款失败", 49.90, "原路退回", "需人工介入", "原支付账户异常"),
    ]
    cursor.executemany("""
        INSERT INTO refunds VALUES (?,?,?,?,?,?)
    """, refunds)

    # === 退货申请 ===
    requests = [
        ("R20260728001", "A100003", "退货", "质量问题", "已受理", "2026-07-27"),
        ("R20260725002", "A100005", "退货", "不喜欢", "已完成", "2026-07-24"),
    ]
    cursor.executemany("""
        INSERT INTO return_requests VALUES (?,?,?,?,?,?)
    """, requests)

    conn.commit()
    print(f"✅ 数据写入成功：{len(orders)}条订单，{len(refunds)}条退款，{len(requests)}条退货申请")


def verify_data(conn):
    """验证数据，打印出来看一眼"""
    cursor = conn.cursor()

    print("\n📊 数据库验证：")
    print("-" * 60)

    # 订单总数
    cursor.execute("SELECT COUNT(*) FROM orders")
    print(f"订单总数：{cursor.fetchone()[0]}")

    # 各状态分布（面试可以说"我设计了多种状态覆盖测试场景"）
    cursor.execute("SELECT order_status, COUNT(*) FROM orders GROUP BY order_status")
    print("\n订单状态分布：")
    for status, count in cursor.fetchall():
        print(f"  {status}: {count}条")

    # 金额超500的（转人工场景）
    cursor.execute("SELECT order_id, item, amount FROM orders WHERE amount > 500")
    print(f"\n金额超500元（需转人工）的订单：")
    for oid, item, amount in cursor.fetchall():
        print(f"  {oid} - {item} - ¥{amount}")

    print("-" * 60)
    print("✅ 数据库就绪！接下来运行 rag_engine.py 初始化向量库")


if __name__ == "__main__":
    print("=" * 60)
    print("初始化 SQLite 数据库")
    print("=" * 60)

    conn = init_database()
    insert_mock_data(conn)
    verify_data(conn)
    conn.close()

    print(f"\n📍 数据库文件位置：{SQLITE_DB_PATH}")
    print("💡 你可以用 DB Browser for SQLite（免费工具）打开这个db文件看数据")
