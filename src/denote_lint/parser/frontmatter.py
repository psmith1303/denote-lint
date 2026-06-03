"""Front-matter parsers: org / YAML / TOML / plain-text.

Each flavour returns a normalised :class:`FrontMatter` plus the body
text. The dispatcher :func:`parse_frontmatter` picks the right flavour
by extension (and, for ``.md``, by the opening fence).

Contract: input is already-normalised UTF-8 text (BOM stripped, line
endings ``\\n``). The corpus loader is responsible for that step.
"""

from __future__ import annotations

import re
import tomllib
from datetime import date, datetime
from typing import Any

import yaml

from denote_lint.models import FrontMatter

_ORG_DATE_RE = re.compile(
    r"^\[?\s*(\d{4})-(\d{2})-(\d{2})"
    r"(?:\s+[A-Za-z]{3,})?"
    r"(?:\s+(\d{2}):(\d{2})(?::(\d{2}))?)?"
    r"\s*\]?$"
)


def parse_frontmatter(extension: str, text: str) -> tuple[FrontMatter | None, str]:
    """Parse the front matter for the given extension.

    Returns ``(FrontMatter, body)`` for note types and ``(None, body)``
    for attachments (any extension other than org/md/txt).

    A markdown file with no recognised opening fence yields an empty
    :class:`FrontMatter` (no parse_errors); the caller's checks decide
    whether that's acceptable.
    """
    ext = extension.lower()
    if ext == "org":
        return _parse_org(text)
    if ext == "md":
        if text.startswith("---\n") or text == "---" or text.startswith("---\r"):
            return _parse_md_yaml(text)
        if text.startswith("+++\n") or text == "+++" or text.startswith("+++\r"):
            return _parse_md_toml(text)
        return FrontMatter(), text
    if ext == "txt":
        return _parse_plaintext(text)
    return None, text


def _parse_org(text: str) -> tuple[FrontMatter, str]:
    lines = text.split("\n")
    fm_lines: list[str] = []
    body_start = len(lines)
    in_property_drawer = False
    for i, line in enumerate(lines):
        if in_property_drawer:
            if line.strip() == ":END:":
                in_property_drawer = False
            continue
        if line.strip() == ":PROPERTIES:":
            in_property_drawer = True
            continue
        if line.startswith("#+"):
            fm_lines.append(line)
            continue
        if line.startswith("#"):
            continue
        if line.strip() == "" and fm_lines:
            body_start = i + 1
            break
        if line.strip() == "":
            continue
        body_start = i
        break

    title: str | None = None
    identifier: str | None = None
    fm_date: datetime | None = None
    keywords: tuple[str, ...] = ()

    for line in fm_lines:
        key, _, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip()
        if key == "#+title":
            title = value or None
        elif key == "#+identifier":
            identifier = value or None
        elif key == "#+filetags":
            keywords = _parse_org_filetags(value)
        elif key == "#+date":
            fm_date = parse_date_tolerant(value)

    body = "\n".join(lines[body_start:])
    return FrontMatter(
        title=title,
        identifier=identifier,
        date=fm_date,
        keywords=keywords,
        raw_lines=tuple(fm_lines),
    ), body


def _parse_org_filetags(value: str) -> tuple[str, ...]:
    s = value.strip()
    if s.startswith(":"):
        s = s[1:]
    if s.endswith(":"):
        s = s[:-1]
    if not s:
        return ()
    return tuple(t for t in s.split(":") if t)


def _parse_md_yaml(text: str) -> tuple[FrontMatter, str]:
    lines = text.split("\n")
    end = _find_fence(lines, "---")
    if end is None:
        return FrontMatter(parse_errors=("E008",)), text
    fm_block = "\n".join(lines[1:end])
    body = "\n".join(lines[end + 1 :])
    try:
        data = yaml.safe_load(fm_block)
    except yaml.YAMLError:
        return FrontMatter(
            parse_errors=("E008",), raw_lines=tuple(lines[1:end])
        ), body
    if data is None:
        return FrontMatter(raw_lines=tuple(lines[1:end])), body
    if not isinstance(data, dict):
        return FrontMatter(
            parse_errors=("E008",), raw_lines=tuple(lines[1:end])
        ), body
    return _frontmatter_from_mapping(data, lines[1:end]), body


