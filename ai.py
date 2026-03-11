"""AI 功能模块 — 基于 ollama qwen3:14b（仅报告和画像调 LLM）"""

import hashlib
import json
import re
from datetime import datetime, timedelta
from collections import defaultdict

import httpx

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen3:4b"
MODEL_FALLBACK = "qwen3:14b"  # 格式不合格时 fallback
TIMEOUT = 120

# 简易内存缓存：key → (result, timestamp)
_cache: dict[str, tuple[str, float]] = {}
_CACHE_TTL = 3600  # 1 小时


def _cache_get(key: str) -> str | None:
    if key in _cache:
        result, ts = _cache[key]
        if datetime.now().timestamp() - ts < _CACHE_TTL:
            return result
        del _cache[key]
    return None


def _cache_set(key: str, value: str):
    _cache[key] = (value, datetime.now().timestamp())

ALL_CATEGORIES = "餐饮、交通、购物、娱乐、居住、医疗、教育、通讯、投资、人情、美容、工资、理财、红包、报销、兼职、奖金、退款、租金收入、生意、补贴、其他"
ALL_CATS_LIST = ALL_CATEGORIES.split("、")


async def _call_llm(prompt: str, temperature=0.7, max_tokens=2000,
                    model: str | None = None) -> str:
    """调用 ollama，返回清理后的文本"""
    use_model = model or MODEL
    # qwen3 会先输出 thinking 再输出 content，需要额外 token 余量
    total_predict = max_tokens + 1500
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(OLLAMA_URL, json={
            "model": use_model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": temperature, "num_predict": total_predict},
        })
        resp.raise_for_status()
        msg = resp.json()["message"]
        raw = msg.get("content", "") or ""
        # 清理 <think> 标签（兼容旧格式）
        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
        return raw


# ============================================================
# 关键词 → 分类映射表（纯规则）
# ============================================================

_KEYWORD_MAP = {
    "餐饮": [
        "餐", "饭", "食", "吃", "外卖", "美团", "饿了么", "肯德基", "麦当劳",
        "星巴克", "奶茶", "咖啡", "火锅", "烧烤", "面包", "蛋糕", "零食",
        "水果", "超市", "菜", "早餐", "午餐", "晚餐", "夜宵", "饮料",
        "便利店", "瑞幸", "海底捞", "必胜客", "下午茶", "甜品", "酒",
        "食堂", "盒马", "叮咚", "买菜", "生鲜",
    ],
    "交通": [
        "打车", "滴滴", "出租", "公交", "地铁", "高铁", "火车", "飞机",
        "机票", "加油", "油费", "停车", "过路费", "高速", "骑行", "共享单车",
        "哈啰", "青桔", "曹操", "首汽", "航班", "车费", "船票",
    ],
    "购物": [
        "淘宝", "京东", "拼多多", "天猫", "购物", "买", "衣服", "鞋",
        "包", "化妆品", "护肤", "日用", "家电", "数码", "手机", "电脑",
        "充电", "耳机", "家具", "装修", "洗衣", "快递", "1688", "唯品会",
        "得物", "闲鱼", "苹果", "小米",
    ],
    "娱乐": [
        "电影", "游戏", "KTV", "唱歌", "旅游", "门票", "景点", "酒店",
        "住宿", "民宿", "演出", "演唱会", "健身", "运动", "球", "游泳",
        "瑜伽", "会员", "VIP", "视频", "音乐", "爱奇艺", "优酷", "腾讯",
        "网易", "B站", "抖音", "直播", "打赏", "Steam",
    ],
    "居住": [
        "房租", "租金", "水费", "电费", "燃气", "物业", "暖气", "宽带",
        "网费", "房贷", "月供", "维修",
    ],
    "医疗": [
        "医院", "药", "看病", "挂号", "体检", "牙", "眼", "保健",
        "门诊", "住院", "手术", "核酸", "疫苗", "中医", "西医",
    ],
    "教育": [
        "学费", "培训", "课程", "书", "教材", "考试", "报名", "辅导",
        "学习", "网课", "驾校", "补习",
    ],
    "通讯": [
        "话费", "流量", "手机费", "宽带", "电话", "短信", "移动", "联通",
        "电信", "充值",
    ],
    "投资": [
        "股票", "基金", "理财产品", "定期", "存款", "证券", "债券",
        "期货", "黄金", "比特币", "加密",
    ],
    "人情": [
        "份子钱", "随礼", "请客", "送礼", "礼金", "红白事", "婚礼",
        "满月", "乔迁", "聚餐", "人情", "礼物", "生日礼",
    ],
    "美容": [
        "理发", "美发", "染发", "烫发", "护肤", "美甲", "美容",
        "化妆", "面膜", "spa", "按摩",
    ],
    "工资": [
        "工资", "薪水", "月薪", "发工资", "薪资",
    ],
    "理财": [
        "利息", "分红", "收益", "回报", "余额宝", "零钱通",
    ],
    "红包": [
        "红包", "转账", "微信红包", "支付宝红包", "压岁钱",
    ],
    "报销": [
        "报销", "差旅", "出差",
    ],
    "兼职": [
        "兼职", "副业", "稿费", "外包", "接单", "私活",
    ],
    "奖金": [
        "奖金", "年终奖", "绩效", "提成", "激励",
    ],
    "退款": [
        "退款", "返现", "退货", "赔付",
    ],
    "租金收入": [
        "房租收入", "租金收入", "出租", "租客", "房东",
    ],
    "生意": [
        "营业", "进账", "货款", "客户付款", "店铺", "摆摊", "卖货",
    ],
    "补贴": [
        "补贴", "津贴", "补助", "福利",
    ],
}


