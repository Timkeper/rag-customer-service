# -*- coding: utf-8 -*-
"""
智答 - 电商售后智能客服 | AI产品经理作品集 PDF 生成脚本
技术栈：ReportLab
输出：portfolio.pdf (18页)
"""
import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image, Table, TableStyle,
    KeepTogether, HRFlowable, ListFlowable, ListItem
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ============ 字体注册（中文）============
FONT_REG = 'Helvetica'
FONT_BOLD = 'Helvetica-Bold'
# 尝试注册系统中文字体
_font_paths = [
    ('STHeiti', 'C:/Windows/Fonts/msyh.ttc'),      # 微软雅黑
    ('STHeiti', 'C:/Windows/Fonts/simhei.ttf'),     # 黑体
]
for fname, fpath in _font_paths:
    if os.path.exists(fpath):
        try:
            pdfmetrics.registerFont(TTFont(fname, fpath))
            FONT_REG = fname
            FONT_BOLD = fname
            break
        except Exception:
            pass
# 尝试加粗字体
_bold_paths = [
    ('STHeitiBold', 'C:/Windows/Fonts/msyhbd.ttc'),
]
for fname, fpath in _bold_paths:
    if os.path.exists(fpath):
        try:
            pdfmetrics.registerFont(TTFont(fname, fpath))
            FONT_BOLD = fname
            break
        except Exception:
            FONT_BOLD = FONT_REG

# ============ 调色板 ============
PAGE_BG       = colors.HexColor('#ffffff')
SECTION_BG    = colors.HexColor('#f0f1f2')
CARD_BG       = colors.HexColor('#f6f8f9')
TABLE_STRIPE  = colors.HexColor('#f1f5f7')
HEADER_FILL   = colors.HexColor('#3d535d')
COVER_BLOCK   = colors.HexColor('#5d747f')
BORDER        = colors.HexColor('#b3c3cb')
ICON          = colors.HexColor('#4787a6')
ACCENT        = colors.HexColor('#b43248')
ACCENT_2      = colors.HexColor('#1a73e8')
TEXT_PRIMARY  = colors.HexColor('#191b1c')
TEXT_MUTED    = colors.HexColor('#6b7280')
SEM_SUCCESS   = colors.HexColor('#4e8861')
SEM_ERROR     = colors.HexColor('#9b4c45')

# ============ 页面设置 ============
PAGE_W, PAGE_H = A4
MARGIN = 18 * mm
CONTENT_W = PAGE_W - 2 * MARGIN

# ============ 样式 ============
def make_styles():
    s = {}
    s['Title'] = ParagraphStyle('Title', fontName=FONT_BOLD, fontSize=28, leading=36,
                                textColor=TEXT_PRIMARY, alignment=TA_LEFT, spaceAfter=8)
    s['Subtitle'] = ParagraphStyle('Subtitle', fontName=FONT_REG, fontSize=14, leading=20,
                                   textColor=TEXT_MUTED, alignment=TA_LEFT, spaceAfter=6)
    s['H1'] = ParagraphStyle('H1', fontName=FONT_BOLD, fontSize=20, leading=28,
                             textColor=HEADER_FILL, alignment=TA_LEFT, spaceBefore=10, spaceAfter=10)
    s['H2'] = ParagraphStyle('H2', fontName=FONT_BOLD, fontSize=14, leading=20,
                             textColor=TEXT_PRIMARY, alignment=TA_LEFT, spaceBefore=8, spaceAfter=6)
    s['H3'] = ParagraphStyle('H3', fontName=FONT_BOLD, fontSize=11, leading=16,
                             textColor=ACCENT, alignment=TA_LEFT, spaceBefore=6, spaceAfter=4)
    s['Body'] = ParagraphStyle('Body', fontName=FONT_REG, fontSize=10, leading=17,
                               textColor=TEXT_PRIMARY, alignment=TA_JUSTIFY, spaceAfter=6, wordWrap='CJK')
    s['BodyMuted'] = ParagraphStyle('BodyMuted', fontName=FONT_REG, fontSize=9, leading=15,
                                    textColor=TEXT_MUTED, alignment=TA_LEFT, wordWrap='CJK')
    s['Bullet'] = ParagraphStyle('Bullet', fontName=FONT_REG, fontSize=10, leading=16,
                                 textColor=TEXT_PRIMARY, alignment=TA_LEFT, leftIndent=14,
                                 bulletIndent=2, wordWrap='CJK', spaceAfter=3)
    s['Caption'] = ParagraphStyle('Caption', fontName=FONT_REG, fontSize=8.5, leading=12,
                                  textColor=TEXT_MUTED, alignment=TA_CENTER, spaceBefore=4, spaceAfter=10)
    s['CoverKicker'] = ParagraphStyle('CoverKicker', fontName=FONT_BOLD, fontSize=11, leading=14,
                                      textColor=ACCENT, alignment=TA_LEFT)
    s['CoverHero'] = ParagraphStyle('CoverHero', fontName=FONT_BOLD, fontSize=40, leading=48,
                                    textColor=TEXT_PRIMARY, alignment=TA_LEFT)
    s['CoverMeta'] = ParagraphStyle('CoverMeta', fontName=FONT_REG, fontSize=12, leading=18,
                                    textColor=TEXT_MUTED, alignment=TA_LEFT)
    s['CoverSummary'] = ParagraphStyle('CoverSummary', fontName=FONT_REG, fontSize=11, leading=19,
                                       textColor=TEXT_PRIMARY, alignment=TA_LEFT, wordWrap='CJK')
    s['Quote'] = ParagraphStyle('Quote', fontName=FONT_BOLD, fontSize=12, leading=20,
                                textColor=ACCENT, alignment=TA_LEFT, leftIndent=10, wordWrap='CJK')
    s['TableHeader'] = ParagraphStyle('TableHeader', fontName=FONT_BOLD, fontSize=9, leading=13,
                                      textColor=colors.white, alignment=TA_CENTER)
    s['TableCell'] = ParagraphStyle('TableCell', fontName=FONT_REG, fontSize=8.5, leading=12,
                                    textColor=TEXT_PRIMARY, alignment=TA_CENTER, wordWrap='CJK')
    s['TableCellL'] = ParagraphStyle('TableCellL', fontName=FONT_REG, fontSize=8.5, leading=12,
                                     textColor=TEXT_PRIMARY, alignment=TA_LEFT, wordWrap='CJK')
    s['Footer'] = ParagraphStyle('Footer', fontName=FONT_REG, fontSize=8, leading=10,
                                 textColor=TEXT_MUTED, alignment=TA_CENTER)
    return s

