"""Per-comment orchestration for the two annotation passes."""

from __future__ import annotations

from typing import Any, Mapping

from .client import chat
from .config import AnnotationError, ClientConfig, PROMPT_VERSION, utc_now
from .lexical import lexical_resource_status, lexical_values
from .mechanics import mechanical_values
from .prompts import PART_I_SYSTEM, PART_II_SYSTEM
from .schemas import PART_I_SCHEMA, PART_II_SCHEMA
from .validation import set_formula_fields, validate_part_i, validate_part_ii


def annotate_one(
    source_line: int,
    record: Mapping[str, Any],
    text_field: str,
    config: ClientConfig,
) -> dict[str, Any]:
    text = record.get(text_field)
    if not isinstance(text, str):
        raise AnnotationError(f"第 {source_line} 行字段 {text_field!r} 不是字符串")
    fixed = mechanical_values(text)
    fixed.update(lexical_values(fixed["N1"]["tokens"]))
    part_i, usage_i, tries_i = chat(
        PART_I_SYSTEM,
        {"comment": text, "MECHANICAL_VALUES": fixed},
        config,
        validate_part_i,
        "reddit_part_i_annotation",
        PART_I_SCHEMA,
    )
    set_formula_fields(part_i, fixed, config.model)
    validate_part_i(part_i, text)
    part_ii, usage_ii, tries_ii = chat(
        PART_II_SYSTEM,
        {"comment": text},
        config,
        validate_part_ii,
        "reddit_part_ii_annotation",
        PART_II_SCHEMA,
    )
    output = dict(record)
    output["annotations"] = {"part_i": part_i, "part_ii": part_ii}
    output["_prelabel_meta"] = {
        "source_line": source_line,
        "status": "ok",
        "model": config.model,
        "base_url": config.base_url,
        "prompt_version": PROMPT_VERSION,
        "created_at": utc_now(),
        "attempts": {"part_i": tries_i, "part_ii": tries_ii},
        "usage": {"part_i": usage_i, "part_ii": usage_ii},
        "resource_status": {
            **lexical_resource_status(),
            "function_word_lexicon": "not_provided",
            "flesch_syllables": "fixed_fallback_heuristic",
        },
    }
    return output


def error_record(source_line: int, record: Mapping[str, Any], config: ClientConfig, exc: Exception) -> dict[str, Any]:
    output = dict(record)
    output["annotations"] = None
    output["_prelabel_meta"] = {
        "source_line": source_line,
        "status": "error",
        "model": config.model,
        "base_url": config.base_url,
        "prompt_version": PROMPT_VERSION,
        "created_at": utc_now(),
        "error": str(exc),
    }
    return output
