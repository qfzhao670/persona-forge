"""Shared configuration and metadata helpers."""

from __future__ import annotations

import dataclasses
import datetime as dt
from pathlib import Path


DEFAULT_BASE_URL = "http://47.120.70.138:7113/v1"
DEFAULT_MODEL = "min-lab-v1"
ALIYUN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
ALIYUN_MODEL = "qwen3.8-flash"
ALIYUN_API_KEY_ENV = "DASHSCOPE_API_KEY"
DEFAULT_INPUT = Path("input/random_100_comments.jsonl")
DEFAULT_OUTPUT = Path("output/random_100_comments_prelabeled.jsonl")
PROMPT_VERSION = "reddit-pdf-v1.3-fixed-g1-cdi"


class AnnotationError(RuntimeError):
    pass


@dataclasses.dataclass(frozen=True)
class ClientConfig:
    base_url: str
    model: str
    timeout: float
    max_tokens: int
    retries: int
    response_format: bool
    api_key: str | None


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
