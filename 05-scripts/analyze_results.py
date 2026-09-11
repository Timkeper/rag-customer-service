"""
评测结果分析 + 对比图表生成（自动统计版）
功能：
  1. 读取3份CSV（baseline/rag/agent）
  2. 自动统计：工具准确率、转人工触发率、误调用率、延迟
  3. 生成对比图表（柱状图）—— 作品集直接用！

用法：python analyze_results.py
"""

import glob
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

# 中文字体设置（Windows）
plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei"]
plt.rcParams["axes.unicode_minus"] = False

RESULTS_DIR = "./results"
CHARTS_DIR = "./results/charts"
Path(CHARTS_DIR).mkdir(parents=True, exist_ok=True)


def get_latest_csv(prefix):
    """获取某组最新的CSV"""
    files = sorted(glob.glob(f"{RESULTS_DIR}/eval_{prefix}_*.csv"))
    return files[-1] if files else None


def analyze_one(path):
    """分析单份CSV，返回各项指标"""
    df = pd.read_csv(path)

    # 工具选择准确率（仅agent有意义）
    tc = pd.to_numeric(df["tool_correct"], errors="coerce").dropna()
    tool_acc = tc.mean() * 100 if len(tc) > 0 else 0

    # D类转人工触发率（应100%）
    d_df = df[df["category"].str.contains("转人工")]
    d_rate = d_df["escalated"].mean() * 100 if len(d_df) > 0 else 0

    # B/C类工具调用场景的任务完成度（看是否调了正确工具，简化代理指标）
    bc_df = df[df["category"].str.contains("订单物流|退货退款")]
    bc_tool = bc_df["all_tools"].apply(lambda x: x != "none").mean() * 100 if len(bc_df) > 0 else 0

    # E类边界误调用率（越低越好）
    e_df = df[df["category"].str.contains("边界")]
    if len(e_df) > 0:
        e_false = e_df[e_df["all_tools"].str.contains("query_|submit_|check_", na=False)]
        false_invoke = len(e_false) / len(e_df) * 100
    else:
        false_invoke = 0

    # 平均延迟
    latency = df["latency_ms"].mean()

    return {
        "tool_acc": tool_acc,
        "escalation_rate": d_rate,
        "business_handling": bc_tool,
        "false_invoke_rate": false_invoke,
        "latency": latency,
    }


