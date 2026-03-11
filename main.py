import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

import bcrypt
import jwt
from fastapi import FastAPI, Query, UploadFile, File, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from itsdangerous import URLSafeSerializer
from pydantic import BaseModel
from sqlalchemy import func

from models import SessionLocal, User, Record, Category, Budget, init_db
from ai import (classify, generate_report, smart_parse, detect_anomalies,
                budget_advice, chat_query, spending_profile)
from bill_parser import parse_alipay_csv, parse_wechat_csv, parse_excel

SECRET_KEY = "bookkeeper-secret-key-2026"
COOKIE_NAME = "session"
serializer = URLSafeSerializer(SECRET_KEY)

JWT_SECRET = SECRET_KEY
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = 30


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs("data", exist_ok=True)
    init_db()
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Auth helpers ---

def create_token(user_id: int) -> str:
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(days=JWT_EXPIRE_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def get_current_user(request: Request):
    """从 Bearer Token 或 Cookie 解析当前用户，返回 User 或 None"""
    # 1. 尝试 Bearer Token（小程序/App）
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            payload = jwt.decode(auth[7:], JWT_SECRET, algorithms=[JWT_ALGORITHM])
            db = SessionLocal()
            user = db.query(User).filter(User.id == payload["user_id"]).first()
            db.close()
            if user:
                return user
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            pass
    # 2. 回退 Cookie（Web）
    cookie = request.cookies.get(COOKIE_NAME)
    if not cookie:
        return None
    try:
        user_id = serializer.loads(cookie)
    except Exception:
        return None
    db = SessionLocal()
    user = db.query(User).filter(User.id == user_id).first()
    db.close()
    return user


def require_user(request: Request):
    """要求登录，未登录返回 None（由路由返回 401）"""
    return get_current_user(request)


def set_session_cookie(response: Response, user_id: int):
    response.set_cookie(COOKIE_NAME, serializer.dumps(user_id),
                        httponly=True, samesite="lax", max_age=30 * 86400)


# --- Pydantic schemas ---

class AuthRequest(BaseModel):
    username: str
    password: str


class RecordCreate(BaseModel):
    type: str
    amount: float
    category: str
    note: str = ""
    date: str


class ClassifyRequest(BaseModel):
    note: str


# --- Auth API ---

@app.post("/api/register")
def register(data: AuthRequest, response: Response):
    if len(data.username) < 2 or len(data.password) < 4:
        return JSONResponse({"error": "用户名至少2位，密码至少4位"}, 400)
    db = SessionLocal()
    if db.query(User).filter(User.username == data.username).first():
        db.close()
        return JSONResponse({"error": "用户名已存在"}, 400)
    pw_hash = bcrypt.hashpw(data.password.encode(), bcrypt.gensalt()).decode()
    user = User(username=data.username, password_hash=pw_hash)
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    set_session_cookie(response, user.id)
    return {"ok": True, "username": user.username, "token": create_token(user.id)}


@app.post("/api/login")
def login(data: AuthRequest, response: Response):
    db = SessionLocal()
    user = db.query(User).filter(User.username == data.username).first()
    db.close()
    if not user or not bcrypt.checkpw(data.password.encode(), user.password_hash.encode()):
        return JSONResponse({"error": "用户名或密码错误"}, 401)
    set_session_cookie(response, user.id)
    return {"ok": True, "username": user.username, "token": create_token(user.id)}


@app.post("/api/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME)
    return {"ok": True}


@app.get("/api/user")
def get_user(request: Request):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, 401)
    return {"username": user.username}


# --- Data API (require auth) ---

@app.get("/api/records")
def get_records(request: Request, month: str = Query(None), category: str = Query(None)):
    user = require_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, 401)
    db = SessionLocal()
    q = db.query(Record).filter(Record.user_id == user.id).order_by(Record.date.desc(), Record.id.desc())
    if month:
        q = q.filter(Record.date.like(f"{month}%"))
    if category:
        q = q.filter(Record.category == category)
    records = q.all()
    result = [
        {"id": r.id, "type": r.type, "amount": r.amount, "category": r.category,
         "note": r.note, "date": r.date, "created_at": r.created_at}
        for r in records
    ]
    db.close()
    return result


@app.post("/api/records")
def create_record(request: Request, data: RecordCreate):
    user = require_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, 401)
    db = SessionLocal()
    record = Record(user_id=user.id, type=data.type, amount=data.amount,
                    category=data.category, note=data.note, date=data.date)
    db.add(record)
    db.commit()
    db.refresh(record)
    result = {"id": record.id, "type": record.type, "amount": record.amount,
              "category": record.category, "note": record.note, "date": record.date}
    db.close()
    return result


