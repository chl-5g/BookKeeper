# BookKeeper 智小账-AI记账助手

个人智能记账应用，支持手动记账、自然语言智能记账、支付宝/微信账单导入、AI 财务报告、消费画像分析等。后端纯 Python，AI 功能基于本地 ollama 推理，数据完全私有。

## 功能概览

| 功能 | 说明 | 是否调 LLM |
|------|------|:----------:|
| 手动记账 | 输入备注自动识别分类（关键词匹配） | 否 |
| 智能记账 | 自然语言输入如"昨天打车花了30"，自动解析金额/日期/分类 | 否 |
| 账单导入 | 支持支付宝（GBK CSV）、微信支付（UTF-8 CSV）、Excel | 否 |
| 统计图表 | 支出/收入饼图 + 月度收支趋势折线图（ECharts） | 否 |
| 预算管理 | 设定月度预算，追踪进度，给出节省建议 | 否 |
| 账单问答 | "这个月吃饭花了多少？""哪个月花钱最多？" | 否 |
| 异常消费预警 | 单笔大额检测 + 分类月均突增检测 | 否 |
| AI 财务报告 | 基于月度收支数据生成分析报告和理财建议（流式输出） | **是** |
| 消费习惯画像 | 分析多月消费数据，生成消费标签和优化建议（流式输出） | **是** |

> **LLM 使用原则**：只有 AI 财务报告和消费习惯画像调用 LLM（qwen3:4b），其他功能全部纯规则实现，零延迟。

## 技术栈

- **后端**：Python 3.12 + FastAPI + SQLite + SQLAlchemy
- **Web 前端**：Vue 3（CDN）+ ECharts
- **uni-app 前端**：Vue 3 + Vite（支持微信小程序 / App / H5 三端）
- **AI 推理**：ollama + qwen3:4b（本地 GPU）
- **认证**：Cookie Session（Web）+ JWT Bearer Token（小程序/App）
- **部署**：systemd 服务，端口 8080

## 项目结构

```
/opt/bookkeeper/
├── main.py              # FastAPI 主入口，路由 & 中间件
├── models.py            # SQLAlchemy 模型（User, Record, Category, Budget）
├── ai.py                # AI 模块（关键词分类、LLM 报告/画像、智能记账、问答）
├── bill_parser.py       # 支付宝/微信/Excel 账单解析器
├── data/
│   └── bookkeeper.db    # SQLite 数据库
├── static/
│   ├── index.html       # Web 单页应用
│   ├── app.js           # Vue 3 应用逻辑
│   ├── style.css        # 样式
│   └── favicon.svg      # 图标
└── uni-app/             # 跨端应用（微信小程序 / App / H5）
    └── src/
        └── pages/       # login / home / add / stats / ai
```

## 数据库

SQLite，文件路径：`data/bookkeeper.db`

### 数据表

| 表名 | 说明 | 主要字段 |
|------|------|----------|
| `users` | 用户 | id, username, password_hash, created_at |
| `records` | 收支记录 | id, user_id(FK), type(income/expense), amount, category, note, date(YYYY-MM-DD), created_at |
| `categories` | 分类 | id, name, type(income/expense), icon |
| `budgets` | 月度预算 | id, user_id(FK), month(YYYY-MM), amount |

### 表关系

- `records.user_id` → `users.id`
- `budgets.user_id` → `users.id`
- `categories` 独立表，初始化时预填默认分类

## 快速启动

### 环境要求

- Python 3.12+
- ollama（运行 qwen3:4b 模型，需 GPU）

### 安装依赖

```bash
pip install fastapi uvicorn sqlalchemy httpx python-multipart bcrypt itsdangerous pyjwt
```

### 启动服务

```bash
cd /opt/bookkeeper
python3 -m uvicorn main:app --host 0.0.0.0 --port 8080
# 访问 http://localhost:8080
```

### systemd 部署

```ini
# /etc/systemd/system/bookkeeper.service
[Unit]
Description=BookKeeper
After=network.target ollama.service

[Service]
Type=simple
WorkingDirectory=/opt/bookkeeper
ExecStart=/usr/bin/python3 -m uvicorn main:app --host 0.0.0.0 --port 8080
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
systemctl enable --now bookkeeper.service
```