# ============================================================
# 1. 自动分类（纯规则 — 关键词匹配）
# ============================================================

async def classify(note: str) -> str:
    """根据消费描述返回分类名（关键词匹配，不调 LLM）"""
    if not note:
        return "其他"
    note_lower = note.lower()
    # 按匹配长度排序，优先匹配更长的关键词
    best_cat = "其他"
    best_len = 0
    for cat, keywords in _KEYWORD_MAP.items():
        for kw in keywords:
            if kw in note_lower and len(kw) > best_len:
                best_cat = cat
                best_len = len(kw)
    return best_cat


# ============================================================
# 2. 月度收支报告 + 理财建议（调 LLM）
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

    # 缓存：同月同数据不重复生成
    cache_key = f"report:{month}:{income_total}:{expense_total}:{record_count}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    try:
        result = await _call_llm(prompt, max_tokens=800)
        # 格式降级：输出缺 ### 时 fallback 到 14b
        if result.count("###") < 3:
            result = await _call_llm(prompt, max_tokens=800, model=MODEL_FALLBACK)
        _cache_set(cache_key, result)
        return result
    except Exception as e:
        return f"报告生成失败：{e}"


# ============================================================
# 3. 智能记账（纯规则 — 正则解析）
# ============================================================

_INCOME_KEYWORDS = ["工资", "薪水", "收入", "到账", "奖金", "年终奖", "绩效",
                     "红包", "转入", "退款", "返现", "报销", "兼职", "副业",
                     "稿费", "利息", "分红", "补贴", "津贴", "提成", "外包",
                     "租金收入", "出租", "营业", "进账", "货款", "赔付"]

_DATE_PATTERNS = {
    "今天": 0, "今日": 0,
    "昨天": -1, "昨日": -1,
    "前天": -2, "前日": -2,
    "大前天": -3,
}