@app.delete("/api/records/all")
def delete_all_records(request: Request):
    user = require_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, 401)
    db = SessionLocal()
    count = db.query(Record).filter(Record.user_id == user.id).delete()
    db.commit()
    db.close()
    return {"ok": True, "deleted": count}


@app.delete("/api/records/{record_id}")
def delete_record(request: Request, record_id: int):
    user = require_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, 401)
    db = SessionLocal()
    record = db.query(Record).filter(Record.id == record_id, Record.user_id == user.id).first()
    if not record:
        db.close()
        return {"error": "not found"}
    db.delete(record)
    db.commit()
    db.close()
    return {"ok": True}


@app.get("/api/stats/monthly")
def monthly_stats(request: Request, month: str = Query(...)):
    user = require_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, 401)
    db = SessionLocal()
    rows = (
        db.query(Record.type, Record.category, func.sum(Record.amount))
        .filter(Record.user_id == user.id, Record.date.like(f"{month}%"))
        .group_by(Record.type, Record.category)
        .all()
    )
    income_total = 0.0
    expense_total = 0.0
    income_cats = []
    expense_cats = []
    for type_, cat, total in rows:
        entry = {"category": cat, "amount": round(total, 2)}
        if type_ == "income":
            income_total += total
            income_cats.append(entry)
        else:
            expense_total += total
            expense_cats.append(entry)
    db.close()
    return {
        "month": month,
        "income_total": round(income_total, 2),
        "expense_total": round(expense_total, 2),
        "income_categories": sorted(income_cats, key=lambda x: -x["amount"]),
        "expense_categories": sorted(expense_cats, key=lambda x: -x["amount"]),
    }


@app.get("/api/stats/trend")
def trend_stats(request: Request, months: int = Query(6)):
    user = require_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, 401)
    db = SessionLocal()
    rows = (
        db.query(
            func.substr(Record.date, 1, 7).label("month"),
            Record.type,
            func.sum(Record.amount),
        )
        .filter(Record.user_id == user.id)
        .group_by("month", Record.type)
        .order_by("month")
        .all()
    )
    db.close()
    data = {}
    for month, type_, total in rows:
        if month not in data:
            data[month] = {"month": month, "income": 0, "expense": 0}
        data[month][type_] = round(total, 2)
    result = sorted(data.values(), key=lambda x: x["month"])
    return result[-months:] if len(result) > months else result


@app.get("/api/categories")
def get_categories():
    db = SessionLocal()
    cats = db.query(Category).all()
    result = [{"id": c.id, "name": c.name, "type": c.type, "icon": c.icon} for c in cats]
    db.close()
    return result


@app.post("/api/ai/classify")
async def ai_classify(request: Request, data: ClassifyRequest):
    user = require_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, 401)
    category = await classify(data.note)
    return {"category": category}


@app.get("/api/ai/report")
async def ai_report(request: Request, month: str = Query(...)):
    user = require_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, 401)
    db = SessionLocal()
    # 获取月度统计
    rows = (
        db.query(Record.type, Record.category, func.sum(Record.amount))
        .filter(Record.user_id == user.id, Record.date.like(f"{month}%"))
        .group_by(Record.type, Record.category)
        .all()
    )
    record_count = db.query(Record).filter(
        Record.user_id == user.id, Record.date.like(f"{month}%")
    ).count()
    db.close()

    income_total = 0.0
    expense_total = 0.0
    income_cats = []
    expense_cats = []
    for type_, cat, total in rows:
        entry = {"category": cat, "amount": round(total, 2)}
        if type_ == "income":
            income_total += total
            income_cats.append(entry)
        else:
            expense_total += total
            expense_cats.append(entry)

    if record_count == 0:
        return {"report": "本月暂无交易记录，无法生成报告。"}

    report = await generate_report(
        month, round(income_total, 2), round(expense_total, 2),
        sorted(income_cats, key=lambda x: -x["amount"]),
        sorted(expense_cats, key=lambda x: -x["amount"]),
        record_count,
    )
    return {"report": report, "month": month}


# --- 智能记账 ---

class SmartAddRequest(BaseModel):
    text: str


@app.post("/api/ai/smart-add")
async def ai_smart_add(request: Request, data: SmartAddRequest):
    user = require_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, 401)
    result = await smart_parse(data.text)
    if "error" in result:
        return result
    # 返回解析结果让前端确认，不直接入库
    return {"parsed": result}


