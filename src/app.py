"""
智答 - 电商售后智能客服 Web 界面（Gradio 4.x 稳定版）
Gradio 4.x 的 ChatInterface 经过验证稳定，不会段错误。
运行：python app.py → 浏览器打开 http://localhost:7860
"""

import gradio as gr
from agent import CustomerServiceAgent

print("正在初始化客服Agent，请稍候...")
agent = CustomerServiceAgent()
print("✅ Agent就绪！")


def chat_respond(message, history):
    """对话回调（Gradio 4.x 非流式，最稳定）"""
    if not message or not message.strip():
        return ""
    try:
        result = agent.chat(message)
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
            reply = f"<div style='background:#f0f7ff;border-left:3px solid #1a73e8;padding:6px 10px;margin:8px 0;font-size:13px;color:#1a73e8'>{badges}</div>\n\n{reply}"
        if result.get("escalated"):
            reply += "\n\n<div style='background:#fff3e0;border-left:3px solid #ff9800;padding:8px 12px;margin:8px 0;border-radius:4px'>🔔 <b>系统提示</b>：已为您转接人工客服，紧急工单将优先处理。</div>"
        return reply
    except Exception as e:
        return f"抱歉，处理您的问题时出现异常：{e}。已为您转接人工客服。"


# ============================================
# CSS
# ============================================
CUSTOM_CSS = """
.gradio-container { max-width: 1100px !important; margin: auto !important; }
.brand-header {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white; padding: 24px; border-radius: 0 0 16px 16px; text-align: center;
}
.brand-header h1 { margin: 0; font-size: 24px; }
.brand-header p { margin: 6px 0 0; opacity: 0.9; font-size: 13px; }
.status-bar {
    display: flex; align-items: center; gap: 8px;
    background: #f6f8f9; padding: 8px 16px; border-radius: 8px; margin: 10px 0;
    font-size: 13px; color: #5f6368;
}
.status-dot { width: 8px; height: 8px; background: #34a853; border-radius: 50%; display: inline-block; }
.footer-info { text-align: center; color: #9aa0a6; font-size: 12px; padding: 14px 0; border-top: 1px solid #e8eaed; margin-top: 16px; }
"""

# ============================================
# 界面（Gradio 4.x 稳定 ChatInterface）
# ============================================
with gr.Blocks(title="智答 - 电商售后智能客服", css=CUSTOM_CSS) as demo:
    gr.HTML("""
    <div class="brand-header">
        <h1>🛍️ 智答 · 售后客服小答</h1>
        <p>基于 RAG + Agent 的智能客服 · 查物流 / 办退货 / 问政策 / 转人工</p>
    </div>
    <div class="status-bar">
        <span class="status-dot"></span>
        <span>客服小答 在线 · 平均响应 3-7 秒 · 支持办理真实业务</span>
    </div>
    """)

    with gr.Row():
        # 左侧主对话区
        with gr.Column(scale=4):
            gr.ChatInterface(
                fn=chat_respond,
                title="💬 和客服小答对话",
                description="直接输入您的问题，小答会查询订单、办理退换货、解答政策",
                retry_btn="重试",
                undo_btn="撤销",
                clear_btn="清空对话",
                examples=[
                    "我的订单A100001到哪了？",
                    "退货政策是什么？",
                    "我要退货A100002，不喜欢",
                    "帮我把A100004退了",
                    "查一下A100007的退款",
                    "我要投诉你们这破服务！",
                    "你好，你是谁？",
                ],
            )

        # 右侧信息栏
        with gr.Column(scale=1, min_width=220):
            gr.Markdown("""
            ### 📋 我能帮你做什么
            | 能力 | 说明 |
            |---|---|
            | 📦 查物流 | 告诉订单号 |
            | 🔄 办退货 | 想退换直接说 |
            | 💰 查退款 | 问退款进度 |
            | 📋 问政策 | 退换货规则 |
            | 👤 转人工 | 不满意随时转 |

            ### 🧪 演示订单
            | 订单号 | 场景 |
            |---|---|
            | A100001 | 查物流 |
            | A100002 | 普通退货 |
            | A100003 | 查退款 |
            | A100004 | 金额超限 |
            | A100007 | 退款失败 |

            <div style='font-size:11px;color:#9aa0a6'>
            ℹ️ 也可输入任意订单号，系统如实告知是否查到
            </div>

            ### 🔧 技术栈
            <div style='font-size:12px'>
            LangChain · Chroma<br/>DeepSeek · 智谱 · SQLite
            </div>
            """)

    gr.HTML('<div class="footer-info">智答 · 电商售后智能客服 ｜ AI产品经理作品集项目 ｜ Powered by RAG + Agent</div>')


if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True,
    )
