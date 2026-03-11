import re
import httpx

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen3:14b"

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
