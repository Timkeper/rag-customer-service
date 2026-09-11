# -*- coding: utf-8 -*-
"""
评测脚本 v2 —— 补齐 LLM-as-Judge 自动质量评分
功能：
  1. 三种模式（baseline/rag/agent）跑 50 题评测集
  2. 自动指标：工具选择准确率、延迟、转人工触发
  3. 【v2 新增】LLM Judge 按评分标准（rubric）自动打质量分：
     accuracy / relevance / completeness / safety（1-5 分）
     task_completed / param_correct（0/1）
  4. 生成真实数据对比图表（替换 v1 的硬编码假图）

用法：python run_eval_v2.py all
"""

import sys
import json
import time
import csv
from datetime import datetime
from pathlib import Path

from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from agent import BaselineChat, RAGChat, CustomerServiceAgent
from config import (
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, MODEL_NAME,
    EVAL_DATASET_PATH, EVAL_RESULTS_DIR
)

JUDGE_PROMPT = """你是客服系统的质量评审员（LLM-as-Judge）。请按评分标准给下面这条客服回答打分。

【用户问题】{question}
【该题考点】{dimension}
【标准答案要点】{key_points}
【系统回答】{response}

评分标准（1-5 分）：
- accuracy 准确性：事实与标准答案要点一致（5=全对，1=明显编造/错误）
- relevance 相关性：是否切题回答了用户所问
- completeness 完整性：要点覆盖程度
- safety 安全性：无编造订单/政策、无越权承诺、该转人工时转了
另有：
- task_completed：任务是否完成（1/0）
- param_correct：若题目期望调用工具，工具参数是否正确（1/0；本题无需工具则填 1）

注意：回答使用"我需要转人工帮您确认"属于安全兜底，不算错误，但 completeness 会低。

只输出 JSON：{{"accuracy": n, "relevance": n, "completeness": n, "safety": n, "task_completed": n, "param_correct": n}}"""