def _parse_md_toml(text: str) -> tuple[FrontMatter, str]:
    lines = text.split("\n")
    end = _find_fence(lines, "+++")
    if end is None:
        return FrontMatter(parse_errors=("E008",)), text
    fm_block = "\n".join(lines[1:end])
    body = "\n".join(lines[end + 1 :])
    try:
        data = tomllib.loads(fm_block)
    except tomllib.TOMLDecodeError:
        return FrontMatter(
            parse_errors=("E008",), raw_lines=tuple(lines[1:end])
        ), body
    return _frontmatter_from_mapping(data, lines[1:end]), body


def _find_fence(lines: list[str], fence: str) -> int | None:
    """Return the index of the closing fence line, or None if absent."""
    if not lines or lines[0].rstrip() != fence:
        return None
    for i in range(1, len(lines)):
        if lines[i].rstrip() == fence:
            return i
    return None


def _frontmatter_from_mapping(
    data: dict[str, Any], raw_lines: list[str]
) -> FrontMatter:
    title_raw = data.get("title")
    identifier_raw = data.get("identifier")
    date_raw = data.get("date")
    tags_raw = data.get("tags")

    title = str(title_raw) if title_raw not in (None, "") else None
    identifier = str(identifier_raw) if identifier_raw not in (None, "") else None
    fm_date = _coerce_date(date_raw)

    if isinstance(tags_raw, list):
        keywords = tuple(str(t) for t in tags_raw if isinstance(t, (str, int)))
    elif isinstance(tags_raw, str):
        keywords = tuple(t for t in tags_raw.split() if t)
    else:
        keywords = ()

    return FrontMatter(
        title=title,
        identifier=identifier,
        date=fm_date,
        keywords=keywords,
        raw_lines=tuple(raw_lines),
    )


def _coerce_date(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo is not None else value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    if isinstance(value, str):
        return parse_date_tolerant(value)
    return None


def _parse_plaintext(text: str) -> tuple[FrontMatter, str]:
    lines = text.split("\n")
    sep_idx: int | None = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped and set(stripped) == {"-"} and len(stripped) >= 3:
            sep_idx = i
            break
        if i > 50:
            break

    if sep_idx is None:
        return FrontMatter(parse_errors=("E008",), raw_lines=tuple(lines)), text

    fm_lines = lines[:sep_idx]
    body = "\n".join(lines[sep_idx + 1 :])

    title: str | None = None
    identifier: str | None = None
    fm_date: datetime | None = None
    keywords: tuple[str, ...] = ()

    for line in fm_lines:
        key, sep, value = line.partition(":")
        if not sep:
            continue
        key = key.strip().lower()
        value = value.strip()
        if key == "title":
            title = value or None
        elif key == "identifier":
            identifier = value or None
        elif key == "date":
            fm_date = parse_date_tolerant(value)
        elif key == "tags":
            keywords = tuple(
                t.strip("_") for t in value.split() if t.strip("_")
            )

    return FrontMatter(
        title=title,
        identifier=identifier,
        date=fm_date,
        keywords=keywords,
        raw_lines=tuple(fm_lines),
    ), body


def parse_date_tolerant(s: str) -> datetime | None:
    """Parse the formats denote uses across its front-matter flavours.

    Recognised:
    - Org bracketed: ``[2024-01-15 Mon 09:30]``, ``[2024-01-15]``.
    - ISO 8601 (with or without time, with or without offset).
    - Plain ``YYYY-MM-DD``.

    Timezone offsets are preserved at the wall-clock level by stripping
    ``tzinfo``; per design we treat all dates as naive local time.
    Returns ``None`` on anything we don't recognise.
    """
    s = s.strip()
    if not s:
        return None
    if s.startswith("["):
        m = _ORG_DATE_RE.match(s)
        if not m:
            return None
        year, month, day, hour, minute, second = m.groups()
        return datetime(
            int(year),
            int(month),
            int(day),
            int(hour) if hour else 0,
            int(minute) if minute else 0,
            int(second) if second else 0,
        )
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    return dt.replace(tzinfo=None) if dt.tzinfo is not None else dt