## 分类体系

### 支出分类
餐饮、交通、购物、娱乐、居住、医疗、教育、通讯、投资、人情、美容、其他

### 收入分类
工资、理财、红包、报销、兼职、奖金、退款、租金收入、生意、补贴、其他

分类基于关键词匹配（`ai.py` 中的 `_KEYWORD_MAP`），不调用 LLM。

## API 文档

### 认证

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/register` | 注册（username, password） |
| POST | `/api/login` | 登录（返回 Cookie + JWT） |
| POST | `/api/logout` | 登出 |
| GET | `/api/user` | 获取当前用户信息 |
| POST | `/api/wx-login` | 微信小程序登录 |

### 记账

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/records?month=YYYY-MM&page=1` | 查询记录（分页） |
| POST | `/api/records` | 新增记录（type, amount, category, note, date） |
| DELETE | `/api/records/{id}` | 删除记录 |
| DELETE | `/api/records/all` | 清空所有记录 |
| POST | `/api/import` | 导入账单（multipart/form-data，CSV/Excel） |

### 统计

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/stats/monthly?month=YYYY-MM` | 月度统计（收支总额 + 分类明细） |
| GET | `/api/stats/trend` | 近 6 个月收支趋势 |
| GET | `/api/categories` | 分类列表 |

### 预算

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/budget?month=YYYY-MM` | 获取月度预算 |
| POST | `/api/budget` | 设定月度预算（month, amount） |
| GET | `/api/ai/budget-advice?month=YYYY-MM` | 获取预算建议（纯计算） |

### AI 功能

| 方法 | 路径 | 说明 | 调 LLM |
|------|------|------|:------:|
| POST | `/api/ai/classify` | 自动分类（{"note":"打车"}） | 否 |
| POST | `/api/ai/smart-add` | 智能记账解析（{"text":"昨天打车30"}） | 否 |
| POST | `/api/ai/smart-add/confirm` | 确认智能记账结果并保存 | 否 |
| GET | `/api/ai/alerts` | 异常消费预警 | 否 |
| POST | `/api/ai/chat` | 账单问答（{"question":"这个月吃饭花了多少"}） | 否 |
| GET | `/api/ai/report?month=YYYY-MM` | AI 财务报告（一次性返回） | **是** |
| GET | `/api/ai/report/stream?month=YYYY-MM` | AI 财务报告（SSE 流式） | **是** |
| GET | `/api/ai/profile` | 消费习惯画像（一次性返回） | **是** |
| GET | `/api/ai/profile/stream` | 消费习惯画像（SSE 流式） | **是** |

> AI 报告和画像接口有限流：每用户每分钟 1 次。

## UI 布局

### Web 端（4 个 Tab）

- **首页**：收支概览 + 异常预警 + 预算进度 + 最近记录
- **记账**：智能记账（自然语言）+ 手动记账（备注自动分类）+ 账单导入
- **统计**：支出/收入饼图 + 趋势图 + 预算设定 + 账单问答
- **AI 助手**：AI 财务报告 + 消费习惯画像

### uni-app 端

与 Web 端功能一致，支持微信小程序 / App / H5 三端构建。

## 性能优化

- **流式输出**：AI 报告和画像使用 SSE 流式推送，思考阶段显示 loading，正文逐字显示
- **ollama 并行**：`OLLAMA_NUM_PARALLEL=3`，支持多用户同时推理
- **结果缓存**：LLM 生成结果缓存 1 小时（同月同数据不重复调用）
- **限流保护**：AI 接口每用户每分钟 1 次

## 开发

### uni-app 开发

```bash
cd uni-app
npm install
npm run dev:h5          # H5 开发
npm run dev:mp-weixin   # 微信小程序开发
npm run build:h5        # H5 构建
```

### uni-app 上线前置条件

- 微信小程序账号（个人/企业）
- 域名 + ICP 备案（小程序强制要求）
- HTTPS 证书
- 公网 HTTP 穿透

## License

MIT
