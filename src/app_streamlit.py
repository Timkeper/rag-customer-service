"""
智答 - 电商售后智能客服 Web 界面（Streamlit 稳定版）
Streamlit 的聊天组件稳定可靠，不会像 Gradio 那样有版本兼容问题。

运行：streamlit run app_streamlit.py
浏览器自动打开 http://localhost:8501
"""

import streamlit as st
from agent import CustomerServiceAgent
import db_tools

# ============ 页面配置 ============
st.set_page_config(
    page_title="智答 - 电商售后智能客服",
    page_icon="🛍️",
    layout="wide",
)

# ============ 自定义样式 ============
st.markdown("""
<style>
    /* 顶部品牌区 */
    .brand-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white; padding: 20px 24px; border-radius: 0 0 12px 12px;
        text-align: center; margin-bottom: 8px;
    }
    .brand-header h1 { margin: 0; font-size: 26px; }
    .brand-header p { margin: 4px 0 0; opacity: 0.9; font-size: 13px; }
    /* 状态条 */
    .status-bar {
        background: #f6f8f9; padding: 8px 16px; border-radius: 8px;
        margin: 8px 0 16px; font-size: 13px; color: #5f6368;
        display: flex; align-items: center; gap: 8px;
    }
    .status-dot {
        width: 8px; height: 8px; background: #34a853; border-radius: 50%;
        display: inline-block;
    }
    /* 隐藏Streamlit默认元素 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display: none;}
</style>
""", unsafe_allow_html=True)


# ============ 初始化 Agent（缓存，只加载一次）============
@st.cache_resource
def get_agent():
    return CustomerServiceAgent()


# ============ 页面布局 ============
# 顶部品牌
st.markdown("""
<div class="brand-header">
    <h1>🛍️ 智答 · 售后客服小答</h1>
    <p>基于 RAG + Agent 的智能客服 · 查物流 / 办退货 / 问政策 / 转人工</p>
</div>
<div class="status-bar">
    <span class="status-dot"></span>
    <span>客服小答 在线 · 平均响应 3-7 秒 · 支持办理真实业务</span>
</div>
""", unsafe_allow_html=True)

# 左右布局
col_chat, col_info = st.columns([4, 1])

with col_info:
    st.markdown("### 📋 我能帮你做什么")
    st.markdown("""
    | 能力 | 说明 |
    |---|---|
    | 📦 查物流 | 告诉订单号 |
    | 🔄 办退货 | 想退换直接说 |
    | 💰 查退款 | 问退款进度 |
    | 📋 问政策 | 退换货规则 |
    | 👤 转人工 | 不满意随时转 |
    """)
    st.divider()
    st.markdown("### 🛒 模拟下单（测试新订单）")
    st.caption("输入商品信息生成新订单，之后可在对话中查询/退货")
    with st.form("order_form"):
        item_name = st.text_input("商品名称", value="蓝牙音箱", key="item_name")
        item_amount = st.number_input("金额（元）", min_value=0.1, value=128.0, step=10.0, key="item_amount")
        submitted = st.form_submit_button("📦 模拟下单", use_container_width=True)
        if submitted:
            result = db_tools.create_order(item_name, item_amount)
            if result["success"]:
                new_oid = result["order_id"]
                st.session_state.last_order = new_oid
                st.success(f"下单成功！\n订单号：**{new_oid}**\n（{item_name} ¥{item_amount}）")
                st.info("💡 现在可以在对话框输入：\n「我的订单{oid}到哪了」查询".format(oid=new_oid))

    st.divider()
    st.markdown("### 🧪 预置演示订单")
    st.markdown("""
    | 订单号 | 场景 |
    |---|---|
    | A100001 | 查物流 |
    | A100002 | 普通退货 |
    | A100003 | 查退款 |
    | A100004 | 金额超限 |
    | A100007 | 退款失败 |
    """)
    st.caption("ℹ️ 也可输入任意订单号，系统如实告知是否查到")
    st.divider()
    st.markdown("### 🔧 技术栈")
    st.caption("LangChain · Chroma\nDeepSeek · 智谱 · SQLite")

with col_chat:
    # 初始化会话状态
    if "messages" not in st.session_state:
        st.session_state.messages = []
        # 欢迎语
        st.session_state.messages.append({
            "role": "assistant",
            "content": "您好！我是售后客服小答 🤖\n\n我可以帮您：\n- 📦 查询订单物流\n- 🔄 办理退换货\n- 💰 查询退款进度\n- 📋 解答退货政策\n\n请问有什么可以帮您的？"
        })

    # 显示历史消息
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"], unsafe_allow_html=True)

    # 快捷问题按钮
    st.caption("💡 快捷提问：")
    qc1, qc2, qc3, qc4 = st.columns(4)
    quick_prompts = {
        qc1: "我的订单A100001到哪了？",
        qc2: "退货政策是什么？",
        qc3: "帮我把A100004退了",
        qc4: "我要投诉你们！",
    }
    for col, prompt in quick_prompts.items():
        if col.button(prompt, use_container_width=True, key=f"q_{prompt}"):
            st.session_state.pending_input = prompt

    # 用户输入
    user_input = st.chat_input("请输入您的问题，如：我的订单A100001到哪了？")

    # 处理快捷按钮的输入
    if "pending_input" in st.session_state:
        user_input = st.session_state.pending_input
        del st.session_state.pending_input

    if user_input:
        # 显示用户消息
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        # 获取 Agent 回复
        with st.chat_message("assistant"):
            with st.spinner("小答正在为您处理..."):
                try:
                    agent = get_agent()
                    result = agent.chat(user_input)
                    reply = result["reply"]
                    tools = result.get("tools_used", [])

                    # 工具调用提示
                    if tools:
                        labels = {
                            "query_order_status": "📦 已查询订单物流",
                            "query_return_policy": "📋 已检索退货政策",
                            "submit_return_request": "🔄 已提交退货申请",
                            "check_refund_progress": "💰 已查询退款进度",
                            "escalate_to_human": "👤 已转接人工客服",
                        }
                        badges = "  ".join(labels.get(t, "✅ 已处理") for t in tools)
                        st.info(badges)

                    st.markdown(reply, unsafe_allow_html=True)

                    # 转人工高亮
                    if result.get("escalated"):
                        st.warning("🔔 **系统提示**：已为您转接人工客服，紧急工单将优先处理。")

                    # 保存到历史（用纯文本，不含HTML标签）
                    st.session_state.messages.append({"role": "assistant", "content": reply})

                except Exception as e:
                    error_msg = f"抱歉，处理您的问题时出现异常：{e}"
                    st.error(error_msg)
                    st.session_state.messages.append({"role": "assistant", "content": error_msg})
