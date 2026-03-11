#!/usr/bin/env python3
"""
BookKeeper Qwen3-4B QLoRA 微调训练脚本
基座: unsloth/Qwen3-4B-bnb-4bit
配置: config.yaml
复用环境: /opt/quant-llm/finetune-env
"""

import json
import os
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
DATA_FILE = os.path.join(SCRIPT_DIR, cfg["data"]["output_file"])
OUTPUT_DIR = os.path.join(SCRIPT_DIR, cfg["paths"]["output_dir"])
SEED = cfg["training"]["seed"]
EVAL_RATIO = cfg["training"]["eval_ratio"]

# ============================================================
# 1. 加载模型
# ============================================================
from unsloth import FastLanguageModel

print("=" * 60)
print("BookKeeper Qwen3-4B QLoRA 微调")
print("=" * 60)
print(f"\n1. 加载基座模型: {MODEL_NAME}")
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=MODEL_NAME,
    max_seq_length=MAX_SEQ_LENGTH,
    load_in_4bit=True,
)

# ============================================================
# 2. 配置 LoRA
# ============================================================
print("2. 配置 LoRA 适配器...")
lcfg = cfg["lora"]
model = FastLanguageModel.get_peft_model(
    model,
    r=lcfg["r"],
    target_modules=lcfg["target_modules"],
    lora_alpha=lcfg["alpha"],
    lora_dropout=lcfg["dropout"],
    bias="none",
    use_gradient_checkpointing="unsloth",
    use_rslora=lcfg.get("use_rslora", True),
    random_state=SEED,
)

trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
total = sum(p.numel() for p in model.parameters())
print(f"   可训练参数: {trainable:,} / {total:,} ({trainable/total*100:.2f}%)")

# ============================================================
# 3. 加载数据
# ============================================================
from datasets import Dataset

print(f"3. 加载训练数据: {DATA_FILE}")
records = []
with open(DATA_FILE, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        records.append(json.loads(line))

print(f"   总计 {len(records)} 条")


def format_chatml(record):
    messages = record["messages"]
    text = ""
    for msg in messages:
        role = msg["role"]
        content = msg["content"]
        text += f"<|im_start|>{role}\n{content}<|im_end|>\n"
    text += "<|im_start|>assistant\n"
    return text


texts = [format_chatml(r) for r in records]
task_types = [r.get("task_type", "report") for r in records]
full_dataset = Dataset.from_dict({"text": texts, "task_type": task_types})

# 分层抽样
from collections import Counter
from datasets import ClassLabel

type_counts = Counter(task_types)
print(f"   任务分布: {dict(type_counts)}")

unique_types = sorted(type_counts.keys())
if len(unique_types) > 1:
    full_dataset = full_dataset.cast_column(
        "task_type", ClassLabel(names=unique_types)
    )
    split = full_dataset.train_test_split(
        test_size=EVAL_RATIO, seed=SEED, stratify_by_column="task_type"
    )
else:
    split = full_dataset.train_test_split(test_size=EVAL_RATIO, seed=SEED)

dataset = split["train"].remove_columns("task_type")
eval_dataset = split["test"].remove_columns("task_type")
print(f"   训练集: {len(dataset)} 条，验证集: {len(eval_dataset)} 条")

# ============================================================
# 4. 训练
# ============================================================
from trl import SFTTrainer
from transformers import TrainingArguments, EarlyStoppingCallback

print("4. 开始训练...")
print("=" * 60)

tcfg = cfg["training"]
trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset,
    eval_dataset=eval_dataset,
    args=TrainingArguments(
        output_dir=OUTPUT_DIR,
        per_device_train_batch_size=tcfg["batch_size"],
        gradient_accumulation_steps=tcfg["gradient_accumulation_steps"],
        warmup_steps=tcfg["warmup_steps"],
        num_train_epochs=tcfg["num_train_epochs"],
        learning_rate=tcfg["learning_rate"],
        fp16=False,
        bf16=tcfg["bf16"],
        logging_steps=tcfg["logging_steps"],
        save_steps=tcfg["save_steps"],
        save_total_limit=tcfg["save_total_limit"],
        eval_steps=tcfg["eval_steps"],
        eval_strategy="steps",
        optim=tcfg["optim"],
        lr_scheduler_type=tcfg["lr_scheduler"],
        seed=SEED,
        logging_dir=os.path.join(OUTPUT_DIR, "logs"),
        report_to="none",
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
    ),
    callbacks=[EarlyStoppingCallback(
        early_stopping_patience=tcfg["early_stopping_patience"],
    )],
    max_seq_length=MAX_SEQ_LENGTH,
    dataset_text_field="text",
    packing=True,
)

import torch
print(f"训练前 GPU 显存: {torch.cuda.memory_allocated()/1e9:.1f}GB / "
      f"{torch.cuda.get_device_properties(0).total_memory/1e9:.1f}GB")

# 自动从最新 checkpoint 恢复
import glob as _glob
checkpoints = sorted(
    _glob.glob(os.path.join(OUTPUT_DIR, "checkpoint-*")),
    key=lambda x: int(x.split("-")[-1])
)
resume_ckpt = checkpoints[-1] if checkpoints else None
if resume_ckpt:
    print(f"从 {resume_ckpt} 恢复训练...")
trainer_stats = trainer.train(resume_from_checkpoint=resume_ckpt)

# ============================================================
# 5. 保存
# ============================================================
print("\n" + "=" * 60)
print("5. 保存模型...")
model.save_pretrained(OUTPUT_DIR)
tokenizer.save_pretrained(OUTPUT_DIR)

print(f"\n训练完成！")
print(f"  训练时长: {trainer_stats.metrics['train_runtime']:.0f} 秒")
print(f"  训练损失: {trainer_stats.metrics['train_loss']:.4f}")
print(f"  模型保存: {OUTPUT_DIR}")

# 保存训练日志
log_file = os.path.join(OUTPUT_DIR, "training_log.txt")
with open(log_file, "w", encoding="utf-8") as lf:
    lf.write("=" * 60 + "\n")
    lf.write("BookKeeper Qwen3-4B 训练日志\n")
    lf.write("=" * 60 + "\n\n")
    lf.write(f"模型: {MODEL_NAME}\n")
    lf.write(f"LoRA: r={lcfg['r']}, alpha={lcfg['alpha']}, rslora={lcfg.get('use_rslora')}\n")
    lf.write(f"训练集: {len(dataset)} 条，验证集: {len(eval_dataset)} 条\n")
    lf.write(f"Epochs: {tcfg['num_train_epochs']}, LR: {tcfg['learning_rate']}\n\n")
    for entry in trainer.state.log_history:
        lf.write(json.dumps(entry, ensure_ascii=False) + "\n")
    lf.write(f"\n最终指标:\n")
    for k, v in trainer_stats.metrics.items():
        lf.write(f"  {k}: {v}\n")
print(f"  训练日志: {log_file}")
