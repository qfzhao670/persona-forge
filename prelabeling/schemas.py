"""Strict JSON schemas and label vocabularies for model output."""

from __future__ import annotations

from typing import Any, Mapping


PART_I_KEYS = (
    "N1", "N2", "O1", "O2", "Y1", "Y2", "W1", "W2", "D1", "D2",
    "C1", "C2", "P1", "P2", "F1", "G1",
)
PART_II_KEYS = (
    "E1", "E2", "E3", "R1", "R2", "R3", "R4", "S1", "K1", "T1",
    "I1", "I2", "N1", "P1", "P2", "P3",
)
GO_EMOTIONS = {
    "admiration", "amusement", "anger", "annoyance", "approval", "caring",
    "confusion", "curiosity", "desire", "disappointment", "disapproval",
    "disgust", "embarrassment", "excitement", "fear", "gratitude", "grief",
    "joy", "love", "nervousness", "optimism", "pride", "realization",
    "relief", "remorse", "sadness", "surprise", "neutral",
}


def object_schema(properties: Mapping[str, Any]) -> dict[str, Any]:
    """Build an object schema compatible with strict structured output."""
    return {
        "type": "object",
        "properties": dict(properties),
        "required": list(properties),
        "additionalProperties": False,
    }


STRING = {"type": "string"}
INTEGER = {"type": "integer"}
NUMBER_OR_NULL = {"type": ["number", "null"]}
STRING_OR_NULL = {"type": ["string", "null"]}
NULL = {"type": "null"}


PART_I_SCHEMA = object_schema({
    "N1": object_schema({
        "word_count": INTEGER,
        "tokens": {"type": "array", "items": STRING},
        "language_status": {"type": "string", "enum": ["english_dominant", "non_english_dominant"]},
    }),
    "N2": object_schema({
        "sentence_count": INTEGER,
        "sentences": {"type": "array", "items": STRING},
    }),
    "O1": object_schema({
        "paragraph_count": INTEGER,
        "paragraphs": {"type": "array", "items": STRING},
    }),
    "O2": object_schema({
        "counts": object_schema({name: INTEGER for name in ("list", "quote", "code", "link", "edit")}),
        "total": INTEGER,
    }),
    "Y1": object_schema({
        "word_count": INTEGER, "clause_count": INTEGER, "MLC": NUMBER_OR_NULL,
        "parser_version": STRING_OR_NULL, "insufficient": {"type": "boolean"},
    }),
    "Y2": object_schema({
        "dependent_clause_count": INTEGER, "clause_count": INTEGER, "DC_C": NUMBER_OR_NULL,
        "parser_version": STRING_OR_NULL, "insufficient": {"type": "boolean"},
    }),
    "W1": object_schema({
        "matched": NULL, "oov": NULL, "coverage": NULL, "mean_zipf": NULL,
        "lexicon_version": NULL, "status": {"type": "string", "enum": ["lexicon_required"]},
    }),
    "W2": object_schema({
        "low_frequency_count": NULL, "matched": NULL, "coverage": NULL, "low_frequency_ratio": NULL,
    }),
    "D1": object_schema({
        "content_word_count": INTEGER, "word_count": INTEGER,
        "lexical_density": NUMBER_OR_NULL, "tagger_version": STRING_OR_NULL,
    }),
    "D2": object_schema({
        "token_count": INTEGER, "window_size": INTEGER,
        "window_ttr": {"type": "array", "items": {"type": "number"}},
        "MATTR": NUMBER_OR_NULL, "short_text": {"type": "boolean"},
    }),
    "C1": object_schema({
        "pair_scores": {"type": "array", "items": NUMBER_OR_NULL},
        "mean_adjacent_overlap": NUMBER_OR_NULL, "sentence_count": INTEGER,
    }),
    "C2": object_schema({
        "counts": object_schema({name: INTEGER for name in ("additive", "adversative", "causal", "temporal")}),
        "connective_count": INTEGER, "word_count": INTEGER,
        "per_100_words": NUMBER_OR_NULL, "lexicon_version": STRING_OR_NULL,
    }),
    "P1": object_schema({
        "items": {
            "type": "array",
            "items": object_schema({
                "type": {"type": "string", "enum": [
                    "emoji_emoticon", "repeated_punctuation", "expressive_caps",
                    "letter_lengthening", "stage_action_sound",
                ]},
                "evidence": STRING,
            }),
        },
        "labels": {"type": "array", "items": {"type": "string", "enum": [
            "emoji_emoticon", "repeated_punctuation", "expressive_caps",
            "letter_lengthening", "stage_action_sound",
        ]}},
    }),
    "P2": object_schema({
        "unit_counts": object_schema({name: INTEGER for name in (
            "emoji_emoticon", "repeated_punctuation", "expressive_caps",
            "letter_lengthening", "stage_action_sound",
        )}),
        "paralinguistic_units": INTEGER, "word_count": INTEGER, "per_100_words": {"type": "number"},
    }),
    "F1": object_schema({
        "word_count": INTEGER, "sentence_count": INTEGER, "syllable_count": INTEGER,
        "reading_ease": NUMBER_OR_NULL, "short_text": {"type": "boolean"},
    }),
    "G1": object_schema({
        "word_count": INTEGER,
        "rates_pct": object_schema({name: NULL for name in (
            "article", "preposition", "personal_pronoun", "impersonal_pronoun",
            "auxiliary_verb", "conjunction", "adverb", "negation",
        )}),
        "CDI": NULL, "lexicon_version": NULL, "short_text": {"type": "boolean"},
        "status": {"type": "string", "enum": ["lexicon_required"]},
    }),
})

