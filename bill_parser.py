"""解析支付宝和微信支付导出的 CSV 账单"""

import csv
import io
import re

# 分类关键词映射
CATEGORY_KEYWORDS = {
    "餐饮": ["餐", "饭", "食", "奶茶", "咖啡", "外卖", "美团", "饿了么", "肯德基", "麦当劳", "火锅", "小吃", "早餐", "午餐", "晚餐", "面包", "蛋糕", "水果"],
    "交通": ["打车", "滴滴", "地铁", "公交", "高铁", "火车", "机票", "加油", "停车", "出行", "铁路", "航空", "uber", "曹操", "哈啰"],
    "购物": ["淘宝", "京东", "拼多多", "天猫", "超市", "商城", "购物", "买", "服装", "数码"],
    "娱乐": ["电影", "游戏", "KTV", "音乐", "视频", "会员", "爱奇艺", "优酷", "腾讯视频", "网易云", "Spotify", "bilibili"],
    "居住": ["房租", "水费", "电费", "燃气", "物业", "装修", "家具", "房贷"],
    "医疗": ["医院", "药", "诊所", "体检", "挂号", "医保"],
    "教育": ["学费", "课程", "培训", "书", "考试", "教材"],
    "通讯": ["话费", "流量", "宽带", "中国移动", "中国联通", "中国电信"],
    "工资": ["工资", "薪资", "奖金", "绩效"],
    "理财": ["利息", "股息", "分红", "收益", "理财", "基金"],
    "红包": ["红包"],
    "报销": ["报销"],
    "转账": ["转账", "转入", "转出"],
}


def guess_category(note: str, counterpart: str = "") -> str:
    """根据备注和交易对方猜测分类"""
    text = (note + " " + counterpart).lower()
    for cat, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return cat
    return "其他"


def parse_alipay_csv(text: str) -> list[dict]:
    """解析支付宝账单 CSV"""
    lines = text.splitlines()

    # 跳过 # 开头的头部信息行，找到表头
    header_idx = None
    for i, line in enumerate(lines):
        stripped = line.strip().strip("\t").strip(",")
        if stripped.startswith("交易号") or stripped.startswith("交易创建时间"):
            header_idx = i
            break
    if header_idx is None:
        # 尝试找包含"金额"的行作为表头
        for i, line in enumerate(lines):
            if "金额" in line and "收/支" in line:
                header_idx = i
                break
    if header_idx is None:
        return []

    # 解析 CSV
    csv_text = "\n".join(lines[header_idx:])
    reader = csv.DictReader(io.StringIO(csv_text))
    records = []

    for row in reader:
        # 清理 key 中的空白
        row = {k.strip(): v.strip() if v else "" for k, v in row.items() if k}

        direction = row.get("收/支", "").strip()
        if direction not in ("收入", "支出", "收", "支"):
            continue  # 跳过不明确的（如"不计收支"）

        # 金额
        amount_str = row.get("金额（元）", row.get("金额(元)", "0"))
        amount_str = amount_str.replace(",", "").replace("¥", "").strip()
        try:
            amount = float(amount_str)
        except ValueError:
            continue

        # 日期
        time_str = row.get("交易创建时间", row.get("付款时间", ""))
        date = time_str[:10].replace("/", "-") if time_str else ""
        if not re.match(r"\d{4}-\d{2}-\d{2}", date):
            continue

        # 备注
        product = row.get("商品名称", row.get("商品说明", ""))
        counterpart = row.get("交易对方", "")
        note = product if product else counterpart

        is_income = direction in ("收入", "收")
        category = guess_category(note, counterpart)
        if is_income and category == "其他":
            category = "其他收入"

        records.append({
            "type": "income" if is_income else "expense",
            "amount": amount,
            "category": category,
            "note": note[:100],
            "date": date,
        })

    return records


def parse_wechat_csv(text: str) -> list[dict]:
    """解析微信支付账单 CSV"""
    lines = text.splitlines()

    # 找到表头行
    header_idx = None
    for i, line in enumerate(lines):
        if "交易时间" in line and "收/支" in line:
            header_idx = i
            break
    if header_idx is None:
        return []

    csv_text = "\n".join(lines[header_idx:])
    reader = csv.DictReader(io.StringIO(csv_text))
    records = []

    for row in reader:
        row = {k.strip(): v.strip() if v else "" for k, v in row.items() if k}

        direction = row.get("收/支", "").strip()
        if direction not in ("收入", "支出", "收", "支"):
            continue

        amount_str = row.get("金额(元)", row.get("金额（元）", "0"))
        amount_str = amount_str.replace(",", "").replace("¥", "").strip()
        try:
            amount = float(amount_str)
        except ValueError:
            continue

        time_str = row.get("交易时间", "")
        date = time_str[:10].replace("/", "-") if time_str else ""
        if not re.match(r"\d{4}-\d{2}-\d{2}", date):
            continue

        product = row.get("商品", row.get("商品说明", ""))
        counterpart = row.get("交易对方", "")
        note = product if product else counterpart

        is_income = direction in ("收入", "收")
        category = guess_category(note, counterpart)
        if is_income and category == "其他":
            category = "其他收入"

        records.append({
            "type": "income" if is_income else "expense",
            "amount": amount,
            "category": category,
            "note": note[:100],
            "date": date,
        })

    return records
