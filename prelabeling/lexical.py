"""Fixed POS/lemma analysis and SUBTLEX-US frequency measurements."""

from __future__ import annotations

import csv
import hashlib
import json
import os
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Sequence

from .config import AnnotationError
from .mechanics import round4


RESOURCE_DIR_ENV = "PRELABELING_RESOURCE_DIR"
DEFAULT_RESOURCE_DIR = Path(__file__).resolve().parent.parent / "resources"
MANIFEST_NAME = "lexical_manifest.json"
LEXICON_NAME = "subtlex_us_zipf.tsv"
EXPECTED_NLTK_VERSION = "3.9.2"
EXPECTED_ENTRY_COUNT = 74286
LEXICON_VERSION = (
    "subtlex_us_pos_zipf_2013+nltk_3.9.2+wordnet_3.0+surface_then_lemma_v1"
)
TAGGER_VERSION = "nltk_3.9.2:averaged_perceptron_tagger_eng"
LEMMATIZER_VERSION = "nltk_3.9.2:wordnet_3.0"

_WORDNET_POS_BY_PREFIX = {
    "NN": "n",
    "VB": "v",
    "JJ": "a",
    "RB": "r",
}
_CONTENT_PREFIXES = tuple(_WORDNET_POS_BY_PREFIX)
_AUXILIARY_CONTRACTIONS = {
    "ain't", "aren't", "can't", "couldn't", "didn't", "doesn't", "don't",
    "hadn't", "hasn't", "haven't", "isn't", "mightn't", "mustn't", "shan't",
    "shouldn't", "wasn't", "weren't", "won't", "wouldn't",
    "he'd", "he'll", "he's", "i'd", "i'll", "i'm", "i've", "it'd", "it'll",
    "it's", "she'd", "she'll", "she's", "they'd", "they'll", "they're",
    "they've", "we'd", "we'll", "we're", "we've", "you'd", "you'll",
    "you're", "you've",
}


@dataclass(frozen=True)
class TokenAnalysis:
    token: str
    penn_tag: str
    lemma: str
    is_content: bool


@dataclass
class LexicalResources:
    tagger: Any
    lemmatizer: Any
    zipf_by_word: Mapping[str, float]
    resource_dir: Path


def resource_dir_from_env() -> Path:
    configured = os.environ.get(RESOURCE_DIR_ENV)
    return Path(configured).expanduser().resolve() if configured else DEFAULT_RESOURCE_DIR


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_tree(path: Path) -> str:
    digest = hashlib.sha256()
    if not path.is_dir():
        return ""
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        digest.update(child.relative_to(path).as_posix().encode("utf-8"))
        digest.update(b"\0")
        with child.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def _resource_error(detail: str) -> AnnotationError:
    return AnnotationError(
        f"固定词法资源不可用：{detail}。请先运行 "
        "`python3 scripts/setup_lexical_resources.py`，并安装 requirements.txt。"
    )


