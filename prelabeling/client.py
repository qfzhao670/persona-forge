"""OpenAI-compatible HTTP client with structured-output fallback and retries."""

from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.request
from typing import Any, Mapping

from .config import AnnotationError, ClientConfig


def endpoint_for(base_url: str) -> str:
    value = base_url.rstrip("/")
    if value.endswith("/chat/completions"):
        return value
    return value + "/chat/completions"


def extract_json_object(text: str) -> Mapping[str, Any]:
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise AnnotationError("模型响应中没有可解析的 JSON 对象")


def post_json(url: str, payload: Mapping[str, Any], config: ClientConfig) -> Mapping[str, Any]:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if config.api_key:
        headers["Authorization"] = "Bearer " + config.api_key
    request = urllib.request.Request(
        url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers, method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=config.timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:2000]
        raise AnnotationError(f"HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise AnnotationError(f"请求失败: {exc}") from exc
    try:
        parsed = json.loads(raw)
        choice = parsed["choices"][0]["message"]
        content = choice.get("content")
        if isinstance(content, list):
            content = "".join(
                item.get("text", "") for item in content if isinstance(item, dict)
            )
        if not isinstance(content, str):
            raise TypeError("message.content 不是字符串")
        return {"content": content, "usage": parsed.get("usage")}
    except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
        raise AnnotationError(f"OpenAI 兼容响应格式无效: {exc}; body={raw[:1000]}") from exc


def chat(
    system_prompt: str,
    user_payload: Mapping[str, Any],
    config: ClientConfig,
    validator: Any,
    schema_name: str,
    response_schema: Mapping[str, Any],
) -> tuple[dict[str, Any], Mapping[str, Any] | None, int]:
    url = endpoint_for(config.base_url)
    last_error: Exception | None = None
    repair_note = ""
    format_mode: str | None = "json_schema" if config.response_format else None
    attempt = 0
    ordinary_failures = 0
    while ordinary_failures <= config.retries:
        attempt += 1
        user_text = (
            "/no_think\n"
            + repair_note
            + "COMMENT_JSON_AND_FIXED_VALUES:\n"
            + json.dumps(user_payload, ensure_ascii=False, separators=(",", ":"))
        )
        body: dict[str, Any] = {
            "model": config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
            "temperature": 0,
            "max_tokens": config.max_tokens,
            "stream": False,
        }
        if format_mode == "json_schema":
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "strict": True,
                    "schema": response_schema,
                },
            }
        elif format_mode == "json_object":
            body["response_format"] = {"type": "json_object"}
        try:
            response = post_json(url, body, config)
            result = dict(extract_json_object(str(response["content"])))
            validator(result, str(user_payload["comment"]))
            return result, response.get("usage"), attempt
        except Exception as exc:  # retry model, transport, JSON, and validation failures
            last_error = exc
            error_text = str(exc)
            if (
                format_mode is not None
                and ("HTTP 400" in error_text or "HTTP 422" in error_text)
            ):
                format_mode = "json_object" if format_mode == "json_schema" else None
                repair_note = ""
                continue
            ordinary_failures += 1
            repair_note = (
                "上一次输出未通过校验。请重新从原评论标注，并修正这个问题："
                + str(exc)[:1200]
                + "\n"
            )
            if ordinary_failures <= config.retries:
                time.sleep(min(8.0, (2 ** (attempt - 1)) + random.random()))
    raise AnnotationError(f"超过最大重试次数: {last_error}")