async def smart_parse(text: str) -> dict:
    """解析自然语言记账（纯正则，不调 LLM）"""
    today = datetime.now()
    today_str = today.strftime("%Y-%m-%d")

    if not text or not text.strip():
        return {"error": "请输入记账内容"}

    text = text.strip()

    # 提取金额
    amount_match = re.search(r'(\d+(?:\.\d{1,2})?)', text)
    if not amount_match:
        return {"error": "无法识别金额"}
    amount = float(amount_match.group(1))
    if amount <= 0:
        return {"error": "金额必须大于0"}

    # 判断收入/支出
    record_type = "expense"
    for kw in _INCOME_KEYWORDS:
        if kw in text:
            record_type = "income"
            break

    # 提取日期
    date_str = today_str
    for keyword, delta in _DATE_PATTERNS.items():
        if keyword in text:
            date_str = (today + timedelta(days=delta)).strftime("%Y-%m-%d")
            break
    # 匹配 MM-DD 或 M月D日
    date_match = re.search(r'(\d{1,2})[月/\-](\d{1,2})[日号]?', text)
    if date_match:
        month = int(date_match.group(1))
        day = int(date_match.group(2))
        if 1 <= month <= 12 and 1 <= day <= 31:
            date_str = f"{today.year}-{month:02d}-{day:02d}"

    # 提取备注（去掉金额和日期相关词）
    note = text
    note = re.sub(r'\d+(?:\.\d{1,2})?[元块]?', '', note)
    for kw in list(_DATE_PATTERNS.keys()) + ["元", "块", "花了", "花", "用了", "用", "付了", "付", "收到", "收了"]:
        note = note.replace(kw, '')
    note = note.strip()
    if not note:
        note = text

    # 分类
    category = await classify(note)

    return {
        "type": record_type,
        "amount": round(amount, 2),
        "category": category,
        "note": note[:100] if note else text[:100],
        "date": date_str,
    }


# ============================================================
# 4. 异常消费预警（纯计算，原本就不调 LLM）
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

    # 去重
    seen = set()
    unique = []
    for a in alerts:
        if a["message"] not in seen:
            seen.add(a["message"])
            unique.append(a)
    return unique[:5]


# ============================================================
# 5. 预算助手（纯规则 — 计算 + 模板文本）
# ============================================================

async def budget_advice(month, budget, expense_total, expense_cats,
                        days_passed, days_total) -> str:
    """根据预算和支出进度给建议（纯计算，不调 LLM）"""
    remaining = budget - expense_total
    days_left = days_total - days_passed
    daily_avg = expense_total / days_passed if days_passed > 0 else 0
    projected = daily_avg * days_total
    daily_remaining = remaining / days_left if days_left > 0 else 0

    # 支出最大的分类
    top_cat = expense_cats[0]["category"] if expense_cats else "暂无"
    top_amt = expense_cats[0]["amount"] if expense_cats else 0

    lines = []

    # 进度评价
    spend_ratio = expense_total / budget if budget > 0 else 0
    time_ratio = days_passed / days_total if days_total > 0 else 0
    if spend_ratio > time_ratio + 0.15:
        lines.append(f"本月已过 {days_passed}/{days_total} 天，花了预算的 {spend_ratio*100:.0f}%，消费节奏偏快。")
    elif spend_ratio < time_ratio - 0.15:
        lines.append(f"本月已过 {days_passed}/{days_total} 天，只花了预算的 {spend_ratio*100:.0f}%，控制得不错！")
    else:
        lines.append(f"本月已过 {days_passed}/{days_total} 天，花了预算的 {spend_ratio*100:.0f}%，节奏比较正常。")

    # 剩余额度
    if remaining > 0:
        lines.append(f"剩余 {remaining:.0f} 元，接下来每天可花约 {daily_remaining:.0f} 元。")
    else:
        lines.append(f"已超支 {-remaining:.0f} 元，建议控制后续开支。")

    # 预测
    if projected > budget:
        lines.append(f"按当前日均 {daily_avg:.0f} 元的速度，月底预计支出 {projected:.0f} 元，可能超预算 {projected-budget:.0f} 元。")
    else:
        lines.append(f"按当前节奏，月底预计支出 {projected:.0f} 元，在预算范围内。")

    # 节省建议
    if top_cat and top_amt > budget * 0.3:
        lines.append(f"「{top_cat}」占支出大头（{top_amt:.0f} 元），可以重点关注这块的开支。")

    return "\n".join(lines)


# ============================================================
# 6. 账单问答（纯规则 — 结构化数据检索 + 计算）
# ============================================================

