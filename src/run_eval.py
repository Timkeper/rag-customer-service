"""
三组对比评测脚本（半工程化版）
功能：
  1. 用三种模式（baseline / rag / agent）分别跑50题评测集
  2. 记录回复内容、调用的工具、响应延迟
  3. 自动计算工具选择准确率、参数准确率
  4. 生成CSV供后续人工打分

用法：
  python run_eval.py baseline   # 跑裸模型
  python run_eval.py rag        # 跑纯RAG
  python run_eval.py agent      # 跑RAG+Agent（完整版）
  python run_eval.py all        # 三个都跑（推荐，约30-40分钟）
"""

import sys
import json
import time
import csv
from datetime import datetime
from pathlib import Path

# 从agent.py导入三种模式
from agent import BaselineChat, RAGChat, CustomerServiceAgent
from config import EVAL_DATASET_PATH, EVAL_RESULTS_DIR


def load_dataset():
    """加载评测集"""
    with open(EVAL_DATASET_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def run_single_version(version: str, dataset: dict):
    """跑单个版本的50题评测"""
    print(f"\n{'='*60}")
    print(f"开始评测：{version.upper()} 版")
    print(f"{'='*60}")

    # 初始化对应模式
    print("初始化模型...")
    if version == "baseline":
        chatbot = BaselineChat()
    elif version == "rag":
        chatbot = RAGChat()
    elif version == "agent":
        chatbot = CustomerServiceAgent()
    else:
        raise ValueError(f"未知版本：{version}，可选 baseline/rag/agent")

    results = []
    questions = dataset["questions"]
    total = len(questions)

    for i, q in enumerate(questions, 1):
        print(f"\n[{i}/{total}] {q['id']} - {q['question'][:30]}...")

        # 调模型，记录耗时
        start = time.time()
        try:
            result = chatbot.chat(q["question"])
            reply = result.get("reply", "")
            tool_used = result.get("tool_used", "unknown")
            # 新版agent返回完整工具列表，用它做更准确判断
            all_tools = result.get("tools_used", [tool_used] if tool_used != "none" else [])
            escalated = result.get("escalated", False)
        except Exception as e:
            reply = f"[ERROR] {e}"
            tool_used = "error"
            all_tools = []
            escalated = False
        latency_ms = int((time.time() - start) * 1000)

        # 自动判断工具选择准确率
        # 逻辑：期望工具是否在实际调用的工具列表里
        tool_correct = ""
        if version == "agent":
            expected = q["expected_tool"]
            if expected == "none":
                # 不该调工具时，调了就算错（除非合理转人工）
                tool_correct = 1 if len(all_tools) == 0 or all_tools == ["escalate_to_human"] else 0
            else:
                # 该调 expected 工具时，检查实际是否调了
                tool_correct = 1 if expected in all_tools else 0

        # 记录
        results.append({
            "id": q["id"],
            "category": q["category"],
            "question": q["question"],
            "expected_tool": q["expected_tool"],
            "actual_tool": tool_used,
            "all_tools": "+".join(all_tools) if all_tools else "none",  # 实际调用的所有工具
            "tool_correct": tool_correct,
            "response": reply[:500],  # 截断防止CSV过大
            "latency_ms": latency_ms,
            "escalated": escalated,
            # 以下需要人工填
            "accuracy": "",
            "relevance": "",
            "completeness": "",
            "safety": "",
            "task_completed": "",
            "param_correct": "",
            "notes": ""
        })

        # 预览回复
        print(f"  → {reply[:80]}...")
        print(f"  耗时：{latency_ms}ms")

        time.sleep(0.3)  # 避免API限流

    # 保存CSV
    Path(EVAL_RESULTS_DIR).mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    out_csv = f"{EVAL_RESULTS_DIR}/eval_{version}_{timestamp}.csv"

    with open(out_csv, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)

    print(f"\n✅ {version.upper()}版评测完成！")
    print(f"📄 结果保存：{out_csv}")

    # 打印摘要
    avg_latency = sum(r["latency_ms"] for r in results) / len(results)
    print(f"📊 平均延迟：{avg_latency:.0f}ms")

    return out_csv


def main():
    if len(sys.argv) < 2:
        print("用法：")
        print("  python run_eval.py baseline  # 跑裸模型")
        print("  python run_eval.py rag       # 跑纯RAG")
        print("  python run_eval.py agent     # 跑RAG+Agent")
        print("  python run_eval.py all       # 三个都跑（推荐）")
        sys.exit(1)

    target = sys.argv[1]
    dataset = load_dataset()

    csvs = []
    if target == "all":
        for v in ["baseline", "rag", "agent"]:
            csvs.append(run_single_version(v, dataset))
    else:
        csvs.append(run_single_version(target, dataset))

    print(f"\n{'='*60}")
    print("🎉 全部完成！下一步：")
    print("1. 打开CSV，手动填写 accuracy/relevance/completeness/safety（1-5分）")
    print("2. 运行 python analyze_results.py 生成对比图表")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
