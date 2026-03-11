import json
import re
import httpx

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen3:14b"
REPORT_TIMEOUT = 120  # 报告生成超时

ALL_CATEGORIES = "餐饮、交通、购物、娱乐、居住、医疗、教育、通讯、工资、理财、红包、报销、其他收入、其他"
ALL_CATS_LIST = ALL_CATEGORIES.split("、")


async def classify(note: str) -> str:
    """调用 ollama qwen3:14b 识别消费分类"""
    content = (
        f"根据消费描述返回一个分类名。"
        f"可选分类：{ALL_CATEGORIES}。"
        f"描述：{note}。只回答分类名："
    )
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(OLLAMA_URL, json={
                "model": MODEL,
                "messages": [{"role": "user", "content": content}],
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 500},
            })
            resp.raise_for_status()
            raw = resp.json()["message"]["content"]
            # 去掉 <think>...</think>
            raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
            result = raw.strip().strip("。.，,")
            if result in ALL_CATS_LIST:
                return result
            for cat in ALL_CATS_LIST:
                if cat in result:
                    return cat
            return "其他"
    except Exception:
        return "其他"


async def generate_report(month: str, income_total: float, expense_total: float,
                          income_cats: list[dict], expense_cats: list[dict],
                          record_count: int) -> str:
    """调用 ollama qwen3:14b 生成月度收支报告和理财建议"""
    # 构建支出明细
    expense_detail = "\n".join(
        f"  - {c['category']}：{c['amount']}元"
        for c in expense_cats
    ) or "  无支出记录"

    income_detail = "\n".join(
        f"  - {c['category']}：{c['amount']}元"
        for c in income_cats
    ) or "  无收入记录"

    balance = income_total - expense_total
    savings_rate = (balance / income_total * 100) if income_total > 0 else 0

    prompt = f"""你是一位专业的个人财务顾问。请根据以下{month}月度收支数据，生成一份简洁实用的财务报告。

## 月度数据
- 月份：{month}
- 总收入：{income_total:.2f}元
- 总支出：{expense_total:.2f}元
- 结余：{balance:.2f}元
- 储蓄率：{savings_rate:.1f}%
- 交易笔数：{record_count}笔

支出明细：
{expense_detail}

收入明细：
{income_detail}

## 要求
请用中文输出，包含以下三个部分，每部分用标题分隔：

### 收支概况
简要总结本月收支情况（2-3句话）

### 消费分析
分析支出结构，指出占比最大的类别，是否有异常消费（3-4句话）

### 理财建议
给出 2-3 条具体、可操作的理财建议（针对该用户的实际数据）

注意：语言简洁友好，不要啰嗦，不要用表格，直接给出分析和建议。"""

    try:
        async with httpx.AsyncClient(timeout=REPORT_TIMEOUT) as client:
            resp = await client.post(OLLAMA_URL, json={
                "model": MODEL,
                "messages": [{"role": "user", "content": prompt + " /no_think"}],
                "stream": False,
                "options": {"temperature": 0.7, "num_predict": 2000},
            })
            resp.raise_for_status()
            raw = resp.json()["message"]["content"]
            # 去掉 <think>...</think>
            raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
            return raw.strip()
    except Exception as e:
        return f"报告生成失败：{str(e)}"
