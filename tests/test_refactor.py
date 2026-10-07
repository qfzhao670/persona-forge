"""Offline regression checks for the package split."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import annotate_comments
from prelabeling import mechanics, pipeline
from prelabeling.cli import main, parse_args
from prelabeling.config import (
    ALIYUN_API_KEY_ENV,
    ALIYUN_BASE_URL,
    ALIYUN_MODEL,
    AnnotationError,
    ClientConfig,
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
)
from prelabeling.lexical import (
    LexicalResources,
    TokenAnalysis,
    analyze_tokens,
    frequency_metrics,
    load_lexical_resources,
)
from prelabeling.storage import format_output_record, load_output_records


class MechanicsTests(unittest.TestCase):
    def test_tokenize_normalizes_apostrophes_and_removes_urls(self) -> None:
        text = "We’re testing https://example.com and DON'T stop."
        self.assertEqual(
            mechanics.tokenize(text),
            ["we're", "testing", "and", "don't", "stop"],
        )

    def test_mechanical_values_cover_empty_and_short_text(self) -> None:
        empty = mechanics.mechanical_values("")
        self.assertEqual(empty["N1"], {"word_count": 0, "tokens": []})
        self.assertIsNone(empty["D2"]["MATTR"])

        short = mechanics.mechanical_values("one two one")
        self.assertEqual(short["D2"]["MATTR"], 0.6667)
        self.assertTrue(short["D2"]["short_text"])


class LexicalMetricTests(unittest.TestCase):
    def test_auxiliary_detection_skips_intervening_adverbs(self) -> None:
        class FixedTagger:
            def tag(self, tokens):
                tags = ["VBP", "RB", "VB", "VBP", "RB", "VBN", "NN"]
                return list(zip(tokens, tags))

        class FixedLemmatizer:
            def lemmatize(self, token, pos):
                return {"does": "do", "has": "have"}.get(token, token)

        resources = LexicalResources(
            tagger=FixedTagger(),
            lemmatizer=FixedLemmatizer(),
            zipf_by_word={},
            resource_dir=Path("."),
        )
        analyses = analyze_tokens(
            ["does", "not", "stop", "has", "already", "finished", "work"],
            resources,
        )
        self.assertFalse(analyses[0].is_content)
        self.assertFalse(analyses[3].is_content)
        self.assertTrue(analyses[2].is_content)
        self.assertTrue(analyses[5].is_content)
        self.assertTrue(analyses[6].is_content)

    def test_frequency_metrics_use_only_content_tokens_and_lemma_fallback(self) -> None:
        analyses = [
            TokenAnalysis("common", "NN", "common", True),
            TokenAnalysis("rare", "JJ", "rare", True),
            TokenAnalysis("missing", "NN", "missing", True),
            TokenAnalysis("runner's", "NN", "runner", True),
            TokenAnalysis("the", "DT", "the", False),
        ]
        result = frequency_metrics(
            analyses,
            {"common": 5.0, "rare": 2.5, "runner": 4.0, "the": 7.0},
        )
        self.assertEqual(result["W1"]["matched"], 3)
        self.assertEqual(result["W1"]["oov"], 1)
        self.assertEqual(result["W1"]["coverage"], 0.75)
        self.assertEqual(result["W1"]["mean_zipf"], 3.8333)
        self.assertEqual(result["W1"]["status"], "ok")
        self.assertEqual(result["W2"]["low_frequency_count"], 1)
        self.assertEqual(result["W2"]["low_frequency_ratio"], 0.3333)

    def test_frequency_metrics_handle_no_content_tokens(self) -> None:
        result = frequency_metrics(
            [TokenAnalysis("the", "DT", "the", False)],
            {"the": 7.0},
        )
        self.assertEqual(result["W1"]["matched"], 0)
        self.assertIsNone(result["W1"]["coverage"])
        self.assertIsNone(result["W1"]["mean_zipf"])
        self.assertIsNone(result["W2"]["low_frequency_ratio"])

    def test_missing_resources_have_an_actionable_error(self) -> None:
        load_lexical_resources.cache_clear()
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(AnnotationError, "setup_lexical_resources.py"):
                load_lexical_resources(directory)
        load_lexical_resources.cache_clear()


class PipelineLexicalTests(unittest.TestCase):
    def test_w1_w2_are_added_to_part_i_mechanical_values(self) -> None:
        lexical = {
            "W1": {
                "matched": 1,
                "oov": 0,
                "coverage": 1.0,
                "mean_zipf": 4.2,
                "lexicon_version": "test-lexicon",
                "status": "ok",
            },
            "W2": {
                "low_frequency_count": 0,
                "matched": 1,
                "coverage": 1.0,
                "low_frequency_ratio": 0.0,
            },
        }
        config = ClientConfig(
            base_url="https://example.test/v1",
            model="test-model",
            timeout=1,
            max_tokens=100,
            retries=0,
            response_format=False,
            api_key=None,
        )

        def inspect_part_i_call(system, payload, *args):
            self.assertEqual(payload["MECHANICAL_VALUES"]["W1"], lexical["W1"])
            self.assertEqual(payload["MECHANICAL_VALUES"]["W2"], lexical["W2"])
            raise RuntimeError("payload inspected")

        with (
            mock.patch.object(pipeline, "lexical_values", return_value=lexical),
            mock.patch.object(pipeline, "chat", side_effect=inspect_part_i_call),
            self.assertRaisesRegex(RuntimeError, "payload inspected"),
        ):
            pipeline.annotate_one(1, {"body": "hello"}, "body", config)


class StorageTests(unittest.TestCase):
    def test_formatted_record_round_trips(self) -> None:
        record = {
            "body": "hello",
            "annotations": {
                "part_i": {"N1": {"word_count": 1}},
                "part_ii": {"E1": {"valence": 0}},
            },
            "_prelabel_meta": {"source_line": 3},
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "output.jsonl"
            path.write_text(format_output_record(record) + "\n", encoding="utf-8")
            self.assertEqual(load_output_records(path), [(1, record)])


class CompatibilityTests(unittest.TestCase):
    def test_original_module_reexports_public_helpers(self) -> None:
        self.assertIs(annotate_comments.mechanical_values, mechanics.mechanical_values)
        self.assertTrue(callable(annotate_comments.main))


class ProviderTests(unittest.TestCase):
    def test_default_provider_keeps_existing_service(self) -> None:
        args = parse_args([
            "--input", "input.jsonl",
            "--output", "output.jsonl",
        ])
        self.assertEqual(args.base_url, DEFAULT_BASE_URL)
        self.assertEqual(args.model, DEFAULT_MODEL)
        self.assertIsNone(args.api_key_env)

    def test_aliyun_provider_selects_dashscope_defaults(self) -> None:
        args = parse_args([
            "--provider", "aliyun",
            "--input", "input.jsonl",
            "--output", "output.jsonl",
        ])
        self.assertEqual(args.base_url, ALIYUN_BASE_URL)
        self.assertEqual(args.model, ALIYUN_MODEL)
        self.assertEqual(args.api_key_env, ALIYUN_API_KEY_ENV)

    def test_aliyun_provider_allows_explicit_overrides(self) -> None:
        args = parse_args([
            "--provider", "aliyun",
            "--base-url", "https://example.test/v1",
            "--model", "another-model",
            "--api-key-env", "OTHER_API_KEY",
            "--input", "input.jsonl",
            "--output", "output.jsonl",
        ])
        self.assertEqual(args.base_url, "https://example.test/v1")
        self.assertEqual(args.model, "another-model")
        self.assertEqual(args.api_key_env, "OTHER_API_KEY")

    def test_aliyun_provider_requires_api_key_environment_variable(self) -> None:
        with mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(AnnotationError, ALIYUN_API_KEY_ENV):
                main([
                    "--provider", "aliyun",
                    "--input", "missing-input.jsonl",
                    "--output", "output.jsonl",
                ])


if __name__ == "__main__":
    unittest.main()