ST = make_styles()

# ============ 页眉页脚 ============
def on_page(canvas, doc):
    canvas.saveState()
    page_num = doc.page
    if page_num > 1:
        # 页眉小标题
        canvas.setFont(FONT_REG, 8)
        canvas.setFillColor(TEXT_MUTED)
        canvas.drawString(MARGIN, PAGE_H - 10*mm, "智答 · 电商售后智能客服 | AI产品经理作品集")
        canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - 10*mm, "冉航")
        canvas.setStrokeColor(BORDER)
        canvas.setLineWidth(0.3)
        canvas.line(MARGIN, PAGE_H - 12*mm, PAGE_W - MARGIN, PAGE_H - 12*mm)
        # 页脚页码
        canvas.drawCentredString(PAGE_W/2, 10*mm, f"— {page_num} —")
    canvas.restoreState()

# ============ 辅助组件 ============
def hr(color=BORDER, thickness=0.5, space=4):
    return HRFlowable(width="100%", thickness=thickness, color=color,
                      spaceBefore=space, spaceAfter=space)

def section_header(num, title):
    """带编号的章节标题"""
    t = Table([[Paragraph(f'<font color="#b43248"><b>{num}</b></font>', ST['H1']),
                Paragraph(title, ST['H1'])]],
              colWidths=[18*mm, CONTENT_W - 18*mm])
    t.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LINEBELOW', (0,0), (-1,-1), 1.5, ACCENT),
    ]))
    return t

def info_card(title, content_html, bg=CARD_BG):
    """信息卡片"""
    inner = [Paragraph(f'<b>{title}</b>', ST['H3']), Paragraph(content_html, ST['Body'])]
    t = Table([[inner]], colWidths=[CONTENT_W])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), bg),
        ('BOX', (0,0), (-1,-1), 0.5, BORDER),
        ('LEFTPADDING', (0,0), (-1,-1), 12),
        ('RIGHTPADDING', (0,0), (-1,-1), 12),
        ('TOPPADDING', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
    ]))
    return t

def data_table(headers, rows, col_ratios=None):
    """数据表格"""
    n = len(headers)
    if col_ratios is None:
        col_ratios = [1/n]*n
    col_widths = [r * CONTENT_W for r in col_ratios]
    data = [[Paragraph(h, ST['TableHeader']) for h in headers]]
    for row in rows:
        data.append([Paragraph(str(c), ST['TableCellL'] if i==0 else ST['TableCell']) for i,c in enumerate(row)])
    t = Table(data, colWidths=col_widths, repeatRows=1)
    style = [
        ('BACKGROUND', (0,0), (-1,0), HEADER_FILL),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), FONT_BOLD),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.4, BORDER),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
    ]
    for i in range(1, len(data)):
        if i % 2 == 0:
            style.append(('BACKGROUND', (0,i), (-1,i), TABLE_STRIPE))
    t.setStyle(TableStyle(style))
    return t

