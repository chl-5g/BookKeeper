"""AI 功能模块 — 基于 ollama qwen3:14b"""

import json
import re
from datetime import datetime, timedelta

import httpx

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen3:14b"
TIMEOUT = 120

ALL_CATEGORIES = "餐饮、交通、购物、娱乐、居住、医疗、教育、通讯、投资、工资、理财、红包、报销、其他收入、其他"
ALL_CATS_LIST = ALL_CATEGORIES.split("、")


async def _call_llm(prompt: str, temperature=0.7, max_tokens=2000) -> str:
    """调用 ollama，返回清理后的文本"""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(OLLAMA_URL, json={
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt + " /no_think"}],
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        })
        resp.raise_for_status()
        raw = resp.json()["message"]["content"]
        return re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()


# ============================================================
# 1. 自动分类
# ============================================================

async def classify(note: str) -> str:
    """根据消费描述返回分类名"""
    prompt = (
        f"根据消费描述返回一个分类名。"
        f"可选分类：{ALL_CATEGORIES}。"
        f"描述：{note}。只回答分类名："
    )
    try:
        result = await _call_llm(prompt, temperature=0.1, max_tokens=500)
        result = result.strip("。.，,")
        if result in ALL_CATS_LIST:
            return result
        for cat in ALL_CATS_LIST:
            if cat in result:
                return cat
        return "其他"
    except Exception:
        return "其他"


# ============================================================
# 2. 月度收支报告 + 理财建议
# ============================================================

async def generate_report(month, income_total, expense_total,
                          income_cats, expense_cats, record_count) -> str:
    expense_detail = "\n".join(f"  - {c['category']}：{c['amount']}元" for c in expense_cats) or "  无"
    income_detail = "\n".join(f"  - {c['category']}：{c['amount']}元" for c in income_cats) or "  无"
    balance = income_total - expense_total
    rate = (balance / income_total * 100) if income_total > 0 else 0

    prompt = f"""你是专业的个人财务顾问。根据{month}收支数据生成简洁报告。

数据：收入{income_total:.2f}元，支出{expense_total:.2f}元，结余{balance:.2f}元，储蓄率{rate:.1f}%，共{record_count}笔
支出明细：
{expense_detail}
收入明细：
{income_detail}

请输出三部分（用 ### 标题）：
### 收支概况（2句话总结）
### 消费分析（分析支出结构，指出大头和异常，3句话）
### 理财建议（2-3条具体可操作的建议）
语言简洁友好，不用表格。"""

    try:
        return await _call_llm(prompt)
    except Exception as e:
        return f"报告生成失败：{e}"


# ============================================================
# 3. 智能记账（自然语言解析）
# ============================================================

async def smart_parse(text: str) -> dict:
    """解析自然语言记账，返回 {type, amount, category, note, date} 或 {error}"""
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    prompt = f"""你是记账助手。请从用户输入中提取记账信息，返回 JSON 格式（不要其他内容）。

今天日期：{today}

用户输入："{text}"

返回格式（严格JSON）：
{{"type": "expense或income", "amount": 数字, "category": "分类名", "note": "备注", "date": "YYYY-MM-DD"}}

规则：
- type：默认 expense（支出），明确说收入/工资/奖金等才是 income
- amount：提取数字金额
- category：从 [{ALL_CATEGORIES}] 中选一个最匹配的
- note：原始描述的简短摘要
- date：提到"昨天"用 {yesterday}，"前天"用 {(datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")}，没说日期用 {today}
- 如果无法提取金额，返回 {{"error": "无法识别金额"}}

只返回JSON："""

    try:
        raw = await _call_llm(prompt, temperature=0.1, max_tokens=500)
        # 提取 JSON
        match = re.search(r'\{[^}]+\}', raw)
        if not match:
            return {"error": "AI 无法解析，请检查输入格式"}
        data = json.loads(match.group())
        if "error" in data:
            return data
        # 校验必要字段
        amount = float(data.get("amount", 0))
        if amount <= 0:
            return {"error": "无法识别金额"}
        return {
            "type": data.get("type", "expense"),
            "amount": round(amount, 2),
            "category": data.get("category", "其他"),
            "note": data.get("note", text)[:100],
            "date": data.get("date", today),
        }
    except Exception as e:
        return {"error": f"解析失败：{e}"}


# ============================================================
# 4. 异常消费预警
# ============================================================

