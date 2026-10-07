#!/usr/bin/env python3
"""Compatibility entry point for the Reddit comment pre-labeling package.

Implementation lives in the :mod:`prelabeling` package. Existing commands such
as `python3 annotate_comments.py ...` remain unchanged.
"""

from prelabeling.cli import main, parse_args
from prelabeling.client import chat, endpoint_for, extract_json_object, post_json
from prelabeling.config import (
    ALIYUN_API_KEY_ENV,
    ALIYUN_BASE_URL,
    ALIYUN_MODEL,
    AnnotationError,
    ClientConfig,
    DEFAULT_BASE_URL,
    DEFAULT_INPUT,
    DEFAULT_MODEL,
    DEFAULT_OUTPUT,
    PROMPT_VERSION,
    utc_now,
)
from prelabeling.mechanics import (
    TOKEN_RE,
    URL_RE,
    mattr,
    mechanical_values,
    round4,
    rounded,
    split_paragraphs,
    syllables_in_token,
    tokenize,
)
from prelabeling.lexical import (
    FUNCTION_WORD_VERSION,
    G1_CATEGORIES,
    LEXICON_VERSION,
    TokenAnalysis,
    analyze_tokens,
    frequency_metrics,
    g1_metrics,
    lexical_resource_status,
    lexical_values,
    load_lexical_resources,
)
from prelabeling.pipeline import annotate_one, error_record
from prelabeling.prompts import PART_I_SYSTEM, PART_II_SYSTEM
from prelabeling.schemas import (
    GO_EMOTIONS,
    INTEGER,
    NULL,
    NUMBER_OR_NULL,
    PART_I_KEYS,
    PART_I_SCHEMA,
    PART_II_KEYS,
    PART_II_SCHEMA,
    STRING,
    STRING_OR_NULL,
    object_schema,
)
from prelabeling.storage import (
    compact_json,
    completed_lines,
    format_output_record,
    load_jsonl,
    load_output_records,
)
from prelabeling.validation import (
    require_enum,
    require_exact_keys,
    require_int,
    require_number_or_none,
    require_optional_span,
    require_spans,
    require_string_list,
    set_formula_fields,
    validate_part_i,
    validate_part_ii,
)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AnnotationError, OSError) as exc:
        print(f"fatal: {exc}", file=__import__("sys").stderr)
        raise SystemExit(2)