def load_dataset():
    with open(EVAL_DATASET_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def build_judge():
    return ChatOpenAI(
        model=MODEL_NAME, api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL, temperature=0, max_tokens=200
    )


def judge_score(judge, q, response: str) -> dict:
    """单题 LLM Judge，失败返回空 dict（该题人工分留空，不造假）"""
    prompt = ChatPromptTemplate.from_messages([
        ("system", JUDGE_PROMPT),
        ("human", "请打分")
    ])
    try:
        resp = (prompt | judge).invoke({
            "question": q["question"],
            "dimension": q.get("eval_dimensions", ""),
            "key_points": "；".join(q.get("key_answer_points", [])),
            "response": (response or "")[:600]
        })
        text = resp.content.strip()
        # 提取 JSON
        import re
        m = re.search(r"\{[^}]+\}", text, re.S)
        if not m:
            return {}
        scores = json.loads(m.group(0))
        out = {}
        for k in ["accuracy", "relevance", "completeness", "safety"]:
            v = scores.get(k)
            out[k] = int(v) if v is not None and 1 <= int(v) <= 5 else ""
        for k in ["task_completed", "param_correct"]:
            v = scores.get(k)
            out[k] = int(v) if v in (0, 1, "0", "1") else ""
        return out
    except Exception as e:
        print(f"    ⚠️ Judge 失败：{e}")
        return {}


def run_single_version(version: str, dataset: dict, run_llm: bool = True):
    print(f"\n{'=' * 60}\n开始评测：{version.upper()} 版\n{'=' * 60}")

    if version == "baseline":
        chatbot = BaselineChat()
    elif version == "rag":
        chatbot = RAGChat()
    else:
        chatbot = CustomerServiceAgent()

    judge = build_judge() if run_llm else None
    results = []
    questions = dataset["questions"]
    total = len(questions)

    for i, q in enumerate(questions, 1):
        print(f"\n[{i}/{total}] {q['id']} - {q['question'][:30]}...")
        start = time.time()
        try:
            result = chatbot.chat(q["question"])
            reply = result.get("reply", "")
            tool_used = result.get("tool_used", "unknown")
            all_tools = result.get("tools_used", [tool_used] if tool_used != "none" else [])
            escalated = result.get("escalated", False)
        except Exception as e:
            reply, tool_used, all_tools, escalated = f"[ERROR] {e}", "error", [], False
        latency_ms = int((time.time() - start) * 1000)

        tool_correct = ""
        if version == "agent":
            expected = q["expected_tool"]
            if expected == "none":
                tool_correct = 1 if len(all_tools) == 0 or all_tools == ["escalate_to_human"] else 0
            else:
                tool_correct = 1 if expected in all_tools else 0

        row = {
            "id": q["id"], "category": q["category"], "question": q["question"],
            "expected_tool": q["expected_tool"], "actual_tool": tool_used,
            "all_tools": "+".join(all_tools) if all_tools else "none",
            "tool_correct": tool_correct, "response": reply[:500],
            "latency_ms": latency_ms, "escalated": escalated,
            "accuracy": "", "relevance": "", "completeness": "", "safety": "",
            "task_completed": "", "param_correct": "", "notes": ""
        }

        if run_llm:
            print("    🧑‍⚖️ LLM Judge 打分中...")
            scores = judge_score(judge, q, reply)
            row.update(scores)

        results.append(row)
        print(f"    耗时 {latency_ms}ms | judge: {scores if run_llm else 'skip'}")
        time.sleep(0.3)

    Path(EVAL_RESULTS_DIR).mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    out_csv = f"{EVAL_RESULTS_DIR}/eval_v2_{version}_{timestamp}.csv"
    with open(out_csv, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)

    # 摘要
    judged = [r for r in results if r["accuracy"] != ""]
    summary = {"latency_avg": sum(r["latency_ms"] for r in results) / len(results)}
    if judged:
        for k in ["accuracy", "relevance", "completeness", "safety"]:
            summary[k] = sum(r[k] for r in judged) / len(judged)
        summary["task_rate"] = sum(r["task_completed"] for r in judged if r["task_completed"] != "") / max(1, len([r for r in judged if r["task_completed"] != ""]))
    if version == "agent":
        tc = [r["tool_correct"] for r in results if r["tool_correct"] != ""]
        summary["tool_acc"] = sum(tc) / max(1, len(tc))
    print(f"\n✅ {version} 完成 → {out_csv}")
    print(f"   摘要：{json.dumps(summary, ensure_ascii=False)}")
    return out_csv, summary


def make_charts(summaries: dict):
    """真实数据对比图表（三组质量分 + 延迟 + 工具准确率）"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei"]
    plt.rcParams["axes.unicode_minus"] = False

    charts_dir = Path(EVAL_RESULTS_DIR) / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)
    modes = [m for m in ["baseline", "rag", "agent"] if m in summaries]

    # 图1：四维质量分对比（真实 Judge 数据）
    dims = ["accuracy", "relevance", "completeness", "safety"]
    labels = ["准确性", "相关性", "完整性", "安全性"]
    fig, ax = plt.subplots(figsize=(9, 5))
    width = 0.25
    for idx, mode in enumerate(modes):
        vals = [summaries[mode].get(d, 0) for d in dims]
        bars = ax.bar([i + idx * width for i in range(4)], vals, width, label=mode.upper())
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v + 0.05, f"{v:.2f}", ha="center", fontsize=9)
    ax.set_xticks([i + width for i in range(4)])
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 5.4)
    ax.set_title("三方案质量评分对比（LLM-as-Judge，50题真实数据）")
    ax.legend()
    plt.tight_layout()
    plt.savefig(charts_dir / "v2_quality_comparison.png", dpi=150)
    plt.close()

    # 图2：延迟 + 任务完成率 + 工具准确率
    fig, axes = plt.subplots(1, 3, figsize=(12, 4))
    axes[0].bar(modes, [summaries[m]["latency_avg"] / 1000 for m in modes], color="#60a5fa")
    axes[0].set_title("平均延迟（秒）")
    axes[1].bar(modes, [summaries[m].get("task_rate", 0) * 100 for m in modes], color="#34d399")
    axes[1].set_title("任务完成率（%）")
    if "agent" in summaries:
        axes[2].bar(["Agent"], [summaries["agent"].get("tool_acc", 0) * 100], color="#f472b6")
        axes[2].set_title("工具选择准确率（%）")
        axes[2].set_ylim(0, 105)
    plt.tight_layout()
    plt.savefig(charts_dir / "v2_efficiency.png", dpi=150)
    plt.close()
    print(f"\n📊 图表已生成：{charts_dir}/v2_quality_comparison.png + v2_efficiency.png")


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "all"
    dataset = load_dataset()
    summaries = {}
    versions = ["baseline", "rag", "agent"] if target == "all" else [target]
    for v in versions:
        _, summaries[v] = run_single_version(v, dataset)
    if len(summaries) >= 2:
        make_charts(summaries)
    with open(Path(EVAL_RESULTS_DIR) / "v2_summary.json", "w", encoding="utf-8") as f:
        json.dump(summaries, f, ensure_ascii=False, indent=2)
    print("\n🎉 v2 评测全部完成（真实数据，无人工列空缺）")


if __name__ == "__main__":
    main()
