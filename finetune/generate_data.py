#!/usr/bin/env python3
"""
用 qwen3:14b 批量生成 BookKeeper 微调训练数据
300 条月度报告 + 200 条消费画像 = 500 条 ChatML JSONL
支持断点续传（追加写入）
"""

import json
import os
import random
import time

import httpx
import yaml

# ============================================================
# 配置
# ============================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(SCRIPT_DIR, "config.yaml"), "r") as f:
    cfg = yaml.safe_load(f)

OLLAMA_URL = cfg["ollama"]["url"] + "/api/chat"
TEACHER_MODEL = cfg["ollama"]["teacher_model"]
TIMEOUT = cfg["ollama"]["timeout"]
DATA_FILE = os.path.join(SCRIPT_DIR, cfg["data"]["output_file"])
NUM_REPORTS = cfg["data"]["num_reports"]
NUM_PROFILES = cfg["data"]["num_profiles"]

CATEGORIES = ["餐饮", "交通", "购物", "娱乐", "居住", "医疗", "教育", "通讯", "投资"]
INCOME_CATS = ["工资", "理财", "红包", "报销", "其他收入"]
MONTHS = [f"2025-{m:02d}" for m in range(1, 13)] + [f"2026-{m:02d}" for m in range(1, 4)]


def call_llm(prompt: str, temperature: float = 0.7, max_tokens: int = 800) -> str | None:
    """同步调用 ollama，返回清理后文本"""
    import re
    with httpx.Client(timeout=TIMEOUT) as client:
        resp = client.post(OLLAMA_URL, json={
            "model": TEACHER_MODEL,
            "messages": [{"role": "user", "content": prompt + " /no_think"}],
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        })
        resp.raise_for_status()
        raw = resp.json()["message"]["content"]
        return re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()


def validate_output(text: str) -> bool:
    """质量过滤：必须包含三个 ### 标题，100-500 字"""
    if not text:
        return False
    heading_count = text.count("###")
    char_count = len(text)
    return heading_count >= 3 and 100 <= char_count <= 2000


