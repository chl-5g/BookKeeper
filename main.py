import os
import csv
import io
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import func, extract

from models import SessionLocal, Record, Category, init_db
from ai import classify
from bill_parser import parse_alipay_csv, parse_wechat_csv


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs("data", exist_ok=True)
    init_db()
    yield


app = FastAPI(lifespan=lifespan)


# --- Pydantic schemas ---

class RecordCreate(BaseModel):
    type: str
    amount: float
    category: str
    note: str = ""
    date: str


class ClassifyRequest(BaseModel):
    note: str


# --- API routes ---

@app.get("/api/records")
def get_records(month: str = Query(None), category: str = Query(None)):
    db = SessionLocal()
    q = db.query(Record).order_by(Record.date.desc(), Record.id.desc())
    if month:  # YYYY-MM
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
def create_record(data: RecordCreate):
    db = SessionLocal()
    record = Record(type=data.type, amount=data.amount, category=data.category,
                    note=data.note, date=data.date)
    db.add(record)
    db.commit()
    db.refresh(record)
    result = {"id": record.id, "type": record.type, "amount": record.amount,
              "category": record.category, "note": record.note, "date": record.date}
    db.close()
    return result


@app.delete("/api/records/{record_id}")
def delete_record(record_id: int):
    db = SessionLocal()
    record = db.query(Record).filter(Record.id == record_id).first()
    if not record:
        db.close()
        return {"error": "not found"}
    db.delete(record)
    db.commit()
    db.close()
    return {"ok": True}


@app.get("/api/stats/monthly")
def monthly_stats(month: str = Query(...)):
    """月度统计，按分类汇总。month 格式: YYYY-MM"""
    db = SessionLocal()
    rows = (
        db.query(Record.type, Record.category, func.sum(Record.amount))
        .filter(Record.date.like(f"{month}%"))
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
def trend_stats(months: int = Query(6)):
    """近 N 个月收支趋势"""
    db = SessionLocal()
    # 获取所有记录按月汇总
    rows = (
        db.query(
            func.substr(Record.date, 1, 7).label("month"),
            Record.type,
            func.sum(Record.amount),
        )
        .group_by("month", Record.type)
        .order_by("month")
        .all()
    )
    db.close()
    # 组装数据
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
async def ai_classify(data: ClassifyRequest):
    category = await classify(data.note)
    return {"category": category}


@app.post("/api/import")
async def import_csv(file: UploadFile = File(...)):
    """导入支付宝或微信账单 CSV"""
    raw = await file.read()
    # 尝试 UTF-8（微信），失败则 GBK（支付宝）
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("gbk")

    # 自动检测平台
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