# 关键词→分类的反向映射（用于从问题中提取分类意图）
_QUERY_CAT_MAP = {
    "吃饭": "餐饮", "吃": "餐饮", "餐饮": "餐饮", "外卖": "餐饮", "饭": "餐饮",
    "喝": "餐饮", "咖啡": "餐饮", "奶茶": "餐饮", "水果": "餐饮", "零食": "餐饮",
    "打车": "交通", "交通": "交通", "出行": "交通", "加油": "交通", "地铁": "交通",
    "公交": "交通", "高铁": "交通", "飞机": "交通", "机票": "交通",
    "购物": "购物", "买东西": "购物", "网购": "购物", "淘宝": "购物", "京东": "购物",
    "娱乐": "娱乐", "玩": "娱乐", "游戏": "娱乐", "电影": "娱乐", "旅游": "娱乐",
    "房租": "居住", "居住": "居住", "水电": "居住", "物业": "居住", "房贷": "居住",
    "医疗": "医疗", "看病": "医疗", "药": "医疗", "医院": "医疗",
    "教育": "教育", "学费": "教育", "培训": "教育", "书": "教育",
    "通讯": "通讯", "话费": "通讯", "流量": "通讯",
    "投资": "投资", "理财": "理财", "红包": "红包", "报销": "报销",
    "工资": "工资", "薪水": "工资",
    "兼职": "兼职", "副业": "兼职", "稿费": "兼职",
    "奖金": "奖金", "年终奖": "奖金", "绩效": "奖金",
    "退款": "退款", "返现": "退款",
    "租金": "租金收入", "出租": "租金收入",
    "生意": "生意", "营业": "生意", "货款": "生意",
    "补贴": "补贴", "津贴": "补贴",
    "人情": "人情", "份子钱": "人情", "随礼": "人情", "请客": "人情", "送礼": "人情",
    "美容": "美容", "理发": "美容", "美甲": "美容", "护肤": "美容",
}


def _parse_target_month(q: str) -> str | None:
    """从问题中提取目标月份，返回 YYYY-MM 或 None"""
    now = datetime.now()
    if "这个月" in q or "本月" in q:
        return now.strftime("%Y-%m")
    if "上个月" in q or "上月" in q:
        last = now.replace(day=1) - timedelta(days=1)
        return last.strftime("%Y-%m")
    if "前月" in q or "上上个月" in q or "上上月" in q:
        first_of_last = now.replace(day=1) - timedelta(days=1)
        prev = first_of_last.replace(day=1) - timedelta(days=1)
        return prev.strftime("%Y-%m")
    # 匹配 "X月" 或 "YYYY年X月"
    m = re.search(r'(\d{4})\s*年\s*(\d{1,2})\s*月', q)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}"
    m = re.search(r'(\d{1,2})\s*月', q)
    if m:
        month = int(m.group(1))
        if 1 <= month <= 12:
            return f"{now.year}-{month:02d}"
    return None


def _parse_target_cat(q: str) -> str | None:
    """从问题中提取目标分类"""
    # 先精确匹配分类名
    for cat in ALL_CATS_LIST:
        if cat in q:
            return cat
    # 再模糊匹配关键词
    for kw, cat in sorted(_QUERY_CAT_MAP.items(), key=lambda x: -len(x[0])):
        if kw in q:
            return cat
    return None


