"""
Qwen3-ASR fine-tuning script.

Entry point:
    python -m src.asr.finetune --model_path Qwen/Qwen3-ASR-1.7B \
        --train_file train.jsonl --output_dir ./out

Input JSONL fields:
    audio   — local path to audio file
    text    — transcript string
    prompt  — optional system prompt (default: "")
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import librosa
import torch
from datasets import load_dataset
from transformers import (
    GenerationConfig,
    Trainer,
    TrainerCallback,
    TrainingArguments,
)

from qwen_asr.core.transformers_backend import (
    Qwen3ASRConfig,
    Qwen3ASRForConditionalGeneration,
    Qwen3ASRModel,
    Qwen3ASRProcessor,
)


# ---------------------------------------------------------------------------
# Model forward patch
# ---------------------------------------------------------------------------

def patch_outer_forward(model: Qwen3ASRForConditionalGeneration) -> None:
    """
    Route model.forward() through model.thinker.forward() so that HF Trainer
    can call the model without knowing about the thinker wrapper.
    Only patches once (guarded by _forward_patched).
    """
    cls = model.__class__
    if getattr(cls, "_forward_patched", False):
        return

    if not hasattr(model, "thinker") or not hasattr(model.thinker, "forward"):
        raise RuntimeError(
            "Cannot patch forward: model has no `.thinker.forward`. "
            "Your qwen3_asr model may be incompatible."
        )

    def forward(
        self,
        input_ids=None,
        attention_mask=None,
        input_features=None,
        feature_attention_mask=None,
        labels=None,
        **kwargs: Any,
    ):
        return self.thinker.forward(
            input_ids=input_ids,
            attention_mask=attention_mask,
            input_features=input_features,
            feature_attention_mask=feature_attention_mask,
            labels=labels,
            **kwargs,
        )

    cls.forward = forward
    cls._forward_patched = True


# ---------------------------------------------------------------------------
# Checkpoint utilities
# ---------------------------------------------------------------------------

_CKPT_RE = re.compile(r"^checkpoint-(\d+)$")


def find_latest_checkpoint(output_dir: str) -> Optional[str]:
    """Return path to the highest-numbered checkpoint-N subdirectory, or None."""
    if not output_dir or not os.path.isdir(output_dir):
        return None
    best_step: Optional[int] = None
    best_path: Optional[str] = None
    for name in os.listdir(output_dir):
        m = _CKPT_RE.match(name)
        if not m:
            continue
        step = int(m.group(1))
        path = os.path.join(output_dir, name)
        if os.path.isdir(path) and (best_step is None or step > best_step):
            best_step = step
            best_path = path
    return best_path


def copy_required_hf_files_for_qwen_asr(src_dir: str, dst_dir: str) -> None:
    """Copy HF config/tokenizer files from base model into a checkpoint directory."""
    os.makedirs(dst_dir, exist_ok=True)
    required = [
        "config.json",
        "generation_config.json",
        "preprocessor_config.json",
        "processor_config.json",
        "tokenizer_config.json",
        "tokenizer.json",
        "special_tokens_map.json",
        "chat_template.json",
        "merges.txt",
        "vocab.json",
    ]
    for fn in required:
        src = os.path.join(src_dir, fn)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(dst_dir, fn))


# ---------------------------------------------------------------------------
# Data utilities
# ---------------------------------------------------------------------------

def load_audio(path: str, sr: int = 16000):
    wav, _ = librosa.load(path, sr=sr, mono=True)
    return wav


def build_prefix_messages(prompt: str, audio_array: Any) -> list:
    return [
        {"role": "system", "content": prompt or ""},
        {"role": "user", "content": [{"type": "audio", "audio": audio_array}]},
    ]


def make_preprocess_fn_prefix_only(processor: Qwen3ASRProcessor):
    """Return a HF datasets .map() function that builds prefix text for each example."""
    def _preprocess(ex: Dict[str, Any]) -> Dict[str, Any]:
        prompt = ex.get("prompt", "")
        prefix_msgs = build_prefix_messages(prompt, None)
        prefix_text = processor.apply_chat_template(
            [prefix_msgs], add_generation_prompt=True, tokenize=False
        )[0]
        return {
            "prompt":      prompt,
            "audio":       ex["audio"],
            "target":      ex["text"],
            "prefix_text": prefix_text,
        }
    return _preprocess


# ---------------------------------------------------------------------------
# Data collator
# ---------------------------------------------------------------------------

@dataclass
class DataCollatorForQwen3ASRFinetuning:
    processor: Any
    sampling_rate: int = 16000

    def __call__(self, features: List[Dict[str, Any]]) -> Dict[str, torch.Tensor]:
        audio_paths   = [f["audio"]       for f in features]
        prefix_texts  = [f["prefix_text"] for f in features]
        targets       = [f["target"]      for f in features]

        eos = self.processor.tokenizer.eos_token or ""
        full_texts = [pfx + tgt + eos for pfx, tgt in zip(prefix_texts, targets)]
        audios = [load_audio(p, sr=self.sampling_rate) for p in audio_paths]

        full_inputs = self.processor(
            text=full_texts,
            audio=audios,
            return_tensors="pt",
            padding=True,
            truncation=False,
        )
        prefix_inputs = self.processor(
            text=prefix_texts,
            audio=audios,
            return_tensors="pt",
            padding=True,
            truncation=False,
        )

        prefix_lens = prefix_inputs["attention_mask"].sum(dim=1).tolist()
        labels = full_inputs["input_ids"].clone()
        for i, pl in enumerate(prefix_lens):
            labels[i, :pl] = -100

        pad_id = self.processor.tokenizer.pad_token_id
        if pad_id is not None:
            labels[labels == pad_id] = -100

        full_inputs["labels"] = labels
        return full_inputs


# ---------------------------------------------------------------------------
# Trainer subclass
# ---------------------------------------------------------------------------

class CastFloatInputsTrainer(Trainer):
    """Casts all floating-point inputs to model dtype before each forward pass."""

    def _prepare_inputs(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        inputs = super()._prepare_inputs(inputs)
        model_dtype = getattr(self.model, "dtype", None)
        if model_dtype is not None:
            for k, v in list(inputs.items()):
                if torch.is_tensor(v) and v.is_floating_point():
                    inputs[k] = v.to(dtype=model_dtype)
        return inputs


# ---------------------------------------------------------------------------
# Callback: ensure every saved checkpoint is directly loadable
# ---------------------------------------------------------------------------

class MakeEveryCheckpointInferableCallback(TrainerCallback):
    def __init__(self, base_model_path: str) -> None:
        self.base_model_path = base_model_path

    def on_save(self, args: TrainingArguments, state: Any, control: Any, **kwargs: Any):
        if args.process_index != 0:
            return control

        ckpt_dir = os.path.join(args.output_dir, f"checkpoint-{state.global_step}")
        if not os.path.isdir(ckpt_dir):
            ckpt_dir = kwargs.get("checkpoint", ckpt_dir)

        copy_required_hf_files_for_qwen_asr(self.base_model_path, ckpt_dir)
        return control


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser("Qwen3-ASR Fine-tuning")

    p.add_argument("--model_path",  type=str, default="Qwen/Qwen3-ASR-1.7B")
    p.add_argument("--train_file",  type=str, default="train.jsonl")
    p.add_argument("--eval_file",   type=str, default="")
    p.add_argument("--output_dir",  type=str, default="./qwen3-asr-finetuning-out")

    p.add_argument("--sr",          type=int,   default=16000)

    p.add_argument("--batch_size",  type=int,   default=32)
    p.add_argument("--grad_acc",    type=int,   default=4)
    p.add_argument("--lr",          type=float, default=2e-5)
    p.add_argument("--epochs",      type=float, default=1)
    p.add_argument("--log_steps",   type=int,   default=10)
    p.add_argument("--lr_scheduler_type", type=str,   default="linear")
    p.add_argument("--warmup_ratio",      type=float, default=0.02)

    p.add_argument("--num_workers",         type=int, default=4)
    p.add_argument("--pin_memory",          type=int, default=1)
    p.add_argument("--persistent_workers",  type=int, default=1)
    p.add_argument("--prefetch_factor",     type=int, default=2)

    p.add_argument("--save_strategy",   type=str, default="steps")
    p.add_argument("--save_steps",      type=int, default=200)
    p.add_argument("--save_total_limit", type=int, default=5)

    p.add_argument("--resume_from", type=str, default="")
    p.add_argument("--resume",      type=int, default=0)

    return p.parse_args()


def main() -> None:
    args = parse_args()

    if not args.train_file:
        raise ValueError(
            "TRAIN_FILE is required (json/jsonl). "
            "Needs fields: audio, text, optional prompt"
        )

    use_bf16 = (
        torch.cuda.is_available()
        and torch.cuda.get_device_capability(0)[0] >= 8
    )
    asr_wrapper = Qwen3ASRModel.from_pretrained(
        args.model_path,
        dtype=torch.bfloat16 if use_bf16 else torch.float16,
        device_map=None,
    )
    model     = asr_wrapper.model
    processor = asr_wrapper.processor

    patch_outer_forward(model)
    model.generation_config = GenerationConfig.from_model_config(model.config)

    raw_ds = load_dataset(
        "json",
        data_files={
            "train": args.train_file,
            **({"validation": args.eval_file} if args.eval_file else {}),
        },
    )
    ds = raw_ds.map(make_preprocess_fn_prefix_only(processor), num_proc=1)

    keep = {"prompt", "audio", "target", "prefix_text"}
    for split in ds.keys():
        drop = [c for c in ds[split].column_names if c not in keep]
        if drop:
            ds[split] = ds[split].remove_columns(drop)

    collator = DataCollatorForQwen3ASRFinetuning(
        processor=processor, sampling_rate=args.sr
    )

    training_args = TrainingArguments(
        output_dir=args.output_dir,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_acc,
        learning_rate=args.lr,
        num_train_epochs=args.epochs,
        logging_steps=args.log_steps,
        lr_scheduler_type=args.lr_scheduler_type,
        warmup_ratio=args.warmup_ratio,
        dataloader_num_workers=args.num_workers,
        dataloader_pin_memory=(args.pin_memory == 1),
        dataloader_persistent_workers=(args.persistent_workers == 1),
        dataloader_prefetch_factor=(
            args.prefetch_factor if args.num_workers > 0 else None
        ),
        save_strategy=args.save_strategy,
        save_steps=args.save_steps,
        save_total_limit=args.save_total_limit,
        save_safetensors=True,
        eval_strategy="steps",
        eval_steps=args.save_steps,
        do_eval=bool(args.eval_file),
        bf16=use_bf16,
        fp16=not use_bf16,
        ddp_find_unused_parameters=False,
        remove_unused_columns=False,
        report_to="none",
    )

    trainer = CastFloatInputsTrainer(
        model=model,
        args=training_args,
        train_dataset=ds["train"],
        eval_dataset=ds.get("validation", None),
        data_collator=collator,
        tokenizer=processor.tokenizer,
        callbacks=[
            MakeEveryCheckpointInferableCallback(
                base_model_path=args.model_path
            )
        ],
    )

    resume_from = (args.resume_from or "").strip()
    if not resume_from and args.resume == 1:
        resume_from = find_latest_checkpoint(training_args.output_dir) or ""

    if resume_from:
        if trainer.args.process_index == 0:
            print(f"[resume] resume_from_checkpoint = {resume_from}")
        trainer.train(resume_from_checkpoint=resume_from)
    else:
        trainer.train()


if __name__ == "__main__":
    main()
