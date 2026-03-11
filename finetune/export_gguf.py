#!/usr/bin/env python3
"""
导出 BookKeeper 微调模型为 GGUF 格式并导入 ollama
"""

import os
import subprocess
import warnings
warnings.filterwarnings("ignore")

import yaml

# ============================================================
# 配置
# ============================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(SCRIPT_DIR, "config.yaml"), "r") as f:
    cfg = yaml.safe_load(f)

MODEL_NAME = cfg["model"]["name"]
MAX_SEQ_LENGTH = cfg["model"]["max_seq_length"]
OUTPUT_DIR = os.path.join(SCRIPT_DIR, cfg["paths"]["output_dir"])
GGUF_METHOD = cfg["export"]["gguf_method"]
OLLAMA_MODEL_NAME = cfg["export"]["model_name"]
GGUF_DIR = os.path.join(OUTPUT_DIR, "gguf")

# ============================================================
# 1. 加载微调模型
# ============================================================
from unsloth import FastLanguageModel

print("=" * 60)
print("BookKeeper 模型导出")
print("=" * 60)

print(f"\n1. 加载微调模型: {OUTPUT_DIR}")
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=OUTPUT_DIR,
    max_seq_length=MAX_SEQ_LENGTH,
    load_in_4bit=True,
)

# ============================================================
# 2. 导出 GGUF
# ============================================================
print(f"\n2. 导出 GGUF ({GGUF_METHOD})...")
os.makedirs(GGUF_DIR, exist_ok=True)

model.save_pretrained_gguf(
    GGUF_DIR,
    tokenizer,
    quantization_method=GGUF_METHOD,
)

# 找到生成的 GGUF 文件
gguf_files = [f for f in os.listdir(GGUF_DIR) if f.endswith(".gguf")]
if not gguf_files:
    print("错误：未找到 GGUF 文件")
    exit(1)
gguf_path = os.path.join(GGUF_DIR, gguf_files[0])
gguf_size_mb = os.path.getsize(gguf_path) / 1e6
print(f"   GGUF 文件: {gguf_path} ({gguf_size_mb:.0f} MB)")

# ============================================================
# 3. 生成 Modelfile
# ============================================================
print("\n3. 生成 Modelfile...")
modelfile_path = os.path.join(OUTPUT_DIR, "Modelfile")
modelfile_content = f"""FROM {gguf_path}

SYSTEM "你是一个专业的个人财务顾问，擅长分析收支数据、生成月度报告和消费画像。你的输出必须包含 ### 标题分隔的多个段落，语言简洁友好。"

PARAMETER temperature 0.7
PARAMETER num_predict 800
PARAMETER stop <|im_end|>
"""

with open(modelfile_path, "w") as f:
    f.write(modelfile_content)
print(f"   Modelfile: {modelfile_path}")

# ============================================================
# 4. 导入 ollama
# ============================================================
print(f"\n4. 导入 ollama: {OLLAMA_MODEL_NAME}")
result = subprocess.run(
    ["ollama", "create", OLLAMA_MODEL_NAME, "-f", modelfile_path],
    capture_output=True, text=True,
)
if result.returncode == 0:
    print(f"   成功！模型名: {OLLAMA_MODEL_NAME}")
    print(f"   测试: ollama run {OLLAMA_MODEL_NAME} '你好'")
else:
    print(f"   失败: {result.stderr}")
    exit(1)

print(f"\n{'=' * 60}")
print("导出完成！接下来修改 ai.py 中的模型名即可使用。")