async def chat_query(question: str, records: list[dict]) -> str:
    """基于结构化记录数据回答用户问题（纯规则）
    records: [{"date","type","category","amount","note"}, ...]
    """
    if not records:
        return "暂无记录数据。"

    q = question
    target_month = _parse_target_month(q)
    target_cat = _parse_target_cat(q)

    # 按条件过滤记录
    filtered = records
    month_label = ""
    if target_month:
        filtered = [r for r in filtered if r["date"].startswith(target_month)]
        month_label = target_month
    if target_cat:
        filtered = [r for r in filtered if r["category"] == target_cat]

    # 有分类条件：回答分类支出
    if target_cat:
        expenses = [r for r in filtered if r["type"] == "expense"]
        incomes = [r for r in filtered if r["type"] == "income"]
        scope = month_label or "所有记录"

        if expenses:
            total = sum(r["amount"] for r in expenses)
            lines = [f"**{scope}**「{target_cat}」共支出 **{total:.2f} 元**，{len(expenses)} 笔："]
            for r in sorted(expenses, key=lambda x: x["date"])[-10:]:
                note = f"（{r['note']}）" if r["note"] else ""
                lines.append(f"  {r['date'][5:]} {r['amount']:.2f} 元{note}")
            if len(expenses) > 10:
                lines.append(f"  ...共 {len(expenses)} 笔，仅显示最近 10 笔")
            return "\n".join(lines)
        elif incomes:
            total = sum(r["amount"] for r in incomes)
            return f"**{scope}**「{target_cat}」共收入 **{total:.2f} 元**，{len(incomes)} 笔。"
        else:
            return f"{scope} 没有找到「{target_cat}」相关的记录。"

    # 有月份条件但没分类：回答该月概览
    if target_month:
        if not filtered:
            return f"{target_month} 没有记录。"
        income = sum(r["amount"] for r in filtered if r["type"] == "income")
        expense = sum(r["amount"] for r in filtered if r["type"] == "expense")
        balance = income - expense
        # 分类明细
        cat_totals = defaultdict(float)
        for r in filtered:
            if r["type"] == "expense":
                cat_totals[r["category"]] += r["amount"]
        cat_sorted = sorted(cat_totals.items(), key=lambda x: -x[1])
        lines = [f"**{target_month}** 收入 {income:.2f} 元，支出 {expense:.2f} 元，结余 {balance:.2f} 元。"]
        if cat_sorted:
            lines.append("支出分类：")
            for cat, amt in cat_sorted[:8]:
                lines.append(f"  {cat}：{amt:.2f} 元")
        return "\n".join(lines)

    # "哪个月花钱最多"
    if ("哪个月" in q or "哪月" in q) and ("花" in q or "支出" in q or "多" in q):
        by_month = defaultdict(float)
        for r in records:
            if r["type"] == "expense":
                by_month[r["date"][:7]] += r["amount"]
        if by_month:
            top = max(by_month.items(), key=lambda x: x[1])
            return f"支出最多的是 **{top[0]}**，共支出 **{top[1]:.2f} 元**。"

    # "哪个月收入最多"
    if ("哪个月" in q or "哪月" in q) and "收入" in q:
        by_month = defaultdict(float)
        for r in records:
            if r["type"] == "income":
                by_month[r["date"][:7]] += r["amount"]
        if by_month:
            top = max(by_month.items(), key=lambda x: x[1])
            return f"收入最多的是 **{top[0]}**，共收入 **{top[1]:.2f} 元**。"

    # "总共花了多少"
    if ("总共" in q or "一共" in q or "总" in q) and ("花" in q or "支出" in q):
        total = sum(r["amount"] for r in records if r["type"] == "expense")
        return f"所有记录总支出 **{total:.2f} 元**。"

    if ("总共" in q or "一共" in q or "总" in q) and "收入" in q:
        total = sum(r["amount"] for r in records if r["type"] == "income")
        return f"所有记录总收入 **{total:.2f} 元**。"

    # 通用：按月汇总
    by_month = defaultdict(lambda: {"income": 0.0, "expense": 0.0})
    for r in records:
        by_month[r["date"][:7]][r["type"]] += r["amount"]
    lines = ["以下是您的收支汇总："]
    total_in = total_out = 0.0
    for m in sorted(by_month.keys(), reverse=True):
        d = by_month[m]
        lines.append(f"  {m}：收入 {d['income']:.2f} 元，支出 {d['expense']:.2f} 元")
        total_in += d["income"]
        total_out += d["expense"]
    lines.append(f"\n合计：收入 {total_in:.2f} 元，支出 {total_out:.2f} 元，结余 {total_in-total_out:.2f} 元")
    return "\n".join(lines)


# ============================================================
# 7. 消费习惯画像（调 LLM）
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

    # 缓存
    cache_key = "profile:" + hashlib.md5(summary.encode()).hexdigest()
    cached = _cache_get(cache_key)
    if cached:
        return cached

    try:
        result = await _call_llm(prompt, max_tokens=800)
        # 格式降级：输出缺 ### 时 fallback 到 14b
        if result.count("###") < 3:
            result = await _call_llm(prompt, max_tokens=800, model=MODEL_FALLBACK)
        _cache_set(cache_key, result)
        return result
    except Exception as e:
        return f"画像生成失败：{e}"