def detect_anomalies(current_cats: list[dict], history_cats: list[dict],
                     records: list[dict]) -> list[dict]:
    """纯计算，不调用 AI。返回预警列表 [{type, message}]"""
    alerts = []

    # 4a. 单笔大额检测：超过本月平均的 5 倍
    if records:
        amounts = [r["amount"] for r in records if r["type"] == "expense"]
        if amounts:
            avg = sum(amounts) / len(amounts)
            threshold = max(avg * 5, 500)  # 至少 500 才报
            seen_large = set()
            for r in records:
                if r["type"] == "expense" and r["amount"] >= threshold:
                    key = (r["date"], r["category"], r["amount"])
                    if key in seen_large:
                        continue
                    seen_large.add(key)
                    alerts.append({
                        "type": "large",
                        "message": f"大额支出：{r['date']} {r['category']}「{r.get('note','')}」{r['amount']:.2f}元（均值{avg:.0f}元的{r['amount']/avg:.1f}倍）"
                    })

    # 4b. 分类突增：当月某类别比历史月均高 80%
    if history_cats:
        hist_map = {}
        for h in history_cats:
            cat = h["category"]
            if cat not in hist_map:
                hist_map[cat] = []
            hist_map[cat].append(h["amount"])
        for c in current_cats:
            cat, amt = c["category"], c["amount"]
            if cat in hist_map and len(hist_map[cat]) >= 2:
                hist_avg = sum(hist_map[cat]) / len(hist_map[cat])
                if hist_avg > 0 and amt > hist_avg * 1.8 and amt - hist_avg > 200:
                    alerts.append({
                        "type": "surge",
                        "message": f"「{cat}」本月{amt:.0f}元，比月均{hist_avg:.0f}元高{(amt/hist_avg-1)*100:.0f}%"
                    })

    # 去重（相同 message 只保留一条）
    seen = set()
    unique = []
    for a in alerts:
        if a["message"] not in seen:
            seen.add(a["message"])
            unique.append(a)
    return unique[:5]  # 最多5条


# ============================================================
# 5. 预算助手
# ============================================================

async def budget_advice(month, budget, expense_total, expense_cats,
                        days_passed, days_total) -> str:
    """根据预算和支出进度给建议"""
    remaining = budget - expense_total
    progress = days_passed / days_total if days_total > 0 else 1
    daily_avg = expense_total / days_passed if days_passed > 0 else 0
    projected = daily_avg * days_total
    days_left = days_total - days_passed

    top_cats = "\n".join(f"  - {c['category']}：{c['amount']}元" for c in expense_cats[:5])

    prompt = f"""你是预算管家。根据数据给出简短的预算执行建议（3-4句话）。

{month} 预算：{budget:.0f}元
已支出：{expense_total:.2f}元（剩余{remaining:.2f}元）
时间进度：已过{days_passed}天/{days_total}天，剩{days_left}天
日均消费：{daily_avg:.0f}元，按此速度月底预计支出{projected:.0f}元
{'⚠️ 预计超支！' if projected > budget else '✅ 预计不超支'}
支出大头：
{top_cats}

给出：1)当前进度评价 2)剩余每天可花多少 3)一条具体节省建议
简洁友好，不用标题。"""

    try:
        return await _call_llm(prompt, max_tokens=500)
    except Exception as e:
        return f"建议生成失败：{e}"


# ============================================================
# 6. 账单问答
# ============================================================

async def chat_query(question: str, records_summary: str) -> str:
    """基于收支数据回答用户问题"""
    prompt = f"""你是智小账的 AI 助手。根据用户的收支数据回答问题。

用户的收支数据摘要：
{records_summary}

用户问题：{question}

要求：
- 直接回答问题，简洁明了
- 可以做简单计算（求和、平均、对比等）
- 如果数据不足以回答，说明原因
- 用中文回答"""

    try:
        return await _call_llm(prompt, max_tokens=1000)
    except Exception as e:
        return f"回答失败：{e}"


# ============================================================
# 7. 消费习惯画像
# ============================================================

async def spending_profile(months_data: list[dict]) -> str:
    """分析多月数据，生成消费画像"""
    summary = ""
    for m in months_data:
        cats_str = "、".join(f"{c['category']}{c['amount']}元" for c in m.get("expense_cats", [])[:5])
        summary += f"{m['month']}：收入{m['income']:.0f}元，支出{m['expense']:.0f}元，主要支出：{cats_str}\n"

    prompt = f"""你是消费行为分析师。根据用户近几个月的收支数据，生成消费习惯画像。

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

    try:
        return await _call_llm(prompt)
    except Exception as e:
        return f"画像生成失败：{e}"