@app.post("/api/ai/smart-add/confirm")
async def ai_smart_add_confirm(request: Request, data: RecordCreate):
    """确认智能记账结果并入库"""
    user = require_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, 401)
    db = SessionLocal()
    record = Record(user_id=user.id, type=data.type, amount=data.amount,
                    category=data.category, note=data.note, date=data.date)
    db.add(record)
    db.commit()
    db.refresh(record)
    result = {"id": record.id, "type": record.type, "amount": record.amount,
              "category": record.category, "note": record.note, "date": record.date}
    db.close()
    return result


# --- 异常消费预警 ---

@app.get("/api/ai/alerts")
def get_alerts(request: Request, month: str = Query(...)):
    user = require_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, 401)
    db = SessionLocal()

    # 当月记录
    records = db.query(Record).filter(
        Record.user_id == user.id, Record.date.like(f"{month}%"),
        Record.type == "expense"
    ).all()
    records_list = [{"amount": r.amount, "category": r.category,
                     "note": r.note, "date": r.date, "type": r.type} for r in records]

    # 当月分类汇总
    current_cats = []
    rows = (db.query(Record.category, func.sum(Record.amount))
            .filter(Record.user_id == user.id, Record.date.like(f"{month}%"),
                    Record.type == "expense")
            .group_by(Record.category).all())
    for cat, total in rows:
        current_cats.append({"category": cat, "amount": round(total, 2)})

    # 历史月份分类汇总（排除当月）
    history_cats = []
    hist_rows = (db.query(
        func.substr(Record.date, 1, 7).label("m"), Record.category, func.sum(Record.amount))
        .filter(Record.user_id == user.id, Record.type == "expense",
                ~Record.date.like(f"{month}%"))
        .group_by("m", Record.category).all())
    for _, cat, total in hist_rows:
        history_cats.append({"category": cat, "amount": round(total, 2)})

    db.close()

    alerts = detect_anomalies(current_cats, history_cats, records_list)
    return {"alerts": alerts, "month": month}


# --- 预算助手 ---

class BudgetSet(BaseModel):
    month: str
    amount: float


@app.get("/api/budget")
def get_budget(request: Request, month: str = Query(...)):
    user = require_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, 401)
    db = SessionLocal()
    b = db.query(Budget).filter(Budget.user_id == user.id, Budget.month == month).first()
    db.close()
    return {"month": month, "amount": b.amount if b else None}


@app.post("/api/budget")
def set_budget(request: Request, data: BudgetSet):
    user = require_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, 401)
    db = SessionLocal()
    b = db.query(Budget).filter(Budget.user_id == user.id, Budget.month == data.month).first()
    if b:
        b.amount = data.amount
    else:
        db.add(Budget(user_id=user.id, month=data.month, amount=data.amount))
    db.commit()
    db.close()
    return {"ok": True}


@app.get("/api/ai/budget-advice")
async def get_budget_advice(request: Request, month: str = Query(...)):
    user = require_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, 401)
    db = SessionLocal()
    b = db.query(Budget).filter(Budget.user_id == user.id, Budget.month == month).first()
    if not b:
        db.close()
        return {"advice": "请先设定本月预算。"}

    # 月度支出
    rows = (db.query(Record.category, func.sum(Record.amount))
            .filter(Record.user_id == user.id, Record.date.like(f"{month}%"),
                    Record.type == "expense")
            .group_by(Record.category).all())
    expense_cats = sorted([{"category": c, "amount": round(t, 2)} for c, t in rows],
                          key=lambda x: -x["amount"])
    expense_total = sum(c["amount"] for c in expense_cats)

    # 计算天数
    year, mon = int(month[:4]), int(month[5:7])
    today = datetime.now()
    if today.year == year and today.month == mon:
        days_passed = today.day
    else:
        days_passed = 30
    import calendar
    days_total = calendar.monthrange(year, mon)[1]

    db.close()

    advice = await budget_advice(month, b.amount, expense_total, expense_cats,
                                 days_passed, days_total)
    return {
        "advice": advice, "budget": b.amount,
        "expense_total": round(expense_total, 2),
        "remaining": round(b.amount - expense_total, 2),
        "days_passed": days_passed, "days_total": days_total,
    }


# --- 账单问答 ---

class ChatRequest(BaseModel):
    question: str
    months: int = 3


