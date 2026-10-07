"""Validation and deterministic normalization of model annotations."""

from __future__ import annotations

import math
from decimal import Decimal
from typing import Any, Iterable, Mapping

from .config import AnnotationError
from .mechanics import round4, rounded, tokenize
from .schemas import GO_EMOTIONS, PART_I_KEYS, PART_II_KEYS


def require_exact_keys(value: Any, expected: Iterable[str], path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AnnotationError(f"{path} 必须是对象")
    expected_set = set(expected)
    actual = set(value)
    if actual != expected_set:
        raise AnnotationError(
            f"{path} 字段不符: missing={sorted(expected_set-actual)}, extra={sorted(actual-expected_set)}"
        )
    return value


def require_int(value: Any, low: int, high: int | None, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise AnnotationError(f"{path} 必须是整数")
    if value < low or (high is not None and value > high):
        raise AnnotationError(f"{path} 超出范围")
    return value


def require_number_or_none(value: Any, path: str) -> None:
    if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))):
        raise AnnotationError(f"{path} 必须是数值或 null")
    if isinstance(value, float) and not math.isfinite(value):
        raise AnnotationError(f"{path} 不能是 NaN/Infinity")


def require_enum(value: Any, allowed: set[Any], path: str) -> None:
    if value not in allowed:
        raise AnnotationError(f"{path} 不在允许集合中: {value!r}")