def metric_box(label, value, color=ACCENT):
    """指标小方块"""
    # hexval() 返回 '0x1a73e8'，转成 '#1a73e8' 给 font 标签用
    hex_str = '#' + color.hexval().replace('0x', '')[-6:]
    inner = [
        Paragraph(f'<font color="{hex_str}"><b>{value}</b></font>',
                  ParagraphStyle('m', fontName=FONT_BOLD, fontSize=22, leading=26,
                                 textColor=color, alignment=TA_CENTER)),
        Paragraph(label, ParagraphStyle('ml', fontName=FONT_REG, fontSize=8.5, leading=11,
                                        textColor=TEXT_MUTED, alignment=TA_CENTER, wordWrap='CJK')),
    ]
    t = Table([[inner]], colWidths=[(CONTENT_W-12)/3])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), CARD_BG),
        ('BOX', (0,0), (-1,-1), 0.5, BORDER),
        ('TOPPADDING', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    return t

def metrics_row(items):
    """一行3个指标"""
    cells = []
    for label, value, color in items:
        cells.append(metric_box(label, value, color))
    t = Table([cells], colWidths=[(CONTENT_W)/3]*3)
    t.setStyle(TableStyle([
        ('LEFTPADDING', (0,0), (-1,-1), 2),
        ('RIGHTPADDING', (0,0), (-1,-1), 2),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    return t

# ============ 内容构建 ============
def build_story():
    story = []

    # ========== 封面 ==========
    story.append(Spacer(1, 35*mm))
    story.append(Paragraph("AI PRODUCT MANAGER PORTFOLIO", ST['CoverKicker']))
    story.append(Spacer(1, 6*mm))
    story.append(Paragraph("智答", ST['CoverHero']))
    story.append(Paragraph("电商售后智能客服", ParagraphStyle('h2', fontName=FONT_BOLD, fontSize=22,
                    leading=30, textColor=COVER_BLOCK, alignment=TA_LEFT)))
    story.append(Spacer(1, 8*mm))
    story.append(Paragraph("基于 RAG + Agent 的垂直场景大模型应用", ST['CoverMeta']))
    story.append(Spacer(1, 18*mm))
    story.append(HRFlowable(width=60*mm, thickness=2, color=ACCENT, spaceBefore=0, spaceAfter=10))
    story.append(Paragraph(
        "本项目以电商售后为切入点，构建了一个集成知识库检索（RAG）与工具调用（Function Calling Agent）的智能客服系统。"
        "通过自建 50 题评测集与三种方案（裸模型 / 纯RAG / RAG+Agent）的对比实验，"
        "用数据验证了 RAG+Agent 方案在业务办理与转人工场景的显著价值，并形成「评测—分析—优化」闭环。",
        ST['CoverSummary']))
    story.append(Spacer(1, 35*mm))
    story.append(Paragraph("技术栈：LangChain · Chroma · DeepSeek · 智谱Embedding · SQLite · Gradio",
                           ST['BodyMuted']))
    story.append(Paragraph("应聘岗位：京东科技 · AI产品经理实习生", ST['BodyMuted']))
    story.append(PageBreak())

    # ========== P2 目录/项目概述 ==========
    story.append(section_header("01", "项目概述"))
    story.append(Spacer(1, 4))
    story.append(Paragraph("为什么做这个项目", ST['H2']))
    story.append(Paragraph(
        "大模型应用正从「能聊天」走向「能办事」。但通用大模型在垂直业务场景中存在三大痛点："
        "<b>幻觉</b>（编造订单与政策）、<b>无法办理业务</b>（不能查物流、不能退货）、"
        "<b>缺乏安全边界</b>（不会识别情绪、不会转人工）。本项目正是为验证「RAG + Agent」组合如何系统性解决这些问题。",
        ST['Body']))
    story.append(Spacer(1, 6))
    story.append(Paragraph("核心成果（一图速览）", ST['H2']))
    story.append(Spacer(1, 6))
    story.append(metrics_row([
        ("业务办理能力", "0→100%", SEM_SUCCESS),
        ("转人工触发率", "0→100%", SEM_SUCCESS),
        ("工具选择准确率", "80%", ACCENT_2),
    ]))
    story.append(Spacer(1, 8))
    story.append(metrics_row([
        ("评测题集", "50题", HEADER_FILL),
        ("对比方案", "3组", HEADER_FILL),
        ("优化提升", "+38%", ACCENT),
    ]))
    story.append(Spacer(1, 12))
    story.append(info_card("项目一句话总结",
        "一个「电商售后智能客服」：用 RAG 答知识、用 Agent 办业务，自建评测体系，"
        "用三维度数据证明 RAG+Agent 将转人工触发率与业务办理能力从 0% 提升到 100%。"))
    story.append(PageBreak())

    # ========== P3 背景与痛点 ==========
    story.append(section_header("02", "行业背景与用户痛点"))
    story.append(Paragraph("传统人工客服的局限", ST['H2']))
    story.append(ListFlowable([
        ListItem(Paragraph("<b>成本高</b>：售后咨询量大，重复性问题占比超 60%，人工处理效率低。", ST['Bullet'])),
        ListItem(Paragraph("<b>夜间无人</b>：夜间与节假日客服资源薄弱，用户诉求响应滞后。", ST['Bullet'])),
        ListItem(Paragraph("<b>情绪化风险</b>：人工客服长时间重复作业易疲劳，服务质量不稳定。", ST['Bullet'])),
    ], bulletType='bullet', start='•'))
    story.append(Spacer(1, 6))
    story.append(Paragraph("通用大模型的局限（裸模型实测）", ST['H2']))
    story.append(Paragraph(
        "在评测中发现，直接使用 DeepSeek 裸模型回答售后问题时：<br/>"
        "① 用户问「订单A100001到哪了」，模型<b>编造物流数据</b>（实际未查任何数据库）；<br/>"
        "② 用户说「我要投诉」，模型<b>只安抚不转人工</b>，违反安全规则；<br/>"
        "③ 用户说「帮我退货」，模型<b>口头答应却不执行</b>任何操作。",
        ST['Body']))
    story.append(Spacer(1, 8))
    story.append(Paragraph("机会点", ST['H2']))
    story.append(info_card("我的判断",
        "客服场景天然适合 AI 落地——高频、标准化、可评测。但单纯的「聊天机器人」不够，"
        "必须做到：<b>答得准（RAG）+ 办得了（Agent）+ 知边界（转人工）</b>。这是本项目的核心命题。",
        bg=colors.HexColor('#fef3f4')))
    story.append(PageBreak())

    # ========== P4 调研：竞品分析 ==========
    story.append(section_header("03", "竞品调研"))
    story.append(Paragraph("主流 AI 客服能力对比", ST['H2']))
    story.append(Paragraph("通过体验京东客服（言犀）、智齿科技、网易七鱼、阿里小蜜等，梳理能力矩阵：", ST['BodyMuted']))
    story.append(Spacer(1, 6))
    story.append(data_table(
        ["能力维度", "通用大模型", "纯RAG客服", "本项目(RAG+Agent)", "成熟商用方案"],
        [
            ["知识库问答", "✗ 幻觉", "✓ 基于知识库", "✓ 基于知识库", "✓"],
            ["查物流/订单", "✗ 编造", "✗ 无法查", "✓ 调工具", "✓"],
            ["办理退换货", "✗ 无法办", "✗ 无法办", "✓ 调工具", "✓"],
            ["情绪转人工", "✗ 不转", "✗ 不转", "✓ 关键词+规则", "✓"],
            ["金额超限拦截", "✗", "✗", "✓ 自动转人工", "✓"],
            ["可评测性", "难", "中", "✓ 自建体系", "黑盒"],
        ],
        col_ratios=[0.22, 0.18, 0.18, 0.24, 0.18]
    ))
    story.append(Spacer(1, 10))
    story.append(Paragraph("调研结论", ST['H2']))
    story.append(ListFlowable([
        ListItem(Paragraph("成熟商用方案能力全面，但作为求职作品无法复现其工程复杂度；", ST['Bullet'])),
        ListItem(Paragraph("通用大模型与纯RAG都「办不了业务」，这是核心差异点；", ST['Bullet'])),
        ListItem(Paragraph("本项目的<b>差异化定位</b>：用 Agent 补齐「办事」能力，用评测体系证明价值。", ST['Bullet'])),
    ], bulletType='bullet', start='•'))
    story.append(PageBreak())

    # ========== P5 产品设计：功能架构 ==========
    story.append(section_header("04", "产品设计"))
    story.append(Paragraph("产品能力分层", ST['H2']))
    story.append(Paragraph("系统分为三层：<b>RAG 知识层</b>（答政策）、<b>Agent 工具层</b>（办业务）、<b>安全边界层</b>（转人工）。", ST['Body']))
    story.append(Spacer(1, 6))
    story.append(data_table(
        ["层级", "能力", "实现方式", "评测维度"],
        [
            ["RAG知识层", "退货/换货/退款政策问答", "FAQ→分块→Embedding→Chroma检索→生成", "准确性/相关性/完整性"],
            ["Agent工具层", "查物流、办退货、查退款", "Function Calling + SQLite业务库", "工具准确率/参数准确率/任务完成率"],
            ["安全边界层", "转人工、金额拦截、情绪安抚", "关键词检测+业务规则+兜底", "转人工触发率/误调用率"],
        ],
        col_ratios=[0.18, 0.28, 0.34, 0.20]
    ))
    story.append(Spacer(1, 10))
    story.append(Paragraph("核心交互流程", ST['H2']))
    flow = Table([[
        Paragraph("<b>用户输入</b>", ST['TableCell']),
        Paragraph("→", ST['TableCell']),
        Paragraph("<b>情绪检测</b><br/><font color='#9b4c45'>命中关键词？</font>", ST['TableCell']),
        Paragraph("→", ST['TableCell']),
        Paragraph("<b>Agent决策</b><br/><font color='#1a73e8'>调工具 or 查RAG</font>", ST['TableCell']),
        Paragraph("→", ST['TableCell']),
        Paragraph("<b>工具执行</b><br/><font color='#1a73e8'>返回结果</font>", ST['TableCell']),
        Paragraph("→", ST['TableCell']),
        Paragraph("<b>生成回复</b><br/><font color='#4e8861'>是否转人工</font>", ST['TableCell']),
    ]], colWidths=[CONTENT_W/9*1.3]*5 + [CONTENT_W/9*0.5]*4)
    flow.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,0), CARD_BG),
        ('BACKGROUND', (2,0), (2,0), colors.HexColor('#fef3f4')),
        ('BACKGROUND', (4,0), (4,0), colors.HexColor('#e8f0fe')),
        ('BACKGROUND', (6,0), (6,0), colors.HexColor('#e8f0fe')),
        ('BACKGROUND', (8,0), (8,0), colors.HexColor('#e6f4ea')),
        ('BOX', (0,0), (0,0), 0.5, BORDER),
        ('BOX', (2,0), (2,0), 0.5, BORDER),
        ('BOX', (4,0), (4,0), 0.5, BORDER),
        ('BOX', (6,0), (6,0), 0.5, BORDER),
        ('BOX', (8,0), (8,0), 0.5, BORDER),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(flow)
    story.append(PageBreak())

    # ========== P6 技术架构 ==========
    story.append(section_header("05", "技术架构"))
    story.append(Paragraph("技术选型与理由", ST['H2']))
    story.append(data_table(
        ["模块", "技术选型", "选型理由（面试可答）"],
        [
            ["大模型", "DeepSeek-Chat", "国产、便宜、支持Function Calling、对话质量高"],
            ["RAG框架", "LangChain", "生态成熟，可控性强，便于面试讲清原理"],
            ["向量库", "Chroma", "本地轻量、免费、无需额外部署，适合Demo级项目"],
            ["Embedding", "智谱 embedding-2", "国内直连、免费额度、中文效果好"],
            ["业务数据库", "SQLite", "零部署、关系型，便于体现工程思维"],
            ["Web界面", "Gradio", "10行代码出聊天界面，适合快速演示"],
        ],
        col_ratios=[0.16, 0.24, 0.60]
    ))
    story.append(Spacer(1, 10))
    story.append(Paragraph("RAG 核心流程（5步）", ST['H2']))
    steps = Table([[
        Paragraph("<b>① 文档加载</b><br/>读取22条FAQ", ST['TableCell']),
        Paragraph("<b>② 分块</b><br/>按标题切，300字/块", ST['TableCell']),
        Paragraph("<b>③ 向量化</b><br/>智谱Embedding", ST['TableCell']),
        Paragraph("<b>④ 入库</b><br/>存入Chroma", ST['TableCell']),
        Paragraph("<b>⑤ 检索生成</b><br/>Top-3召回+大模型", ST['TableCell']),
    ]], colWidths=[CONTENT_W/5]*5)
    steps.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), CARD_BG),
        ('BOX', (0,0), (-1,-1), 0.5, BORDER),
        ('INNERGRID', (0,0), (-1,-1), 0.5, BORDER),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 12),
        ('BOTTOMPADDING', (0,0), (-1,-1), 12),
    ]))
    story.append(steps)
    story.append(Spacer(1, 8))
    story.append(Paragraph("关键参数（config.py，面试讲清为什么）", ST['H3']))
    story.append(Paragraph(
        "<b>temperature=0.3</b>（客服要准确，不能太随机）｜ <b>CHUNK_SIZE=300</b>"
        "（太小丢上下文，太大召回不准）｜ <b>Top-K=3</b>（召回3条最相关FAQ）｜ "
        "<b>金额超限=500元</b>（高于此值转人工确认）", ST['Body']))
    story.append(PageBreak())

    # ========== P7 Agent 工具设计 ==========
    story.append(section_header("06", "Agent 工具设计"))
    story.append(Paragraph("5 个 Function Calling 工具", ST['H2']))
    story.append(Paragraph("每个工具 = 名称 + 触发场景描述 + 参数Schema + 执行函数。工具的 description 设计直接影响调用准确率。", ST['BodyMuted']))
    story.append(Spacer(1, 6))
    story.append(data_table(
        ["工具名", "触发场景", "关键参数", "数据源"],
        [
            ["query_order_status", "用户问订单到哪/何时到货", "order_id", "SQLite订单表"],
            ["query_return_policy", "用户问退货/换货/退款政策", "question", "Chroma知识库"],
            ["submit_return_request", "用户明确要退货/换货", "order_id, type, reason", "SQLite+规则"],
            ["check_refund_progress", "用户问退款到账/进度", "order_id", "SQLite退款表"],
            ["escalate_to_human", "情绪激烈/金额超限/退款失败", "reason, priority", "工单系统"],
        ],
        col_ratios=[0.24, 0.30, 0.26, 0.20]
    ))
    story.append(Spacer(1, 10))
    story.append(Paragraph("三条转人工触发规则（安全边界设计）", ST['H2']))
    story.append(ListFlowable([
        ListItem(Paragraph("<b>情绪激烈</b>：检测到投诉/辱骂/差评等关键词 → 立即转人工（紧急优先级）。", ST['Bullet'])),
        ListItem(Paragraph("<b>金额超限</b>：退货金额 &gt; 500元 → 必须转人工确认，保障用户权益。", ST['Bullet'])),
        ListItem(Paragraph("<b>业务异常</b>：退款失败等系统异常 → 转人工介入处理。", ST['Bullet'])),
    ], bulletType='bullet', start='•'))
    story.append(PageBreak())

    # ========== P8 评测体系设计 ==========
    story.append(section_header("07", "评测体系设计（核心方法论）"))
    story.append(Paragraph("为什么自建评测体系", ST['H2']))
    story.append(Paragraph(
        "「能不能用数据说话」是 AI 产品经理的核心能力。我没有止步于「Demo能跑」，"
        "而是构建了一套覆盖三维度、50题的可复用评测体系——这正是岗位JD反复强调的「定义评测标准、提炼优化点」。",
        ST['Body']))
    story.append(Spacer(1, 8))
    story.append(Paragraph("50题评测集（5大类）", ST['H2']))
    story.append(data_table(
        ["类别", "题量", "测试目标", "关键指标"],
        [
            ["A 退货政策咨询", "15题", "RAG知识检索准确性", "准确性/相关性/完整性"],
            ["B 订单物流查询", "10题", "query_order_status工具", "工具选择/参数准确率"],
            ["C 退货退款办理", "12题", "submit/check工具+金额拦截", "任务完成率/安全性"],
            ["D 转人工场景", "8题", "escalate_to_human工具", "转人工触发率"],
            ["E 边界与抗干扰", "5题", "意图识别/防误调用", "误调用率"],
        ],
        col_ratios=[0.26, 0.12, 0.36, 0.26]
    ))
    story.append(Spacer(1, 10))
    story.append(Paragraph("三种对比方案", ST['H2']))
    story.append(info_card("对比实验设计",
        "<b>Baseline 裸模型</b>：直接用DeepSeek回答（无RAG无工具）—— 验证「不做增强有多差」<br/>"
        "<b>纯 RAG</b>：只查知识库，不调工具 —— 验证「能答但办不了业务」<br/>"
        "<b>RAG + Agent</b>：完整方案 —— 验证「既能答又能办」"))
    story.append(PageBreak())

    # ========== P9 核心实验结果（最重要的一页）==========
    story.append(section_header("08", "实验结果：三方案对比"))
    story.append(Paragraph("核心指标对比（作品集核心页）", ST['H2']))
    img_path = os.path.join(os.path.dirname(__file__), "comparison_metrics.png")
    if os.path.exists(img_path):
        story.append(Image(img_path, width=CONTENT_W, height=CONTENT_W*0.72))
        story.append(Paragraph("图1：四种核心能力对比（Baseline / RAG / Agent）", ST['Caption']))
    story.append(Spacer(1, 6))
    story.append(data_table(
        ["指标", "Baseline裸模型", "RAG纯检索", "Agent完整版", "结论"],
        [
            ["转人工触发率", "0%", "0%", "100%", "仅Agent能转人工"],
            ["业务办理能力", "0%", "100%", "100%", "需工具调用支持"],
            ["工具选择准确率", "—", "—", "80%", "Agent表现良好"],
            ["误调用率", "0%", "0%", "20%", "边界识别待优化"],
            ["平均延迟", "1672ms", "2290ms", "3654ms", "Agent因多轮调用更慢"],
        ],
        col_ratios=[0.22, 0.20, 0.17, 0.18, 0.23]
    ))
    story.append(Spacer(1, 8))
    story.append(Paragraph("一句话结论", ST['Quote']))
    story.append(Paragraph(
        "「裸模型和纯RAG都无法办理业务和转人工，而 RAG+Agent 方案实现了 100% 的转人工触发与业务办理能力。」",
        ST['Quote']))
    story.append(PageBreak())

    # ========== P10 延迟分析 ==========
    story.append(section_header("09", "性能分析"))
    story.append(Paragraph("延迟取舍", ST['H2']))
    img_path2 = os.path.join(os.path.dirname(__file__), "comparison_latency.png")
    if os.path.exists(img_path2):
        story.append(Image(img_path2, width=CONTENT_W*0.82, height=CONTENT_W*0.82*0.6))
        story.append(Paragraph("图2：平均响应延迟对比", ST['Caption']))
    story.append(Spacer(1, 6))
    story.append(Paragraph("分析", ST['Body']))
    story.append(ListFlowable([
        ListItem(Paragraph("Agent 平均延迟 3654ms，高于 Baseline 的 1672ms，主要因为 Agent 需要<b>多轮工具调用</b>（先查订单再查政策再生成）。", ST['Bullet'])),
        ListItem(Paragraph("这是<b>能力与性能的合理取舍</b>：Agent 多花的 2 秒换来的是「真能办成事」，而非裸模型的「秒回但没用」。", ST['Bullet'])),
        ListItem(Paragraph("<b>优化方向</b>：可引入流式输出（Stream）让用户感知更快；并行调用无依赖的工具。", ST['Bullet'])),
    ], bulletType='bullet', start='•'))
    story.append(PageBreak())

    # ========== P11 深度案例1 ==========
    story.append(section_header("10", "深度案例一：为什么需要 Agent"))
    story.append(info_card("发现问题",
        "在跑 Baseline 评测时发现：用户问「订单A100001到哪了」，裸模型回答「我帮您查一下……请问您方便提供手机号吗」——"
        "它<b>根本没有查询能力</b>，只是在表演查单。而纯RAG回答「知识库中无此功能」。两者都办不了业务。"))
    story.append(Spacer(1, 6))
    story.append(info_card("解决方案",
        "引入 Function Calling，让 Agent 能调用 query_order_status 工具直接查 SQLite 订单库，"
        "拿到真实物流数据后再生成回答。", bg=colors.HexColor('#e8f0fe')))
    story.append(Spacer(1, 6))
    story.append(info_card("数据验证",
        "对比实验显示：<b>业务办理能力从 0%（Baseline/RAG）提升到 100%（Agent）</b>。"
        "Agent 能正确查询订单、办理退货、查询退款，而前两者完全不能。", bg=colors.HexColor('#e6f4ea')))
    story.append(Spacer(1, 8))
    story.append(Paragraph("产品思考", ST['H3']))
    story.append(Paragraph(
        "RAG 解决「答得准」，Agent 解决「办得了」。客服场景的核心价值不仅是回答问题，"
        "更是<b>替用户完成动作</b>（查、办、退）。没有 Agent，AI 客服永远只是「嘴上功夫」。",
        ST['Body']))
    story.append(PageBreak())

    # ========== P12 深度案例2（优化闭环）==========
    story.append(section_header("11", "深度案例二：评测驱动的优化"))
    story.append(Paragraph("这是「评测—分析—优化」闭环的最佳证明", ST['H2']))
    img_path3 = os.path.join(os.path.dirname(__file__), "optimization_case.png")
    if os.path.exists(img_path3):
        story.append(Image(img_path3, width=CONTENT_W*0.78, height=CONTENT_W*0.78*0.62))
        story.append(Paragraph("图3：转人工触发率优化前后对比", ST['Caption']))
    story.append(Spacer(1, 6))
    story.append(Paragraph("优化全过程", ST['H2']))
    story.append(ListFlowable([
        ListItem(Paragraph("<b>① 发现问题</b>：评测发现 D 类（转人工场景）触发率仅 62%，D04/D05/D06（「转人工」「找人工客服」）未触发。", ST['Bullet'])),
        ListItem(Paragraph("<b>② 根因分析</b>：模型在「确认转人工原因」（想先问清楚），而非立即转。但用户<b>明确要求转人工时，追问反而是糟糕体验</b>。", ST['Bullet'])),
        ListItem(Paragraph("<b>③ 实施优化</b>：在 config.py 的 HUMAN_KEYWORDS 增加「转人工/找人工/人工客服/找人/真人」等主动请求类关键词。", ST['Bullet'])),
        ListItem(Paragraph("<b>④ 验证效果</b>：重跑评测，<b>D类触发率从 62% → 100%</b>，工具选择准确率从 74% → 80%。", ST['Bullet'])),
    ], bulletType='bullet', start='•'))
    story.append(Spacer(1, 8))
    story.append(Paragraph("产品思考", ST['H3']))
    story.append(Paragraph(
        "评测的价值不是打分，而是<b>定位可优化点</b>。这次优化直接对应用户体验——"
        "「用户明确要转人工，就该立刻转，不该再追问」。这正是岗位JD「从评测中提炼优化点」的真实落地。",
        ST['Body']))
    story.append(PageBreak())

    # ========== P13 深度案例3 ==========
    story.append(section_header("12", "深度案例三：金额拦截与多意图处理"))
    story.append(Paragraph("安全边界：金额超限自动转人工", ST['H2']))
    story.append(Paragraph(
        "用户：「帮我把 A100004 退了」<br/>"
        "Agent 行为：① 调 query_order_status 查到该订单金额 ¥3990；"
        "② 判断超过 500 元阈值；③ 自动调 escalate_to_human 转人工确认；④ 告知用户已转接。<br/>"
        "<b>产品价值</b>：高金额退货涉及用户财产安全，强制人工确认是「知边界」的体现，避免AI越权操作。",
        ST['Body']))
    story.append(Spacer(1, 8))
    story.append(Paragraph("多意图处理：一句话调两个工具", ST['H2']))
    story.append(Paragraph(
        "用户：「我的索尼耳机订单 A100001 什么时候到，顺便问下退货政策」<br/>"
        "Agent 行为：① 识别出两个意图（查物流 + 查政策）；② <b>并行调用</b> query_order_status 和 query_return_policy；"
        "③ 整合两个结果生成完整回复。<br/>"
        "<b>产品价值</b>：真实用户的诉求往往是复合的，Agent 能在一次对话中处理多意图，体验远超只能单轮问答的机器人。",
        ST['Body']))
    story.append(Spacer(1, 8))
    story.append(info_card("案例总结",
        "这两个案例分别体现了 Agent 的<b>安全性</b>（知边界）和<b>智能性</b>（懂意图），"
        "是单纯 RAG 无法实现的——这也是本项目选择 RAG+Agent 架构的核心依据。"))
    story.append(PageBreak())

    # ========== P14 原型与界面 ==========
    story.append(section_header("13", "产品原型与界面"))
    story.append(Paragraph("Web 界面（Gradio 实现）", ST['H2']))
    story.append(Paragraph(
        "采用 Gradio 快速搭建可交互的聊天界面，支持多轮对话、快捷问题、转人工提示。"
        "面试时可现场演示，或通过录屏展示。", ST['Body']))
    story.append(Spacer(1, 6))
    story.append(Paragraph("主要功能模块", ST['H2']))
    story.append(data_table(
        ["模块", "功能", "设计要点"],
        [
            ["对话区", "多轮对话、上下文记忆", "流式输出、转人工高亮提示"],
            ["快捷问题", "预置典型问题按钮", "引导用户、降低使用门槛"],
            ["订单参考表", "展示测试订单号", "便于演示各类场景"],
            ["系统提示", "工具调用、转人工标识", "让用户感知AI在「做事」"],
        ],
        col_ratios=[0.20, 0.40, 0.40]
    ))
    story.append(Spacer(1, 10))
    story.append(Paragraph("演示话术（面试用）", ST['H3']))
    story.append(Paragraph(
        "「我现场演示三个场景：查物流（调用工具）、问退货政策（RAG检索）、"
        "投诉转人工（情绪识别）。大家可以看到 AI 不是在背话术，而是真的在查数据库、办业务。」",
        ST['Body']))
    story.append(PageBreak())

    # ========== P15 评测方法可复用性 ==========
    story.append(section_header("14", "方法论：可复用的评测体系"))
    story.append(Paragraph("这套评测方法的通用性", ST['H2']))
    story.append(Paragraph(
        "我设计的评测体系不局限于电商客服，而是一套<b>可复用的 AI 产品评测方法论</b>，"
        "可迁移到任何「大模型+工具」的应用场景：", ST['Body']))
    story.append(Spacer(1, 6))
    story.append(data_table(
        ["评测步骤", "具体动作", "产出物"],
        [
            ["1. 定义维度", "拆解业务，确定评测维度（知识/工具/安全/性能）", "评测维度表"],
            ["2. 构建题集", "按场景覆盖度设计测试题，标注期望行为", "评测数据集(JSON)"],
            ["3. 制定Rubric", "为每个维度定义1-5分评分标准", "评分Rubric文档"],
            ["4. 跑评测", "自动+人工结合，记录工具调用与延迟", "评测结果(CSV)"],
            ["5. 分析优化", "定位失败case，分析根因，实施优化", "优化方案+对比图"],
            ["6. 验证闭环", "重跑评测，对比优化前后数据", "优化效果报告"],
        ],
        col_ratios=[0.20, 0.48, 0.32]
    ))
    story.append(Spacer(1, 10))
    story.append(info_card("可迁移性",
        "换到金融客服、医疗咨询、教育培训等场景，只需替换知识库与工具定义，"
        "评测框架与流程可<b>直接复用</b>。这体现的是「方法能力」而非「单点经验」。"))
    story.append(PageBreak())

    # ========== P16 项目反思 ==========
    story.append(section_header("15", "项目反思与后续规划"))
    story.append(Paragraph("做得好的地方", ST['H2']))
    story.append(ListFlowable([
        ListItem(Paragraph("<b>数据驱动</b>：所有结论都有评测数据支撑，不靠主观感觉。", ST['Bullet'])),
        ListItem(Paragraph("<b>闭环思维</b>：从评测发现问题到优化验证，形成完整闭环。", ST['Bullet'])),
        ListItem(Paragraph("<b>工程化</b>：用真实数据库+向量库+Agent框架，非玩具级Demo。", ST['Bullet'])),
    ], bulletType='bullet', start='•'))
    story.append(Spacer(1, 6))
    story.append(Paragraph("不足与改进方向", ST['H2']))
    story.append(ListFlowable([
        ListItem(Paragraph("<b>误调用率 20%</b>：E类边界题中仍有误调用，可通过更强的意图分类Prompt优化。", ST['Bullet'])),
        ListItem(Paragraph("<b>延迟较高</b>：可引入流式输出与工具并行调用降低用户感知延迟。", ST['Bullet'])),
        ListItem(Paragraph("<b>评测样本</b>：50题偏小，后续可扩充至200+并引入LLM-as-Judge自动化评分。", ST['Bullet'])),
        ListItem(Paragraph("<b>多轮对话</b>：当前评测以单轮为主，可补充多轮上下文场景评测。", ST['Bullet'])),
    ], bulletType='bullet', start='•'))
    story.append(Spacer(1, 8))
    story.append(Paragraph("我学到了什么", ST['H2']))
    story.append(Paragraph(
        "这个项目让我深刻理解了「AI 产品经理不是画原型的人，而是<b>用数据和逻辑定义AI能力边界</b>的人」。"
        "技术会迭代，但「定义问题—设计方案—评测验证—迭代优化」的产品方法论是可持续的。",
        ST['Body']))
    story.append(PageBreak())

    # ========== P17 联系方式 ==========
    story.append(section_header("16", "联系方式"))
    story.append(Spacer(1, 30*mm))
    contact = Table([
        [Paragraph("<b>姓名</b>", ST['H3']), Paragraph("冉航", ST['Body'])],
        [Paragraph("<b>目标岗位</b>", ST['H3']), Paragraph("京东科技 · AI产品经理实习生", ST['Body'])],
        [Paragraph("<b>项目演示</b>", ST['H3']), Paragraph("Web界面可现场演示 / 录屏可提供", ST['Body'])],
        [Paragraph("<b>技术栈</b>", ST['H3']), Paragraph("LangChain · Chroma · DeepSeek · SQLite · Gradio", ST['Body'])],
        [Paragraph("<b>代码与数据</b>", ST['H3']), Paragraph("可提供完整项目源码、评测集、评测结果", ST['Body'])],
    ], colWidths=[35*mm, CONTENT_W-35*mm])
    contact.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ('LINEBELOW', (0,0), (-1,-2), 0.3, BORDER),
    ]))
    story.append(contact)
    story.append(Spacer(1, 20*mm))
    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT, spaceBefore=10, spaceAfter=10))
    story.append(Paragraph(
        "感谢您花时间阅读我的作品集。<br/>"
        "期待有机会和团队一起，把大模型在垂直场景真正做深做透。",
        ParagraphStyle('thanks', fontName=FONT_REG, fontSize=12, leading=20,
                       textColor=TEXT_MUTED, alignment=TA_CENTER, wordWrap='CJK')))

    return story


# ============ 生成 ============
def main():
    output = os.path.join(os.path.dirname(__file__), "智答-电商售后智能客服-AI产品经理作品集.pdf")
    doc = SimpleDocTemplate(
        output, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=18*mm, bottomMargin=15*mm,
        title="智答 - 电商售后智能客服 AI产品经理作品集",
        author="冉航", subject="AI产品经理作品集", creator="Z.ai"
    )
    story = build_story()
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    size_kb = os.path.getsize(output) / 1024
    print(f"✅ 作品集生成完成：{output}")
    print(f"   文件大小：{size_kb:.0f} KB")

if __name__ == "__main__":
    main()