def plot_comparison():
    """生成对比图表"""
    paths = {
        "Baseline\n裸模型": get_latest_csv("baseline"),
        "RAG\n纯检索": get_latest_csv("rag"),
        "Agent\n完整版": get_latest_csv("agent"),
    }

    print("\n分析中...")
    data = {}
    for name, path in paths.items():
        if path is None:
            print(f"  ⚠️ {name}: 找不到CSV，跳过")
            continue
        print(f"  ✅ {name.strip()}: {path}")
        data[name] = analyze_one(path)

    if len(data) < 2:
        print("\n⚠️ 至少需要2组数据才能对比")
        return

    labels = list(data.keys())
    colors = ["#FF6B6B", "#4ECDC4", "#45B7D1"]

    # === 图1：核心能力对比（4个子图）===
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    metrics_config = [
        ("escalation_rate", "D类转人工触发率（%）\n投诉/要求转人工时正确转接", 115),
        ("business_handling", "业务办理能力（%）\n能否调用工具办退货/查物流", 115),
        ("tool_acc", "工具选择准确率（%）\n调对工具的比例", 115),
        ("false_invoke_rate", "误调用率（%）\n不该调工具时调了（越低越好）", 25),
    ]

    for idx, (metric, title, ylim) in enumerate(metrics_config):
        ax = axes[idx // 2][idx % 2]
        vals = [data[k][metric] for k in labels]
        bars = ax.bar(labels, vals, color=colors[:len(labels)], edgecolor="black", linewidth=0.5)
        ax.set_title(title, fontsize=11, fontweight="bold", pad=10)
        ax.set_ylabel("百分比 (%)")
        ax.set_ylim(0, ylim)
        ax.grid(axis="y", alpha=0.3)
        for bar, val in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + ylim*0.02,
                    f"{val:.0f}%", ha="center", va="bottom", fontsize=12, fontweight="bold")

    fig.suptitle("电商售后智能客服 - 三种方案能力对比", fontsize=15, fontweight="bold", y=1.00)
    plt.tight_layout()
    plt.savefig(f"{CHARTS_DIR}/comparison_metrics.png", dpi=150, bbox_inches="tight")
    print(f"\n✅ 核心指标对比图已保存：{CHARTS_DIR}/comparison_metrics.png")

    # === 图2：延迟对比 ===
    fig2, ax2 = plt.subplots(figsize=(8, 5))
    latencies = [data[k]["latency"] for k in labels]
    bars2 = ax2.bar(labels, latencies, color=colors[:len(labels)], edgecolor="black", linewidth=0.5)
    ax2.set_title("平均响应延迟对比（越低越好）", fontsize=13, fontweight="bold", pad=10)
    ax2.set_ylabel("延迟 (毫秒)")
    ax2.grid(axis="y", alpha=0.3)
    for bar, val in zip(bars2, latencies):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 100,
                 f"{val:.0f}ms", ha="center", va="bottom", fontsize=12, fontweight="bold")
    plt.tight_layout()
    plt.savefig(f"{CHARTS_DIR}/comparison_latency.png", dpi=150, bbox_inches="tight")
    print(f"✅ 延迟对比图已保存：{CHARTS_DIR}/comparison_latency.png")

    # === 图3：版本演进对比（真实数据：v1 七月评测 vs v2 当前评测，D类转人工触发率）===
    # v2 变化：多轮会话/鉴权/工单化转人工——用两次真实评测的 D 类触发率对比，不再使用估计值
    try:
        import glob as _glob
        v1_files = _glob.glob(str(RESULTS_DIR / "eval_agent_20260729_1050.csv"))
        v2_files = sorted(_glob.glob(str(RESULTS_DIR / "eval_v2_agent_*.csv")))
        if v1_files and v2_files:
            v1_df = pd.read_csv(v1_files[0])
            v2_df = pd.read_csv(v2_files[-1])
            v1_d = v1_df[v1_df["category"].astype(str).str.startswith("D")]["escalated"].mean() * 100
            v2_d = v2_df[v2_df["category"].astype(str).str.startswith("D")]["escalated"].mean() * 100
            fig3, ax3 = plt.subplots(figsize=(8, 5))
            opt_labels = [f"v1 版\n(2026-07-29 评测)", f"v2 版\n(当前评测)"]
            opt_vals = [round(v1_d, 1), round(v2_d, 1)]
            bars3 = ax3.bar(opt_labels, opt_vals, color=["#FFA07A", "#90EE90"], edgecolor="black", linewidth=0.5)
            ax3.set_title("版本演进：D类「应转人工」触发率\n（v1→v2：转人工全面工单化+确认门，真实评测数据）",
                          fontsize=13, fontweight="bold", pad=10)
            ax3.set_ylabel("D类转人工触发率 (%)")
            ax3.set_ylim(0, 120)
            ax3.grid(axis="y", alpha=0.3)
            for bar, val in zip(bars3, opt_vals):
                ax3.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2,
                         f"{val}%", ha="center", va="bottom", fontsize=14, fontweight="bold")
            delta = v2_d - v1_d
            ax3.annotate("", xy=(1, v2_d), xytext=(0, v1_d),
                         arrowprops=dict(arrowstyle="->", color="red", lw=2))
            ax3.text(0.5, max(v1_d, v2_d) + 12, f"{delta:+.1f}%", color="red", fontsize=16,
                     fontweight="bold", ha="center")
            plt.tight_layout()
            plt.savefig(f"{CHARTS_DIR}/optimization_case.png", dpi=150, bbox_inches="tight")
            print(f"✅ 版本演进图已保存（真实数据：v1={v1_d:.1f}% → v2={v2_d:.1f}%）：{CHARTS_DIR}/optimization_case.png")
        else:
            print("⚠️ 跳过版本演进图（需要 eval_agent_20260729 与 eval_v2_agent 两份CSV）")
    except Exception as e:
        print(f"⚠️ 版本演进图生成失败：{e}")

    # === 打印汇总表 ===
    print(f"\n{'='*65}")
    print("📊 最终数据汇总表（可直接放作品集）")
    print(f"{'='*65}")
    header = f"{'指标':<16}"
    for k in labels:
        header += f"{k.replace(chr(10),' '):>14}"
    print(header)
    print("-" * 65)
    for metric, name_cn in [
        ("escalation_rate", "转人工触发率"),
        ("business_handling", "业务办理能力"),
        ("tool_acc", "工具准确率"),
        ("false_invoke_rate", "误调用率"),
        ("latency", "延迟(ms)"),
    ]:
        row = f"{name_cn:<14}"
        for k in labels:
            v = data[k][metric]
            row += f"{v:>14.0f}"
        print(row)
    print(f"{'='*65}")


if __name__ == "__main__":
    plot_comparison()
    print(f"\n🎉 所有图表已生成在 {CHARTS_DIR}/，直接拖进作品集！")