def count_existing(data_file: str) -> dict[str, int]:
    """统计已生成的数据条数"""
    counts = {"report": 0, "profile": 0}
    if not os.path.exists(data_file):
        return counts
    with open(data_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            task_type = rec.get("task_type", "report")
            if task_type in counts:
                counts[task_type] += 1
    return counts


# ============================================================
# 场景生成器
# ============================================================

def random_report_scenario() -> dict:
    """随机生成月度收支场景"""
    month = random.choice(MONTHS)
    income_total = random.randint(3000, 50000)
    expense_ratio = random.uniform(0.3, 1.2)
    expense_total = round(income_total * expense_ratio, 2)
    balance = round(income_total - expense_total, 2)
    rate = round(balance / income_total * 100, 1) if income_total > 0 else 0
    record_count = random.randint(15, 120)

    # 随机 3-8 个支出分类
    num_cats = random.randint(3, 8)
    cats = random.sample(CATEGORIES, num_cats)
    # 随机分配支出金额
    weights = [random.random() for _ in cats]
    total_w = sum(weights)
    expense_cats = []
    for cat, w in zip(cats, weights):
        amt = round(expense_total * w / total_w, 2)
        expense_cats.append({"category": cat, "amount": amt})
    expense_cats.sort(key=lambda x: -x["amount"])

    # 随机 1-3 个收入分类
    num_inc = random.randint(1, 3)
    inc_cats_names = random.sample(INCOME_CATS, num_inc)
    inc_weights = [random.random() for _ in inc_cats_names]
    inc_total_w = sum(inc_weights)
    income_cats = []
    for cat, w in zip(inc_cats_names, inc_weights):
        amt = round(income_total * w / inc_total_w, 2)
        income_cats.append({"category": cat, "amount": amt})

    return {
        "month": month,
        "income_total": income_total,
        "expense_total": expense_total,
        "balance": balance,
        "rate": rate,
        "record_count": record_count,
        "expense_cats": expense_cats,
        "income_cats": income_cats,
    }


def build_report_prompt(scenario: dict) -> str:
    """构建与 ai.py generate_report 一致的 prompt"""
    s = scenario
    expense_detail = "\n".join(
        f"  - {c['category']}：{c['amount']}元" for c in s["expense_cats"]
    ) or "  无"
    income_detail = "\n".join(
        f"  - {c['category']}：{c['amount']}元" for c in s["income_cats"]
    ) or "  无"

    return f"""你是专业的个人财务顾问。根据{s['month']}收支数据生成简洁报告。

数据：收入{s['income_total']:.2f}元，支出{s['expense_total']:.2f}元，结余{s['balance']:.2f}元，储蓄率{s['rate']:.1f}%，共{s['record_count']}笔
支出明细：
{expense_detail}
收入明细：
{income_detail}

请输出三部分（用 ### 标题）：
### 收支概况（2句话总结）
### 消费分析（分析支出结构，指出大头和异常，3句话）
### 理财建议（2-3条具体可操作的建议）
语言简洁友好，不用表格。"""


def random_profile_scenario() -> dict:
    """随机生成多月消费数据用于画像"""
    num_months = random.randint(3, 6)
    months_data = []
    start_month = random.randint(1, 10)
    for i in range(num_months):
        m = start_month + i
        year = 2025 if m <= 12 else 2026
        month_str = f"{year}-{((m - 1) % 12 + 1):02d}"
        income = random.randint(3000, 50000)
        expense_ratio = random.uniform(0.3, 1.2)
        expense = round(income * expense_ratio, 2)
        num_cats = random.randint(3, 6)
        cats = random.sample(CATEGORIES, num_cats)
        weights = [random.random() for _ in cats]
        total_w = sum(weights)
        expense_cats = [
            {"category": c, "amount": round(expense * w / total_w, 2)}
            for c, w in zip(cats, weights)
        ]
        expense_cats.sort(key=lambda x: -x["amount"])
        months_data.append({
            "month": month_str,
            "income": income,
            "expense": expense,
            "expense_cats": expense_cats,
        })
    return {"months_data": months_data}


def build_profile_prompt(scenario: dict) -> str:
    """构建与 ai.py spending_profile 一致的 prompt"""
    summary = ""
    for m in scenario["months_data"]:
        cats_str = "、".join(
            f"{c['category']}{c['amount']}元" for c in m["expense_cats"][:5]
        )
        summary += f"{m['month']}：收入{m['income']:.0f}元，支出{m['expense']:.0f}元，主要支出：{cats_str}\n"

    return f"""你是消费行为分析师。根据用户近几个月的收支数据，生成消费习惯画像。

历史数据：
{summary}

请输出（用 ### 标题分隔）：

### 消费画像
用 2-3 个标签描述用户（如"外卖依赖型""精打细算型""月光族"等），并解释为什么

### 消费规律
指出 2-3 个消费习惯/规律（如固定支出占比、消费高峰期等）

### 优化建议
给 2-3 条针对性的建议

语言简洁有趣，像朋友聊天一样。"""


# ============================================================
# 主逻辑
# ============================================================

def generate_all():
    os.makedirs(os.path.dirname(DATA_FILE) or ".", exist_ok=True)
    existing = count_existing(DATA_FILE)
    reports_done = existing["report"]
    profiles_done = existing["profile"]

    print(f"已有数据：报告 {reports_done}/{NUM_REPORTS}，画像 {profiles_done}/{NUM_PROFILES}")

    total_generated = reports_done + profiles_done
    total_target = NUM_REPORTS + NUM_PROFILES
    failed = 0

    with open(DATA_FILE, "a", encoding="utf-8") as fout:
        # 生成报告
        while reports_done < NUM_REPORTS:
            idx = reports_done + 1
            scenario = random_report_scenario()
            prompt = build_report_prompt(scenario)
            print(f"[报告 {idx}/{NUM_REPORTS}] {scenario['month']}...", end=" ", flush=True)

            try:
                output = call_llm(prompt, temperature=0.8, max_tokens=800)
                if not validate_output(output):
                    print("✗ 格式不合格，跳过")
                    failed += 1
                    continue
                record = {
                    "task_type": "report",
                    "messages": [
                        {"role": "user", "content": prompt},
                        {"role": "assistant", "content": output},
                    ]
                }
                fout.write(json.dumps(record, ensure_ascii=False) + "\n")
                fout.flush()
                reports_done += 1
                total_generated += 1
                print(f"✓ ({len(output)}字)")
            except Exception as e:
                print(f"✗ 错误: {e}")
                failed += 1
                time.sleep(2)

        # 生成画像
        while profiles_done < NUM_PROFILES:
            idx = profiles_done + 1
            scenario = random_profile_scenario()
            prompt = build_profile_prompt(scenario)
            num_months = len(scenario["months_data"])
            print(f"[画像 {idx}/{NUM_PROFILES}] {num_months}个月...", end=" ", flush=True)

            try:
                output = call_llm(prompt, temperature=0.8, max_tokens=800)
                if not validate_output(output):
                    print("✗ 格式不合格，跳过")
                    failed += 1
                    continue
                record = {
                    "task_type": "profile",
                    "messages": [
                        {"role": "user", "content": prompt},
                        {"role": "assistant", "content": output},
                    ]
                }
                fout.write(json.dumps(record, ensure_ascii=False) + "\n")
                fout.flush()
                profiles_done += 1
                total_generated += 1
                print(f"✓ ({len(output)}字)")
            except Exception as e:
                print(f"✗ 错误: {e}")
                failed += 1
                time.sleep(2)

    print(f"\n{'=' * 60}")
    print(f"完成！共 {total_generated}/{total_target} 条，失败 {failed} 次")
    print(f"数据文件：{DATA_FILE}")


if __name__ == "__main__":
    generate_all()
