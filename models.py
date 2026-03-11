from sqlalchemy import create_engine, Column, Integer, Text, Float, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///data/bookkeeper.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(Text, nullable=False, unique=True)
    password_hash = Column(Text, nullable=False)
    created_at = Column(Text, server_default="CURRENT_TIMESTAMP")


class Record(Base):
    __tablename__ = "records"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    type = Column(Text, nullable=False)       # 'income' / 'expense'
    amount = Column(Float, nullable=False)
    category = Column(Text, nullable=False)
    note = Column(Text, default="")
    date = Column(Text, nullable=False)        # YYYY-MM-DD
    created_at = Column(Text, server_default="CURRENT_TIMESTAMP")


class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False, unique=True)
    type = Column(Text, nullable=False)        # 'income' / 'expense'
    icon = Column(Text, default="")


DEFAULT_CATEGORIES = [
    # 支出
    ("餐饮", "expense", "🍜"), ("交通", "expense", "🚗"), ("购物", "expense", "🛒"),
    ("娱乐", "expense", "🎮"), ("居住", "expense", "🏠"), ("医疗", "expense", "💊"),
    ("教育", "expense", "📚"), ("通讯", "expense", "📱"), ("其他", "expense", "📦"),
    # 收入
    ("工资", "income", "💰"), ("理财", "income", "📈"), ("红包", "income", "🧧"),
    ("报销", "income", "🧾"), ("其他收入", "income", "💵"),
]


def init_db():
    Base.metadata.create_all(engine)
    db = SessionLocal()
    if db.query(Category).count() == 0:
        for name, type_, icon in DEFAULT_CATEGORIES:
            db.add(Category(name=name, type=type_, icon=icon))
        db.commit()
    db.close()