def _load_manifest(resource_dir: Path) -> dict[str, Any]:
    path = resource_dir / MANIFEST_NAME
    if not path.exists():
        raise _resource_error(f"缺少 {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise _resource_error(f"资源清单损坏：{exc}") from exc
    if not isinstance(value, dict) or value.get("format_version") != 1:
        raise _resource_error("资源清单版本不受支持")
    if value.get("lexicon_version") != LEXICON_VERSION:
        raise _resource_error("资源清单与当前代码要求的词表版本不一致")
    return value


def _load_zipf_lexicon(resource_dir: Path, manifest: Mapping[str, Any]) -> dict[str, float]:
    path = resource_dir / LEXICON_NAME
    if not path.exists():
        raise _resource_error(f"缺少 {path}")
    expected_hash = manifest.get("subtlex_us", {}).get("normalized_sha256")
    if not isinstance(expected_hash, str) or sha256_file(path) != expected_hash:
        raise _resource_error(f"{path} 的 SHA-256 与资源清单不一致")

    values: dict[str, float] = {}
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            if reader.fieldnames != ["word", "zipf"]:
                raise _resource_error(f"{path} 的表头应为 word/zipf")
            for row_number, row in enumerate(reader, 2):
                word = row["word"]
                try:
                    zipf = float(row["zipf"])
                except (TypeError, ValueError) as exc:
                    raise _resource_error(f"{path} 第 {row_number} 行 Zipf 值无效") from exc
                if not word or word in values:
                    raise _resource_error(f"{path} 第 {row_number} 行词形为空或重复")
                values[word] = zipf
    except OSError as exc:
        raise _resource_error(f"无法读取 {path}: {exc}") from exc

    if len(values) != EXPECTED_ENTRY_COUNT:
        raise _resource_error(
            f"{path} 应含 {EXPECTED_ENTRY_COUNT} 个词形，实际为 {len(values)}"
        )
    return values


@lru_cache(maxsize=4)
def load_lexical_resources(resource_dir_value: str | None = None) -> LexicalResources:
    resource_dir = (
        Path(resource_dir_value).expanduser().resolve()
        if resource_dir_value is not None
        else resource_dir_from_env()
    )
    manifest = _load_manifest(resource_dir)

    nltk_manifest = manifest.get("nltk", {})
    integrity_targets = (
        (
            resource_dir / "nltk_data" / "taggers" / "averaged_perceptron_tagger_eng",
            nltk_manifest.get("tagger", {}).get("installed_sha256"),
        ),
        (
            resource_dir / "nltk_data" / "corpora" / "wordnet",
            nltk_manifest.get("lemmatizer", {}).get("installed_sha256"),
        ),
    )
    for path, expected_hash in integrity_targets:
        if not isinstance(expected_hash, str) or sha256_tree(path) != expected_hash:
            raise _resource_error(f"{path} 的目录哈希与资源清单不一致")

    try:
        import nltk
        from nltk.stem import WordNetLemmatizer
        from nltk.tag import PerceptronTagger
    except ImportError as exc:
        raise _resource_error(f"缺少 nltk=={EXPECTED_NLTK_VERSION}") from exc
    if nltk.__version__ != EXPECTED_NLTK_VERSION:
        raise _resource_error(
            f"NLTK 版本应为 {EXPECTED_NLTK_VERSION}，实际为 {nltk.__version__}"
        )

    nltk_data_dir = resource_dir / "nltk_data"
    if str(nltk_data_dir) not in nltk.data.path:
        nltk.data.path.insert(0, str(nltk_data_dir))
    try:
        tagger = PerceptronTagger(lang="eng")
        lemmatizer = WordNetLemmatizer()
        # Force lazy WordNet loading here so concurrent workers only read initialized data.
        lemmatizer.lemmatize("tests", pos="n")
    except LookupError as exc:
        raise _resource_error(f"NLTK 数据目录不完整：{exc}") from exc

    return LexicalResources(
        tagger=tagger,
        lemmatizer=lemmatizer,
        zipf_by_word=_load_zipf_lexicon(resource_dir, manifest),
        resource_dir=resource_dir,
    )


def _wordnet_pos(penn_tag: str) -> str | None:
    for prefix, wordnet_pos in _WORDNET_POS_BY_PREFIX.items():
        if penn_tag.startswith(prefix):
            return wordnet_pos
    return None


def _is_auxiliary(
    token: str,
    lemma: str,
    penn_tag: str,
    next_non_adverb_tag: str | None,
) -> bool:
    if penn_tag == "MD" or token in _AUXILIARY_CONTRACTIONS or lemma == "be":
        return True
    # Negation and other adverbs may intervene: "do not stop", "has already left".
    if lemma == "have" and next_non_adverb_tag == "VBN":
        return True
    if (
        lemma == "do"
        and next_non_adverb_tag is not None
        and next_non_adverb_tag.startswith("VB")
    ):
        return True
    return False


def analyze_tokens(tokens: Sequence[str], resources: LexicalResources) -> list[TokenAnalysis]:
    if not tokens:
        return []
    tagged = resources.tagger.tag(list(tokens))
    next_non_adverb_tags: list[str | None] = [None] * len(tagged)
    next_non_adverb: str | None = None
    for index in range(len(tagged) - 1, -1, -1):
        next_non_adverb_tags[index] = next_non_adverb
        current_tag = tagged[index][1]
        if not current_tag.startswith("RB"):
            next_non_adverb = current_tag
    analyses: list[TokenAnalysis] = []
    for index, (token, penn_tag) in enumerate(tagged):
        wordnet_pos = _wordnet_pos(penn_tag)
        lemma = (
            resources.lemmatizer.lemmatize(token, pos=wordnet_pos)
            if wordnet_pos is not None
            else token
        )
        is_content = penn_tag.startswith(_CONTENT_PREFIXES) and not _is_auxiliary(
            token,
            lemma,
            penn_tag,
            next_non_adverb_tags[index],
        )
        analyses.append(TokenAnalysis(token, penn_tag, lemma, is_content))
    return analyses


def _lookup_zipf(analysis: TokenAnalysis, lexicon: Mapping[str, float]) -> float | None:
    candidates = [analysis.token]
    if "'" in analysis.token:
        candidates.append(analysis.token.replace("'", ""))
    if analysis.lemma not in candidates:
        candidates.append(analysis.lemma)
    if "'" in analysis.lemma:
        candidates.append(analysis.lemma.replace("'", ""))
    for candidate in candidates:
        value = lexicon.get(candidate)
        if value is not None:
            return value
    return None


def frequency_metrics(
    analyses: Sequence[TokenAnalysis],
    lexicon: Mapping[str, float],
) -> dict[str, dict[str, Any]]:
    zipf_values: list[float] = []
    oov = 0
    for analysis in analyses:
        if not analysis.is_content:
            continue
        zipf = _lookup_zipf(analysis, lexicon)
        if zipf is None:
            oov += 1
        else:
            zipf_values.append(zipf)

    matched = len(zipf_values)
    total = matched + oov
    coverage = (
        None if total == 0 else round4(Decimal(matched) / Decimal(total))
    )
    mean_zipf = (
        None
        if matched == 0
        else round4(sum(Decimal(str(value)) for value in zipf_values) / Decimal(matched))
    )
    low_frequency_count = sum(value < 3 for value in zipf_values)
    low_frequency_ratio = (
        None
        if matched == 0
        else round4(Decimal(low_frequency_count) / Decimal(matched))
    )
    return {
        "W1": {
            "matched": matched,
            "oov": oov,
            "coverage": coverage,
            "mean_zipf": mean_zipf,
            "lexicon_version": LEXICON_VERSION,
            "status": "ok",
        },
        "W2": {
            "low_frequency_count": low_frequency_count,
            "matched": matched,
            "coverage": coverage,
            "low_frequency_ratio": low_frequency_ratio,
        },
    }


def lexical_values(
    tokens: Sequence[str],
    resource_dir: Path | None = None,
) -> dict[str, dict[str, Any]]:
    resources = load_lexical_resources(str(resource_dir) if resource_dir else None)
    return frequency_metrics(analyze_tokens(tokens, resources), resources.zipf_by_word)


def lexical_resource_status() -> dict[str, str]:
    return {
        "subtlex_us": LEXICON_VERSION,
        "pos_tagger": TAGGER_VERSION,
        "lemmatizer": LEMMATIZER_VERSION,
    }
