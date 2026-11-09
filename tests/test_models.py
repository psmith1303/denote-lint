"""Sanity tests for the data model dataclasses."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime
from pathlib import Path

import pytest

from denote_lint.models import (
    Context,
    FrontMatter,
    Issue,
    Link,
    Note,
    ParsedFilename,
)


def test_parsed_filename_is_frozen() -> None:
    pf = ParsedFilename(
        identifier="20240115T093000",
        identifier_dt=datetime(2024, 1, 15, 9, 30, 0),
        signature=None,
        title_slug="my-note",
        keywords=("tag1",),
        extension="org",
        raw="20240115T093000--my-note__tag1.org",
    )
    with pytest.raises(FrozenInstanceError):
        pf.identifier = "other"  # type: ignore[misc]


def test_issue_is_frozen_and_hashable() -> None:
    i = Issue(
        path=Path("/x.org"),
        line=1,
        col=1,
        severity="error",
        code="E001",
        message="msg",
    )
    hash(i)
    with pytest.raises(FrozenInstanceError):
        i.code = "E002"  # type: ignore[misc]


def test_frontmatter_defaults() -> None:
    fm = FrontMatter()
    assert fm.title is None
    assert fm.identifier is None
    assert fm.keywords == ()
    assert fm.parse_errors == ()


def test_link_is_frozen() -> None:
    link = Link(target_id="20240115T093000", description=None, line=3, col=1)
    with pytest.raises(FrozenInstanceError):
        link.line = 99  # type: ignore[misc]


def test_note_holds_links() -> None:
    pf = ParsedFilename(
        identifier="20240115T093000",
        identifier_dt=None,
        signature=None,
        title_slug=None,
        keywords=(),
        extension="org",
        raw="20240115T093000.org",
    )
    note = Note(path=Path("/n.org"), filename=pf, front_matter=None, body="")
    assert note.links == ()
    assert note.is_attachment is False


def test_context_defaults() -> None:
    ctx = Context()
    assert ctx.image_tag == "image"
    assert "png" in ctx.image_extensions
    assert ctx.allow_attachment_aliases is False