def require_string_list(value: Any, path: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise AnnotationError(f"{path} 必须是字符串数组")
    return value


def require_spans(spans: Any, text: str, path: str) -> None:
    """Validate only the container type; source-text matching is intentionally disabled."""
    require_string_list(spans, path)


def require_optional_span(span: Any, text: str, path: str) -> None:
    if span is not None and not isinstance(span, str):
        raise AnnotationError(f"{path} 必须为字符串或 null")


def set_formula_fields(part: dict[str, Any], fixed: Mapping[str, Any], model: str) -> None:
    """Enforce mechanical values and PDF formulas after contextual analysis."""
    n1 = fixed["N1"]
    part["N1"]["word_count"] = n1["word_count"]
    part["N1"]["tokens"] = n1["tokens"]
    part["O1"] = dict(fixed["O1"])
    part["D2"] = dict(fixed["D2"])
    w = n1["word_count"]

    part["O2"]["total"] = sum(part["O2"]["counts"].values())
    c = part["Y1"]["clause_count"]
    parser_version = "llm_contextual:" + model
    part["Y1"].update(
        word_count=w,
        MLC=None if c == 0 else round4(Decimal(w) / Decimal(c)),
        parser_version=parser_version,
        insufficient=c < 2,
    )
    part["Y2"]["clause_count"] = c
    dc = part["Y2"]["dependent_clause_count"]
    part["Y2"].update(
        DC_C=None if c == 0 else round4(Decimal(dc) / Decimal(c)),
        parser_version=parser_version,
        insufficient=c < 2,
    )

    part["W1"] = dict(fixed["W1"])
    part["W2"] = dict(fixed["W2"])
    cw = part["D1"]["content_word_count"]
    part["D1"].update(
        word_count=w,
        lexical_density=None if w == 0 else round4(Decimal(cw) / Decimal(w)),
        tagger_version="llm_contextual:" + model,
    )

    c2_counts = part["C2"]["counts"]
    k = sum(c2_counts.values())
    part["C2"].update(
        connective_count=k, word_count=w,
        per_100_words=None if w == 0 else round4(Decimal(k) / Decimal(w) * 100),
        lexicon_version="pdf_i_c2_core_v1",
    )
    p2_counts = part["P2"]["unit_counts"]
    units = sum(p2_counts.values())
    part["P2"].update(
        paralinguistic_units=units, word_count=w,
        per_100_words=round4(Decimal(units) / Decimal(max(w, 1)) * 100),
    )
    scores = part["C1"]["pair_scores"]
    valid_scores = [score for score in scores if score is not None]
    part["C1"]["mean_adjacent_overlap"] = (
        round4(Decimal(str(sum(valid_scores))) / Decimal(len(valid_scores))) if valid_scores else None
    )
    part["C1"]["sentence_count"] = part["N2"]["sentence_count"]
    part["P1"]["labels"] = list(
        dict.fromkeys(item["type"] for item in part["P1"]["items"])
    )

    s = part["N2"]["sentence_count"]
    syllables = fixed["F1_syllable_count"]
    reading_ease = None
    if w > 0 and s > 0:
        reading_ease = rounded(
            Decimal("206.835")
            - Decimal("1.015") * Decimal(w) / Decimal(s)
            - Decimal("84.6") * Decimal(syllables) / Decimal(w),
            2,
        )
    part["F1"] = {
        "word_count": w, "sentence_count": s, "syllable_count": syllables,
        "reading_ease": reading_ease, "short_text": w < 100,
    }
    part["G1"] = {
        "word_count": w,
        "rates_pct": {name: None for name in (
            "article", "preposition", "personal_pronoun", "impersonal_pronoun",
            "auxiliary_verb", "conjunction", "adverb", "negation",
        )},
        "CDI": None, "lexicon_version": None,
        "short_text": w < 50, "status": "lexicon_required",
    }


def validate_part_i(part: dict[str, Any], text: str) -> None:
    require_exact_keys(part, PART_I_KEYS, "part_i")
    field_keys = {
        "N1": ("word_count", "tokens", "language_status"),
        "N2": ("sentence_count", "sentences"),
        "O1": ("paragraph_count", "paragraphs"),
        "O2": ("counts", "total"),
        "Y1": ("word_count", "clause_count", "MLC", "parser_version", "insufficient"),
        "Y2": ("dependent_clause_count", "clause_count", "DC_C", "parser_version", "insufficient"),
        "W1": ("matched", "oov", "coverage", "mean_zipf", "lexicon_version", "status"),
        "W2": ("low_frequency_count", "matched", "coverage", "low_frequency_ratio"),
        "D1": ("content_word_count", "word_count", "lexical_density", "tagger_version"),
        "D2": ("token_count", "window_size", "window_ttr", "MATTR", "short_text"),
        "C1": ("pair_scores", "mean_adjacent_overlap", "sentence_count"),
        "C2": ("counts", "connective_count", "word_count", "per_100_words", "lexicon_version"),
        "P1": ("items", "labels"),
        "P2": ("unit_counts", "paralinguistic_units", "word_count", "per_100_words"),
        "F1": ("word_count", "sentence_count", "syllable_count", "reading_ease", "short_text"),
        "G1": ("word_count", "rates_pct", "CDI", "lexicon_version", "short_text", "status"),
    }
    for name, keys in field_keys.items():
        require_exact_keys(part[name], keys, f"part_i.{name}")

    require_enum(part["N1"]["language_status"], {"english_dominant", "non_english_dominant"}, "N1.language_status")
    require_int(part["N2"]["sentence_count"], 0, None, "N2.sentence_count")
    sentences = require_string_list(part["N2"]["sentences"], "N2.sentences")
    if len(sentences) != part["N2"]["sentence_count"]:
        raise AnnotationError("N2 sentence_count 与 sentences 长度不一致")
    require_spans(sentences, text, "N2.sentences")

    count_specs = {
        "O2.counts": (part["O2"]["counts"], {"list", "quote", "code", "link", "edit"}),
        "C2.counts": (part["C2"]["counts"], {"additive", "adversative", "causal", "temporal"}),
        "P2.unit_counts": (part["P2"]["unit_counts"], {"emoji_emoticon", "repeated_punctuation", "expressive_caps", "letter_lengthening", "stage_action_sound"}),
    }
    for path, (counts, keys) in count_specs.items():
        require_exact_keys(counts, keys, path)
        for key, value in counts.items():
            require_int(value, 0, None, f"{path}.{key}")

    c = require_int(part["Y1"]["clause_count"], 0, None, "Y1.clause_count")
    dc = require_int(part["Y2"]["dependent_clause_count"], 0, None, "Y2.dependent_clause_count")
    if dc > c:
        raise AnnotationError("Y2 dependent_clause_count 不能大于 clause_count")
    cw = require_int(part["D1"]["content_word_count"], 0, None, "D1.content_word_count")
    if cw > len(tokenize(text)):
        raise AnnotationError("D1 content_word_count 不能大于 word_count")

    matched = require_int(part["W1"]["matched"], 0, None, "W1.matched")
    oov = require_int(part["W1"]["oov"], 0, None, "W1.oov")
    require_number_or_none(part["W1"]["coverage"], "W1.coverage")
    require_number_or_none(part["W1"]["mean_zipf"], "W1.mean_zipf")
    require_enum(part["W1"]["status"], {"ok"}, "W1.status")
    if not isinstance(part["W1"]["lexicon_version"], str) or not part["W1"]["lexicon_version"]:
        raise AnnotationError("W1.lexicon_version 必须是非空字符串")
    expected_coverage = None if matched + oov == 0 else round4(Decimal(matched) / Decimal(matched + oov))
    if part["W1"]["coverage"] != expected_coverage:
        raise AnnotationError("W1.coverage 与 matched/oov 不一致")
    if (matched == 0) != (part["W1"]["mean_zipf"] is None):
        raise AnnotationError("W1.mean_zipf 与 matched 不一致")

    low = require_int(part["W2"]["low_frequency_count"], 0, None, "W2.low_frequency_count")
    w2_matched = require_int(part["W2"]["matched"], 0, None, "W2.matched")
    require_number_or_none(part["W2"]["coverage"], "W2.coverage")
    require_number_or_none(part["W2"]["low_frequency_ratio"], "W2.low_frequency_ratio")
    if w2_matched != matched or part["W2"]["coverage"] != expected_coverage:
        raise AnnotationError("W2 matched/coverage 必须与 W1 一致")
    if low > matched:
        raise AnnotationError("W2.low_frequency_count 不能大于 matched")
    expected_low_ratio = None if matched == 0 else round4(Decimal(low) / Decimal(matched))
    if part["W2"]["low_frequency_ratio"] != expected_low_ratio:
        raise AnnotationError("W2.low_frequency_ratio 与 low_frequency_count/matched 不一致")

    pair_scores = part["C1"]["pair_scores"]
    if not isinstance(pair_scores, list):
        raise AnnotationError("C1.pair_scores 必须是数组")
    expected_pairs = max(0, part["N2"]["sentence_count"] - 1)
    if len(pair_scores) != expected_pairs:
        raise AnnotationError("C1.pair_scores 长度必须等于 sentence_count-1")
    for index, score in enumerate(pair_scores):
        require_number_or_none(score, f"C1.pair_scores[{index}]")
        if score is not None and not 0 <= score <= 1:
            raise AnnotationError("C1 pair score 必须在 0..1")

    items = part["P1"]["items"]
    if not isinstance(items, list):
        raise AnnotationError("P1.items 必须是数组")
    allowed_p1 = {"emoji_emoticon", "repeated_punctuation", "expressive_caps", "letter_lengthening", "stage_action_sound"}
    for index, item in enumerate(items):
        require_exact_keys(item, ("type", "evidence"), f"P1.items[{index}]")
        require_enum(item["type"], allowed_p1, f"P1.items[{index}].type")
        if not isinstance(item["evidence"], str):
            raise AnnotationError(f"P1.items[{index}].evidence 必须是字符串")
    labels = require_string_list(part["P1"]["labels"], "P1.labels")
    if labels != list(dict.fromkeys(item["type"] for item in items)):
        raise AnnotationError("P1.labels 必须是 items 类别按首次出现去重的结果")


def validate_part_ii(part: dict[str, Any], text: str) -> None:
    require_exact_keys(part, PART_II_KEYS, "part_ii")
    field_keys = {
        "E1": ("valence", "evidence"), "E2": ("arousal", "evidence"),
        "E3": ("labels", "evidence"),
        "R1": ("level", "claim", "reasons", "warrant"),
        "R2": ("types", "evidence_spans"), "R3": ("source_level", "source_span"),
        "R4": ("level", "counterpoint", "response"),
        "S1": ("target", "stance", "evidence"),
        "K1": ("certainty", "proposition", "markers"),
        "T1": ("level", "mechanisms", "evidence"),
        "I1": ("communion", "evidence"), "I2": ("agency", "evidence"),
        "N1": ("type", "strength", "agent", "action", "evidence"),
        "P1": ("strategies", "evidence"),
        "P2": ("irony", "cue", "intended_meaning"),
        "P3": ("direction", "markers", "scope"),
    }
    for name, keys in field_keys.items():
        require_exact_keys(part[name], keys, f"part_ii.{name}")

    require_int(part["E1"]["valence"], -2, 2, "E1.valence")
    require_int(part["E2"]["arousal"], 0, 3, "E2.arousal")
    labels = require_string_list(part["E3"]["labels"], "E3.labels")
    if not labels or len(labels) != len(set(labels)) or not set(labels) <= GO_EMOTIONS:
        raise AnnotationError("E3.labels 为空、重复或含非法类别")
    if "neutral" in labels and len(labels) > 1:
        raise AnnotationError("E3 neutral 不能与明确情绪并列")

    for name in ("E1", "E2", "E3", "S1", "T1", "I1", "I2", "N1", "P1"):
        require_spans(part[name]["evidence"], text, f"{name}.evidence")
    require_spans(part["K1"]["markers"], text, "K1.markers")
    require_spans(part["P2"]["cue"], text, "P2.cue")
    require_spans(part["P3"]["markers"], text, "P3.markers")
    if part["E1"]["valence"] != 0 and not part["E1"]["evidence"]:
        raise AnnotationError("E1 非中性效价必须提供原文证据")
    if part["E2"]["arousal"] != 0 and not part["E2"]["evidence"]:
        raise AnnotationError("E2 非零唤醒必须提供原文证据")
    if labels != ["neutral"] and not part["E3"]["evidence"]:
        raise AnnotationError("E3 明确情绪必须提供原文证据")

    require_int(part["R1"]["level"], 0, 3, "R1.level")
    require_optional_span(part["R1"]["claim"], text, "R1.claim")
    require_spans(part["R1"]["reasons"], text, "R1.reasons")
    require_optional_span(part["R1"]["warrant"], text, "R1.warrant")
    if part["R1"]["level"] == 0 and (part["R1"]["claim"] is not None or part["R1"]["reasons"]):
        raise AnnotationError("R1 level=0 时不能有 claim/reasons")
    if part["R1"]["level"] >= 1 and part["R1"]["claim"] is None:
        raise AnnotationError("R1 level>=1 时必须有 claim")
    if part["R1"]["level"] >= 2 and not part["R1"]["reasons"]:
        raise AnnotationError("R1 level>=2 时必须有 reasons")

    r2_types = require_string_list(part["R2"]["types"], "R2.types")
    allowed_r2 = {"personal_experience", "example", "empirical_data", "documented_fact", "expert_or_institution", "logical_inference"}
    if len(r2_types) != len(set(r2_types)) or not set(r2_types) <= allowed_r2:
        raise AnnotationError("R2.types 含重复或非法类别")
    require_spans(part["R2"]["evidence_spans"], text, "R2.evidence_spans")

    require_int(part["R3"]["source_level"], 0, 3, "R3.source_level")
    require_optional_span(part["R3"]["source_span"], text, "R3.source_span")
    if (part["R3"]["source_level"] == 0) != (part["R3"]["source_span"] is None):
        raise AnnotationError("R3 source_level 与 source_span 不一致")
    require_int(part["R4"]["level"], 0, 3, "R4.level")
    require_optional_span(part["R4"]["counterpoint"], text, "R4.counterpoint")
    require_optional_span(part["R4"]["response"], text, "R4.response")
    if part["R4"]["level"] == 0 and (part["R4"]["counterpoint"] is not None or part["R4"]["response"] is not None):
        raise AnnotationError("R4 level=0 时 counterpoint/response 必须为 null")

    require_enum(part["S1"]["stance"], {"support", "oppose", "neutral", "mixed", "unclear"}, "S1.stance")
    if part["S1"]["target"] is not None and not isinstance(part["S1"]["target"], str):
        raise AnnotationError("S1.target 必须是字符串或 null")
    if part["S1"]["target"] is None and part["S1"]["stance"] != "unclear":
        raise AnnotationError("S1.target=null 时 stance 必须为 unclear")
    if part["S1"]["target"] is not None and not part["S1"]["evidence"]:
        raise AnnotationError("S1 有明确目标时必须提供原文证据")
    require_int(part["K1"]["certainty"], 0, 5, "K1.certainty")
    if part["K1"]["proposition"] is not None and not isinstance(part["K1"]["proposition"], str):
        raise AnnotationError("K1.proposition 必须是字符串或 null")
    if part["K1"]["certainty"] == 0 and part["K1"]["proposition"] is not None:
        raise AnnotationError("K1 certainty=0 时 proposition 必须为 null")

    if part["T1"]["level"] is not None:
        require_int(part["T1"]["level"], 0, 3, "T1.level")
    mechanisms = require_string_list(part["T1"]["mechanisms"], "T1.mechanisms")
    if len(mechanisms) != len(set(mechanisms)) or not set(mechanisms) <= {"insult", "obscenity", "ridicule", "hostility", "identity_harm", "threat"}:
        raise AnnotationError("T1.mechanisms 含重复或非法类别")
    if part["T1"]["level"] in (1, 2, 3) and (not mechanisms or not part["T1"]["evidence"]):
        raise AnnotationError("T1 level>0 时必须提供机制和原文证据")
    if part["T1"]["level"] == 0 and (mechanisms or part["T1"]["evidence"]):
        raise AnnotationError("T1 level=0 时 mechanisms/evidence 必须为空")
    require_int(part["I1"]["communion"], -2, 2, "I1.communion")
    require_int(part["I2"]["agency"], -2, 2, "I2.agency")

    require_enum(part["N1"]["type"], {"none", "recommendation", "permission", "obligation", "prohibition", "entitlement"}, "N1.type")
    require_int(part["N1"]["strength"], 0, 3, "N1.strength")
    if part["N1"]["type"] == "none" and (part["N1"]["strength"] != 0 or part["N1"]["agent"] is not None or part["N1"]["action"] is not None):
        raise AnnotationError("规范模态 N1 type=none 时 strength=0 且 agent/action=null")
    for key in ("agent", "action"):
        if part["N1"][key] is not None and not isinstance(part["N1"][key], str):
            raise AnnotationError(f"N1.{key} 必须是字符串或 null")
    if part["N1"]["type"] != "none" and (
        part["N1"]["strength"] == 0
        or part["N1"]["action"] is None
        or not part["N1"]["evidence"]
    ):
        raise AnnotationError("规范模态 N1 非 none 时必须给出强度、行为和证据；主体仅在可抽取时填写")

    strategies = require_string_list(part["P1"]["strategies"], "P1.strategies")
    if len(strategies) != len(set(strategies)) or not set(strategies) <= {"gratitude", "apology", "deference", "solidarity", "hedging", "indirect_request", "face_threat"}:
        raise AnnotationError("P1.strategies 含重复或非法类别")
    require_enum(part["P2"]["irony"], {"present", "absent", "uncertain"}, "P2.irony")
    if part["P2"]["intended_meaning"] is not None and not isinstance(part["P2"]["intended_meaning"], str):
        raise AnnotationError("P2.intended_meaning 必须是字符串或 null")
    if part["P2"]["irony"] == "absent" and (part["P2"]["cue"] or part["P2"]["intended_meaning"] is not None):
        raise AnnotationError("P2 absent 时 cue=[] 且 intended_meaning=null")
    if part["P2"]["irony"] == "present" and (not part["P2"]["cue"] or part["P2"]["intended_meaning"] is None):
        raise AnnotationError("P2 present 时必须给出 cue 和 intended_meaning")
    require_enum(part["P3"]["direction"], {"upscale", "downscale", "mixed", "none"}, "P3.direction")
    if part["P3"]["scope"] is not None and not isinstance(part["P3"]["scope"], str):
        raise AnnotationError("P3.scope 必须是字符串或 null")
    if part["P3"]["direction"] == "none" and (part["P3"]["markers"] or part["P3"]["scope"] is not None):
        raise AnnotationError("P3 none 时 markers=[] 且 scope=null")
