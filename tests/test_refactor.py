"""Offline regression checks for the package split."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import annotate_comments
from prelabeling import mechanics
from prelabeling.cli import main, parse_args
from prelabeling.config import (
    ALIYUN_API_KEY_ENV,
    ALIYUN_BASE_URL,
    ALIYUN_MODEL,
    AnnotationError,
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
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
