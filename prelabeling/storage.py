"""Input/output parsing, formatting, and resume support."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .config import AnnotationError


def compact_json(value: Any) -> str:
    """Serialize a value without adding whitespace inside an annotation item."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def format_output_record(record: Mapping[str, Any]) -> str:
    """Format one result so every Part I/II indicator occupies one line."""
    annotations = record.get("annotations")
    if not isinstance(annotations, Mapping):
        return compact_json(record)

    source_fields = {
        key: value
        for key, value in record.items()
        if key not in {"annotations", "_prelabel_meta"}
    }
    source_json = compact_json(source_fields)
    prefix = source_json[:-1]
    if source_fields:
        prefix += ","

    lines = [prefix + '"annotations":{']
    sections = list(annotations.items())
    for section_index, (section_name, section) in enumerate(sections):
        section_key = compact_json(section_name)
        if not isinstance(section, Mapping):
            suffix = "," if section_index < len(sections) - 1 else ""
            lines.append(f"  {section_key}:{compact_json(section)}{suffix}")
            continue

        lines.append(f"  {section_key}:{{")
        items = list(section.items())
        for item_index, (item_name, item_value) in enumerate(items):
            suffix = "," if item_index < len(items) - 1 else ""
            lines.append(
                f"    {compact_json(item_name)}:{compact_json(item_value)}{suffix}"
            )
        section_suffix = "," if section_index < len(sections) - 1 else ""
        lines.append(f"  }}{section_suffix}")

    meta = record.get("_prelabel_meta")
    if "_prelabel_meta" in record:
        lines.append(f'}},"_prelabel_meta":{compact_json(meta)}}}')
    else:
        lines.append("}}")
    return "\n".join(lines)


def load_jsonl(path: Path) -> list[tuple[int, dict[str, Any]]]:
    rows: list[tuple[int, dict[str, Any]]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise AnnotationError(f"输入第 {line_no} 行不是合法 JSON: {exc}") from exc
            if not isinstance(value, dict):
                raise AnnotationError(f"输入第 {line_no} 行必须是 JSON 对象")
            if "annotations" in value or "_prelabel_meta" in value:
                raise AnnotationError(f"输入第 {line_no} 行已含保留字段 annotations/_prelabel_meta")
            rows.append((line_no, value))
    return rows


def load_output_records(path: Path) -> list[tuple[int, dict[str, Any]]]:
    """Read whitespace-separated JSON objects, including formatted multi-line ones."""
    content = path.read_text(encoding="utf-8")
    decoder = json.JSONDecoder()
    records: list[tuple[int, dict[str, Any]]] = []
    position = 0
    while position < len(content):
        while position < len(content) and content[position].isspace():
            position += 1
        if position >= len(content):
            break
        start = position
        start_line = content.count("\n", 0, start) + 1
        try:
            value, position = decoder.raw_decode(content, position)
        except json.JSONDecodeError as exc:
            raise AnnotationError(
                f"输出文件第 {start_line} 行起的记录损坏，不能 resume: {exc}"
            ) from exc
        if not isinstance(value, dict):
            raise AnnotationError(f"输出文件第 {start_line} 行起的记录必须是 JSON 对象")
        records.append((start_line, value))
    return records


def completed_lines(path: Path) -> set[int]:
    if not path.exists():
        return set()
    done: set[int] = set()
    for output_line, row in load_output_records(path):
        try:
            source_line = row["_prelabel_meta"]["source_line"]
        except (KeyError, TypeError) as exc:
            raise AnnotationError(f"输出文件第 {output_line} 行起的记录损坏，不能 resume") from exc
        if isinstance(source_line, int):
            done.add(source_line)
    return done