PART_II_SCHEMA = object_schema({
    "E1": object_schema({"valence": INTEGER, "evidence": {"type": "array", "items": STRING}}),
    "E2": object_schema({"arousal": INTEGER, "evidence": {"type": "array", "items": STRING}}),
    "E3": object_schema({
        "labels": {"type": "array", "items": {"type": "string", "enum": sorted(GO_EMOTIONS)}},
        "evidence": {"type": "array", "items": STRING},
    }),
    "R1": object_schema({
        "level": INTEGER, "claim": STRING_OR_NULL,
        "reasons": {"type": "array", "items": STRING}, "warrant": STRING_OR_NULL,
    }),
    "R2": object_schema({
        "types": {"type": "array", "items": {"type": "string", "enum": [
            "personal_experience", "example", "empirical_data", "documented_fact",
            "expert_or_institution", "logical_inference",
        ]}},
        "evidence_spans": {"type": "array", "items": STRING},
    }),
    "R3": object_schema({"source_level": INTEGER, "source_span": STRING_OR_NULL}),
    "R4": object_schema({
        "level": INTEGER, "counterpoint": STRING_OR_NULL, "response": STRING_OR_NULL,
    }),
    "S1": object_schema({
        "target": STRING_OR_NULL,
        "stance": {"type": "string", "enum": ["support", "oppose", "neutral", "mixed", "unclear"]},
        "evidence": {"type": "array", "items": STRING},
    }),
    "K1": object_schema({
        "certainty": INTEGER, "proposition": STRING_OR_NULL,
        "markers": {"type": "array", "items": STRING},
    }),
    "T1": object_schema({
        "level": {"type": ["integer", "null"]},
        "mechanisms": {"type": "array", "items": {"type": "string", "enum": [
            "insult", "obscenity", "ridicule", "hostility", "identity_harm", "threat",
        ]}},
        "evidence": {"type": "array", "items": STRING},
    }),
    "I1": object_schema({"communion": INTEGER, "evidence": {"type": "array", "items": STRING}}),
    "I2": object_schema({"agency": INTEGER, "evidence": {"type": "array", "items": STRING}}),
    "N1": object_schema({
        "type": {"type": "string", "enum": [
            "none", "recommendation", "permission", "obligation", "prohibition", "entitlement",
        ]},
        "strength": INTEGER, "agent": STRING_OR_NULL, "action": STRING_OR_NULL,
        "evidence": {"type": "array", "items": STRING},
    }),
    "P1": object_schema({
        "strategies": {"type": "array", "items": {"type": "string", "enum": [
            "gratitude", "apology", "deference", "solidarity", "hedging",
            "indirect_request", "face_threat",
        ]}},
        "evidence": {"type": "array", "items": STRING},
    }),
    "P2": object_schema({
        "irony": {"type": "string", "enum": ["present", "absent", "uncertain"]},
        "cue": {"type": "array", "items": STRING}, "intended_meaning": STRING_OR_NULL,
    }),
    "P3": object_schema({
        "direction": {"type": "string", "enum": ["upscale", "downscale", "mixed", "none"]},
        "markers": {"type": "array", "items": STRING}, "scope": STRING_OR_NULL,
    }),
})