@app.post("/api/ai/chat")
async def ai_chat(request: Request, data: ChatRequest):
    user = require_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, 401)
    db = SessionLocal()

    # 汇总最近 N 个月的数据
    records = (db.query(Record)
               .filter(Record.user_id == user.id)
               .order_by(Record.date.desc())
               .limit(500).all())
    db.close()

    if not records:
        return {"answer": "暂无记录数据，请先记几笔账。"}

    # 构建摘要
    by_month = {}
    for r in records:
        m = r.date[:7]
        if m not in by_month:
            by_month[m] = {"income": 0, "expense": 0, "records": []}
        by_month[m][r.type] += r.amount
        if len(by_month[m]["records"]) < 20:
            by_month[m]["records"].append(f"{r.date} {r.type} {r.category} {r.amount}元 {r.note}")

    summary_parts = []
    for m in sorted(by_month.keys(), reverse=True)[:data.months]:
        d = by_month[m]
        summary_parts.append(
            f"{m}：收入{d['income']:.2f}元，支出{d['expense']:.2f}元\n"
            + "\n".join(f"  {x}" for x in d["records"])
        )
    summary = "\n\n".join(summary_parts)

    answer = await chat_query(data.question, summary)
    return {"answer": answer}


# --- 消费习惯画像 ---

@app.get("/api/ai/profile")
async def ai_profile(request: Request):
    user = require_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, 401)
    db = SessionLocal()

    rows = (db.query(
        func.substr(Record.date, 1, 7).label("month"),
        Record.type, Record.category, func.sum(Record.amount))
        .filter(Record.user_id == user.id)
        .group_by("month", Record.type, Record.category)
        .all())
    db.close()

    if not rows:
        return {"profile": "暂无足够数据生成画像，请多记几个月的账。"}

    months_map = {}
    for month, type_, cat, total in rows:
        if month not in months_map:
            months_map[month] = {"month": month, "income": 0, "expense": 0, "expense_cats": []}
        if type_ == "income":
            months_map[month]["income"] += total
        else:
            months_map[month]["expense"] += total
            months_map[month]["expense_cats"].append({"category": cat, "amount": round(total, 2)})

    months_data = sorted(months_map.values(), key=lambda x: x["month"], reverse=True)[:6]
    for m in months_data:
        m["expense_cats"].sort(key=lambda x: -x["amount"])

    profile = await spending_profile(months_data)
    return {"profile": profile}


@app.post("/api/import")
async def import_csv(request: Request, file: UploadFile = File(...)):
    user = require_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, 401)
    raw = await file.read()
    filename = (file.filename or "").lower()
    is_excel = filename.endswith((".xlsx", ".xls"))

    if is_excel:
        source, records_data = parse_excel(raw)
        if source is None:
            return {"error": "无法识别的 Excel 账单格式，请上传支付宝或微信导出的账单"}
    else:
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("gbk")

        if "支付宝" in text[:500] or "交易号" in text[:2000]:
            records_data = parse_alipay_csv(text)
            source = "alipay"
        elif "微信" in text[:500] or "交易时间" in text[:2000]:
            records_data = parse_wechat_csv(text)
            source = "wechat"
        else:
            return {"error": "无法识别的账单格式，请上传支付宝或微信的 CSV/Excel 账单"}

    # 对分类为"其他"且有备注的记录，批量调用 AI 重新分类
    ai_classified = 0
    for r in records_data:
        if r["amount"] <= 0:
            continue
        note = (r.get("note") or "").strip()
        if r["category"] == "其他" and note:
            try:
                new_cat = await classify(note)
                if new_cat and new_cat != "其他":
                    r["category"] = new_cat
                    ai_classified += 1
            except Exception:
                pass  # 分类失败保持"其他"

    db = SessionLocal()
    imported = 0
    skipped = 0
    for r in records_data:
        if r["amount"] <= 0:
            skipped += 1
            continue
        record = Record(
            user_id=user.id,
            type=r["type"], amount=r["amount"], category=r["category"],
            note=r["note"], date=r["date"],
        )
        db.add(record)
        imported += 1
    db.commit()
    db.close()
    return {"ok": True, "source": source, "imported": imported, "skipped": skipped, "ai_classified": ai_classified}


# --- WeChat login stub ---

class WxLoginRequest(BaseModel):
    code: str


@app.post("/api/wx-login")
async def wx_login(data: WxLoginRequest):
    """微信小程序登录（桩：暂无 AppID）"""
    return JSONResponse({"error": "微信登录暂未开通，请使用用户名密码登录"}, 501)


# --- Static files ---

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def index():
    return FileResponse("static/index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
