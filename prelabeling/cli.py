"""Command-line argument parsing and concurrent batch execution."""

from __future__ import annotations

import argparse
import concurrent.futures
import os
import sys
import threading
from pathlib import Path
from typing import Any, Mapping, Sequence

from .config import (
    ALIYUN_API_KEY_ENV,
    ALIYUN_BASE_URL,
    ALIYUN_MODEL,
    AnnotationError,
    ClientConfig,
    DEFAULT_BASE_URL,
    DEFAULT_INPUT,
    DEFAULT_MODEL,
    DEFAULT_OUTPUT,
)
from .pipeline import annotate_one, error_record
from .storage import completed_lines, format_output_record, load_jsonl


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="按 Reddit_I/II.pdf 对 JSONL 评论进行大模型预标注")
    parser.add_argument("--input", default=DEFAULT_INPUT, type=Path)
    parser.add_argument("--output", default=DEFAULT_OUTPUT, type=Path)
    parser.add_argument("--text-field", default="body")
    parser.add_argument(
        "--provider",
        choices=("default", "aliyun"),
        default="default",
        help="模型服务预设；aliyun 使用 DashScope OpenAI 兼容接口",
    )
    parser.add_argument("--base-url", default=None, help="覆盖所选 provider 的 API 地址")
    parser.add_argument("--model", default=None, help="覆盖所选 provider 的模型名")
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--max-tokens", type=int, default=8192)
    parser.add_argument("--retries", type=int, default=2, help="首次请求失败后的重试次数")
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--stop-on-error", action="store_true")
    parser.add_argument(
        "--no-response-format", action="store_true",
        help="禁用 JSON Schema/JSON Object 结构化输出，仅使用提示词约束",
    )
    parser.add_argument(
        "--api-key-env",
        default=None,
        help="API key 环境变量名；aliyun 默认使用 DASHSCOPE_API_KEY",
    )
    args = parser.parse_args(argv)
    if args.provider == "aliyun":
        args.base_url = args.base_url or ALIYUN_BASE_URL
        args.model = args.model or ALIYUN_MODEL
        args.api_key_env = args.api_key_env or ALIYUN_API_KEY_ENV
    else:
        args.base_url = args.base_url or DEFAULT_BASE_URL
        args.model = args.model or DEFAULT_MODEL
    if args.concurrency < 1 or args.retries < 0 or args.max_tokens < 1 or args.timeout <= 0:
        parser.error("concurrency/max-tokens/timeout 必须为正数，retries 不能为负")
    if args.limit is not None and args.limit < 1:
        parser.error("limit 必须为正数")
    if args.input.resolve() == args.output.resolve():
        parser.error("output 不能覆盖 input")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    api_key = os.environ.get(args.api_key_env) if args.api_key_env else None
    if args.provider == "aliyun" and not api_key:
        raise AnnotationError(
            f"使用 aliyun provider 时必须设置环境变量 {args.api_key_env}"
        )
    config = ClientConfig(
        base_url=args.base_url,
        model=args.model,
        timeout=args.timeout,
        max_tokens=args.max_tokens,
        retries=args.retries,
        response_format=not args.no_response_format,
        api_key=api_key,
    )
    rows = load_jsonl(args.input)
    if args.limit is not None:
        rows = rows[: args.limit]
    done = completed_lines(args.output) if args.resume else set()
    pending = [(line_no, row) for line_no, row in rows if line_no not in done]
    if args.output.exists() and not args.resume:
        raise AnnotationError(f"输出文件已存在: {args.output}（使用 --resume 或换一个路径）")
    args.output.parent.mkdir(parents=True, exist_ok=True)

    write_lock = threading.Lock()
    mode = "a" if args.resume else "x"
    with args.output.open(mode, encoding="utf-8") as output_handle:
        def work(item: tuple[int, dict[str, Any]]) -> dict[str, Any]:
            line_no, record = item
            try:
                return annotate_one(line_no, record, args.text_field, config)
            except Exception as exc:
                if args.stop_on_error:
                    raise
                return error_record(line_no, record, config, exc)

        with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            for result in pool.map(work, pending):
                with write_lock:
                    output_handle.write(format_output_record(result) + "\n")
                    output_handle.flush()
                meta = result["_prelabel_meta"]
                print(
                    f"[{meta['source_line']}] {meta['status']}",
                    file=sys.stderr,
                    flush=True,
                )
    return 0
