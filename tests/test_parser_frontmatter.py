"""Front-matter parser coverage."""

from __future__ import annotations

from datetime import datetime
from textwrap import dedent

import pytest

from denote_lint.parser.frontmatter import parse_date_tolerant, parse_frontmatter


class TestOrg:
    def test_full_block(self) -> None:
        text = dedent(
            """\
            #+title:      Hello
            #+date:       [2024-01-15 Mon 09:30]
            #+filetags:   :tag1:tag2:
            #+identifier: 20240115T093000

            Body line one.
            Body line two.
            """
        )
        fm, body = parse_frontmatter("org", text)
        assert fm is not None
        assert fm.title == "Hello"
        assert fm.identifier == "20240115T093000"
        assert fm.date == datetime(2024, 1, 15, 9, 30, 0)
        assert fm.keywords == ("tag1", "tag2")
        assert body.startswith("Body line one.")

    def test_filetags_empty(self) -> None:
        fm, _ = parse_frontmatter("org", "#+title: x\n#+filetags: ::\n")
        assert fm is not None
        assert fm.keywords == ()

    def test_filetags_no_colons(self) -> None:
        fm, _ = parse_frontmatter("org", "#+filetags:   tag1\n")
        assert fm is not None
        assert fm.keywords == ("tag1",)

    def test_no_frontmatter(self) -> None:
        fm, body = parse_frontmatter("org", "Just body.\n")
        assert fm is not None
        assert fm.title is None
        assert body == "Just body.\n"

    def test_missing_title(self) -> None:
        fm, _ = parse_frontmatter("org", "#+identifier: 20240115T093000\n")
        assert fm is not None
        assert fm.title is None
        assert fm.identifier == "20240115T093000"

    def test_properties_drawer_before_keywords(self) -> None:
        """File-level :PROPERTIES: drawer preceding #+keywords is recognised."""
        text = dedent(
            """\
            # comment -*- indent-tabs-mode:nil -*-
            :PROPERTIES:
            :ID:       20240115T093000
            :CREDITS:  3
            :END:
            #+title:      Hello
            #+identifier: 20240115T093000
            #+filetags:   :tag1:tag2:

            Body.
            """
        )
        fm, body = parse_frontmatter("org", text)
        assert fm is not None
        assert fm.title == "Hello"
        assert fm.identifier == "20240115T093000"
        assert fm.keywords == ("tag1", "tag2")
        assert body.startswith("Body.")

    def test_properties_drawer_only_no_keywords(self) -> None:
        """A drawer with no #+keywords yields empty front matter, not a crash."""
        text = dedent(
            """\
            :PROPERTIES:
            :ID:       20240115T093000
            :END:

            Body.
            """
        )
        fm, body = parse_frontmatter("org", text)
        assert fm is not None
        assert fm.title is None
        assert fm.identifier is None


class TestMarkdownYaml:
    def test_full_block(self) -> None:
        text = dedent(
            """\
            ---
            title: Hello
            date: 2024-01-15T09:30:00
            tags: [tag1, tag2]
            identifier: "20240115T093000"
            ---
            Body.
            """
        )
        fm, body = parse_frontmatter("md", text)
        assert fm is not None
        assert fm.title == "Hello"
        assert fm.identifier == "20240115T093000"
        assert fm.date == datetime(2024, 1, 15, 9, 30, 0)
        assert fm.keywords == ("tag1", "tag2")
        assert body.startswith("Body.")

    def test_truncated_e008(self) -> None:
        fm, _ = parse_frontmatter("md", "---\ntitle: x\n")
        assert fm is not None
        assert "E008" in fm.parse_errors

    def test_yaml_invalid_e008(self) -> None:
        fm, _ = parse_frontmatter("md", "---\ntitle: : bad\n  - x\n---\n")
        assert fm is not None
        assert "E008" in fm.parse_errors

    def test_no_frontmatter_returns_empty(self) -> None:
        fm, body = parse_frontmatter("md", "Just body.\n")
        assert fm is not None
        assert fm.title is None
        assert body == "Just body.\n"

    def test_yaml_with_tz_offset_strips(self) -> None:
        text = "---\ndate: 2024-01-15T09:30:00+13:00\n---\n"
        fm, _ = parse_frontmatter("md", text)
        assert fm is not None
        assert fm.date == datetime(2024, 1, 15, 9, 30, 0)
        assert fm.date.tzinfo is None


class TestMarkdownToml:
    def test_full_block(self) -> None:
        text = dedent(
            """\
            +++
            title = "Hello"
            date = 2024-01-15T09:30:00
            tags = ["tag1", "tag2"]
            identifier = "20240115T093000"
            +++
            Body.
            """
        )
        fm, body = parse_frontmatter("md", text)
        assert fm is not None
        assert fm.title == "Hello"
        assert fm.identifier == "20240115T093000"
        assert fm.date == datetime(2024, 1, 15, 9, 30, 0)
        assert fm.keywords == ("tag1", "tag2")
        assert body.startswith("Body.")

    def test_toml_truncated_e008(self) -> None:
        fm, _ = parse_frontmatter("md", "+++\ntitle = \"x\"\n")
        assert fm is not None
        assert "E008" in fm.parse_errors

    def test_toml_invalid_e008(self) -> None:
        fm, _ = parse_frontmatter("md", "+++\ntitle = unquoted bare\n+++\n")
        assert fm is not None
        assert "E008" in fm.parse_errors


class TestPlaintext:
    def test_full_block(self) -> None:
        text = dedent(
            """\
            title:      Hello
            date:       2024-01-15
            tags:       _tag1_ _tag2_
            identifier: 20240115T093000
            ---------------------------
            Body.
            """
        )
        fm, body = parse_frontmatter("txt", text)
        assert fm is not None
        assert fm.title == "Hello"
        assert fm.identifier == "20240115T093000"
        assert fm.date == datetime(2024, 1, 15)
        assert fm.keywords == ("tag1", "tag2")
        assert body.startswith("Body.")

    def test_no_separator_e008(self) -> None:
        fm, _ = parse_frontmatter("txt", "title: x\nbody without separator\n")
        assert fm is not None
        assert "E008" in fm.parse_errors


class TestAttachment:
    def test_unknown_extension_returns_none(self) -> None:
        fm, body = parse_frontmatter("png", "binary garbage")
        assert fm is None
        assert body == "binary garbage"


class TestDateTolerance:
    @pytest.mark.parametrize(
        "s,expected",
        [
            ("2024-01-15", datetime(2024, 1, 15)),
            ("2024-01-15T09:30:00", datetime(2024, 1, 15, 9, 30, 0)),
            ("2024-01-15T09:30:00Z", datetime(2024, 1, 15, 9, 30, 0)),
            ("2024-01-15T09:30:00+13:00", datetime(2024, 1, 15, 9, 30, 0)),
            ("[2024-01-15 Mon 09:30]", datetime(2024, 1, 15, 9, 30, 0)),
            ("[2024-01-15]", datetime(2024, 1, 15)),
            ("[2024-01-15 Mon]", datetime(2024, 1, 15)),
        ],
    )
    def test_recognised(self, s: str, expected: datetime) -> None:
        assert parse_date_tolerant(s) == expected

    @pytest.mark.parametrize(
        "s",
        ["", "not a date", "Jan 15 2024", "2024/01/15"],
    )
    def test_unrecognised(self, s: str) -> None:
        assert parse_date_tolerant(s) is None
