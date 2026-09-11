"""
SQLite 数据库初始化脚本 v2
功能：
  1. 订单表新增 phone/address 字段（买家自助鉴权用）
  2. 新增 4 张 v2 表：sessions（会话）/ messages（多轮消息）/ tickets（工单）/ audit_log（审计日志）
  3. 灌入 10 条 Mock 订单（覆盖运输中/已签收/退货中/退款完成/退款失败/金额超限等场景）

运行：python init_db.py
v2 变化（面试讲"从 demo 到可落地做了什么"）：
  - 鉴权：订单绑定手机号后四位，会话与用户绑定，堵住"输订单号查任何单"漏洞
  - 工单：转人工 5 条路径全部落库，坐席可接管
  - 审计：AI 的每个资金动作（退款/补发）都有不可抵赖的日志
"""

import sqlite3
import os
from config import SQLITE_DB_PATH

# 确保data目录存在
os.makedirs(os.path.dirname(SQLITE_DB_PATH), exist_ok=True)


def init_database():
    """创建数据库和所有表（v1 三张 + v2 四张）"""
    conn = sqlite3.connect(SQLITE_DB_PATH)
    cursor = conn.cursor()

    # === 表1：订单表（v2：新增 phone / address）===
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        order_id        TEXT PRIMARY KEY,
        user_id         TEXT NOT NULL,
        item            TEXT NOT NULL,
        amount          REAL NOT NULL,
        order_status    TEXT NOT NULL,
        carrier         TEXT,
        tracking_no     TEXT,
        current_location TEXT,
        eta             TEXT,
        returnable      INTEGER DEFAULT 1,
        special_note    TEXT,
        phone           TEXT,
        address         TEXT
    )
    """)

    # === 表2：退款记录表 ===
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS refunds (
        order_id        TEXT PRIMARY KEY,
        refund_status   TEXT NOT NULL,
        refund_amount   REAL NOT NULL,
        refund_method   TEXT,
        eta             TEXT,
        fail_reason     TEXT,
        FOREIGN KEY (order_id) REFERENCES orders(order_id)
    )
    """)

    # === 表3：退货申请表 ===
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS return_requests (
        request_id      TEXT PRIMARY KEY,
        order_id        TEXT NOT NULL,
        request_type    TEXT NOT NULL,
        reason          TEXT,
        status          TEXT DEFAULT '已受理',
        created_at      TEXT,
        FOREIGN KEY (order_id) REFERENCES orders(order_id)
    )
    """)

    # === 表4：会话表（v2 新增）——多轮对话 + 鉴权绑定的载体 ===
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        session_id      TEXT PRIMARY KEY,           -- 会话ID（uuid）
        user_id         TEXT,                       -- 验证通过后绑定的用户ID
        phone_last4     TEXT,                       -- 验证用的手机号后四位
        verified        INTEGER DEFAULT 0,          -- 是否已通过订单验证
        created_at      TEXT,
        last_active_at  TEXT
    )
    """)

    # === 表5：消息表（v2 新增）——多轮历史 + 人机双方消息 ===
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id      TEXT NOT NULL,
        role            TEXT NOT NULL,              -- user / assistant / human_agent
        content         TEXT NOT NULL,
        tools_used      TEXT,                       -- 本轮 AI 调用的工具（JSON，可空）
        created_at      TEXT
    )
    """)

    # === 表6：工单表（v2 新增）——转人工真落地 ===
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tickets (
        ticket_id       TEXT PRIMARY KEY,           -- 工单号 T+时间戳
        session_id      TEXT,
        user_id         TEXT,
        order_id        TEXT,
        reason          TEXT,                       -- 转人工原因
        priority        TEXT DEFAULT '普通',        -- 普通/紧急
        status          TEXT DEFAULT '待接管',      -- 待接管/处理中/已解决
        summary         TEXT,                       -- AI 生成的对话摘要（坐席快速接手）
        assigned_to     TEXT,                       -- 接管坐席
        created_at      TEXT,
        resolved_at     TEXT
    )
    """)

    # === 表7：审计日志表（v2 新增）——Agentic 办结的信任基础 ===
    # 记录：谁、什么条件、执行了什么动作、动了多少钱、AI 的理由
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_log (
        audit_id        INTEGER PRIMARY KEY AUTOINCREMENT,
        ts              TEXT,
        session_id      TEXT,
        user_id         TEXT,
        order_id        TEXT,
        action          TEXT,                       -- auto_refund / reship / change_address
        amount          REAL,
        decision        TEXT,                       -- approved / denied / undone
        policy_reason   TEXT,                       -- 命中或违反的策略说明
        ai_reason       TEXT,                       -- AI 给出的办理理由
        action_id       TEXT,                       -- 办结动作ID（用于撤销）
        undo_deadline   TEXT,                       -- 可撤销截止时间
        undone          INTEGER DEFAULT 0,          -- 是否已撤销
        detail          TEXT                        -- JSON 详情
    )
    """)

    conn.commit()

    # === v1 → v2 迁移：给已存在的旧 orders 表补 phone / address 列 ===
    cols = [r[1] for r in cursor.execute("PRAGMA table_info(orders)").fetchall()]
    if "phone" not in cols:
        cursor.execute("ALTER TABLE orders ADD COLUMN phone TEXT")
        print("🔀 迁移：orders 表新增 phone 列")
    if "address" not in cols:
        cursor.execute("ALTER TABLE orders ADD COLUMN address TEXT")
        print("🔀 迁移：orders 表新增 address 列")
    conn.commit()

    print("✅ 7张表就绪：orders / refunds / return_requests / sessions / messages / tickets / audit_log")
    return conn


def insert_mock_data(conn):
    """灌入 10 条 Mock 订单（v2：带手机号与地址）+ 退款 + 退货申请"""
    cursor = conn.cursor()

    # 清空旧数据（重复运行也不会报错）
    for table in ["orders", "refunds", "return_requests", "sessions", "messages", "tickets", "audit_log"]:
        cursor.execute(f"DELETE FROM {table}")

    # === 10 条订单（手机号尾号与 user_id 对应，便于演示鉴权）===
    orders = [
        # (order_id, user_id, item, amount, status, carrier, tracking, location, eta, returnable, note, phone, address)
        ("A100001", "U8001", "索尼WH-1000XM5 降噪耳机", 1899.00, "运输中", "顺丰速运", "SF1234567890", "成都转运中心", "明天下午18:00前", 1, "金额超500，退货转人工", "13812348001", "重庆市南岸区崇文路2号"),
        ("A100002", "U8002", "小米14 手机壳（透明）", 29.90, "已签收", "中通快递", "ZT9876543210", "已送达", "已于2026-07-26送达", 1, None, "13923458002", "重庆市渝北区金龙路26号"),
        ("A100003", "U8003", "Anker 65W氮化镓充电器", 159.00, "退货处理中", "京东物流", "JD5566778899", "退货商品已揽收", "退款3个工作日到账", 0, None, "13734568003", "成都市武侯区天府大道99号"),
        ("A100004", "U8004", "戴森V12 吸尘器", 3990.00, "已签收", "顺丰速运", "SF2233445566", "已送达", "已于2026-07-20送达", 1, "金额超500，退货转人工", "13645678004", "上海市徐汇区漕溪北路88号"),
        ("A100005", "U8005", "罗技MX Master 3S 鼠标", 699.00, "退款已完成", "-", "-", "-", "-", 0, None, "13556788005", "北京市海淀区中关村大街1号"),
        ("A100006", "U8006", "飞利浦电动牙刷 HX9911", 899.00, "待发货", "待分配", "-", "仓库打包中", "预计2026-07-29发货", 0, None, "13467898006", "杭州市西湖区文三路100号"),
        ("A100007", "U8007", "可口可乐 330ml×24罐", 49.90, "退款失败", "-", "-", "-", "-", 0, "退款失败，应转人工", "13378908007", "广州市天河区体育西路55号"),
        ("A100008", "U8008", "华为Watch GT4 手表", 1488.00, "运输中", "京东物流", "JD1122334455", "武汉转运中心", "后天2026-07-30送达", 1, "金额超500，退货转人工", "13289018008", "武汉市洪山区珞喻路100号"),
        ("A100009", "U8009", "Lego 21333 梵高《星月夜》", 1499.00, "已签收", "顺丰速运", "SF6677889900", "已送达", "已于2026-07-22送达", 1, "金额超500，退货转人工", "13190128009", "南京市建邺区江东中路300号"),
        ("A100010", "U8010", "三只松鼠坚果礼盒 1.5kg", 89.90, "运输中", "圆通速递", "YT3344556677", "分拨中心", "明天上午12:00前", 1, None, "13001238010", "深圳市南山区科技园南路10号"),
    ]
    cursor.executemany("""
        INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, orders)

    # === 退款记录 ===
    refunds = [
        ("A100003", "处理中", 159.00, "原路退回（微信支付）", "预计2026-07-30前到账", None),
        ("A100005", "已退款", 699.00, "原路退回（支付宝）", "2026-07-25已完成", None),
        ("A100007", "退款失败", 49.90, "原路退回", "需人工介入", "原支付账户异常"),
    ]
    cursor.executemany("INSERT INTO refunds VALUES (?,?,?,?,?,?)", refunds)

    # === 退货申请 ===
    requests = [
        ("R20260728001", "A100003", "退货", "质量问题", "已受理", "2026-07-27"),
        ("R20260725002", "A100005", "退货", "不喜欢", "已完成", "2026-07-24"),
    ]
    cursor.executemany("INSERT INTO return_requests VALUES (?,?,?,?,?,?)", requests)

    conn.commit()
    print(f"✅ 数据写入成功：{len(orders)}条订单（含手机号/地址），{len(refunds)}条退款，{len(requests)}条退货申请")


def verify_data(conn):
    """验证数据"""
    cursor = conn.cursor()

    print("\n📊 数据库验证：")
    print("-" * 60)
    cursor.execute("SELECT COUNT(*) FROM orders")
    print(f"订单总数：{cursor.fetchone()[0]}")

    cursor.execute("SELECT order_status, COUNT(*) FROM orders GROUP BY order_status")
    print("\n订单状态分布：")
    for status, count in cursor.fetchall():
        print(f"  {status}: {count}条")

    cursor.execute("SELECT order_id, phone FROM orders WHERE amount > 500 LIMIT 3")
    print(f"\n鉴权样例（金额>500订单的手机号）：")
    for oid, phone in cursor.fetchall():
        print(f"  {oid} - 尾号{phone[-4:]}")

    print("-" * 60)
    print("✅ v2 数据库就绪！")


if __name__ == "__main__":
    print("=" * 60)
    print("初始化 SQLite 数据库（v2：会话/工单/审计）")
    print("=" * 60)

    conn = init_database()
    insert_mock_data(conn)
    verify_data(conn)
    conn.close()

    print(f"\n📍 数据库文件位置：{SQLITE_DB_PATH}")
