import os
from contextlib import asynccontextmanager

import bcrypt
from fastapi import FastAPI, Query, UploadFile, File, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from itsdangerous import URLSafeSerializer
from pydantic import BaseModel
from sqlalchemy import func

from models import SessionLocal, User, Record, Category, init_db
from ai import classify
from bill_parser import parse_alipay_csv, parse_wechat_csv

SECRET_KEY = "bookkeeper-secret-key-2026"
COOKIE_NAME = "session"
serializer = URLSafeSerializer(SECRET_KEY)


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs("data", exist_ok=True)
    init_db()
    yield


app = FastAPI(lifespan=lifespan)


# --- Auth helpers ---

def get_current_user(request: Request):
    """从 Cookie 解析当前用户，返回 User 或 None"""
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
    return {"ok": True, "username": user.username}


@app.post("/api/login")
def login(data: AuthRequest, response: Response):
    db = SessionLocal()
    user = db.query(User).filter(User.username == data.username).first()
    db.close()
    if not user or not bcrypt.checkpw(data.password.encode(), user.password_hash.encode()):
        return JSONResponse({"error": "用户名或密码错误"}, 401)
    set_session_cookie(response, user.id)
    return {"ok": True, "username": user.username}


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


@app.post("/api/import")
async def import_csv(request: Request, file: UploadFile = File(...)):
    user = require_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, 401)
    raw = await file.read()
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
        return {"error": "无法识别的账单格式，请上传支付宝或微信的 CSV 账单"}

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
    return {"ok": True, "source": source, "imported": imported, "skipped": skipped}


# --- Static files ---

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def index():
    return FileResponse("static/index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
