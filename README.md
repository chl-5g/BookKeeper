# BookKeeper 智小账

个人记账应用，支持 AI 自动分类和支付宝/微信账单 CSV 导入。

## 技术栈

- **后端**：FastAPI + SQLite + SQLAlchemy
- **前端**：Vue 3 (CDN) + ECharts
- **AI 分类**：ollama qwen3:14b 本地推理
- **部署**：systemd 服务

## 功能

- 手动记账：输入备注自动识别分类（餐饮/交通/购物等）
- CSV 导入：支持支付宝（GBK）和微信支付（UTF-8）账单批量导入
- 统计图表：饼图（分类占比）+ 折线图（月度趋势）
- 移动端适配

## 快速启动

```bash
pip install fastapi uvicorn sqlalchemy httpx python-multipart
cd /opt/bookkeeper && python3 main.py
# 访问 http://localhost:8080
```

## API

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | /api/records | 查询记录（?month=YYYY-MM） |
| POST | /api/records | 新增记录 |
| DELETE | /api/records/{id} | 删除记录 |
| GET | /api/stats/monthly | 月度统计（?month=YYYY-MM） |
| GET | /api/stats/trend | 近 6 个月趋势 |
| GET | /api/categories | 分类列表 |
| POST | /api/ai/classify | AI 分类（{"note":"打车"}） |
| POST | /api/import | 导入 CSV 账单（multipart/form-data） |
