"""Front-matter check coverage: E005-E008, W002-W004."""

from __future__ import annotations

from datetime import datetime

from denote_lint.checks.frontmatter import (
    check_e005,
    check_e006,
    check_e007,
    check_e008,
    check_w002,
    check_w003,
    check_w004,
)
from denote_lint.models import Issue
from denote_lint.sluggify import sluggify_title
from tests.conftest import make_context, make_note


def _codes(issues: list[Issue]) -> list[str]:
    return [i.code for i in issues]


class TestE005:
    def test_mismatch_fires(self) -> None:
        n = make_note(
            "20240115T093000.org",
            fm_identifier="20240116T100000",
        )
        out = list(check_e005(n, make_context([n])))
        assert _codes(out) == ["E005"]

    def test_match_silent(self) -> None:
        n = make_note(
            "20240115T093000.org",
            fm_identifier="20240115T093000",
        )
        assert list(check_e005(n, make_context([n]))) == []

    def test_missing_fm_id_silent(self) -> None:
        n = make_note("20240115T093000.org", fm_identifier=None)
        assert list(check_e005(n, make_context([n]))) == []

    def test_attachment_silent(self) -> None:
        n = make_note("20240115T093000--photo.jpg")
        assert list(check_e005(n, make_context([n]))) == []


class TestE006:
    def test_missing_id_fires(self) -> None:
        n = make_note("20240115T093000.org", fm_identifier=None)
        out = list(check_e006(n, make_context([n])))
        assert _codes(out) == ["E006"]

    def test_present_id_silent(self) -> None:
        n = make_note("20240115T093000.org", fm_identifier="20240115T093000")
        assert list(check_e006(n, make_context([n]))) == []


class TestE007:
    def test_missing_title_fires(self) -> None:
        n = make_note("20240115T093000.org", fm_title=None)
        out = list(check_e007(n, make_context([n])))
        assert _codes(out) == ["E007"]

    def test_present_title_silent(self) -> None:
        n = make_note("20240115T093000.org", fm_title="Hi")
        assert list(check_e007(n, make_context([n]))) == []


class TestE008:
    def test_unparseable_fires(self) -> None:
        n = make_note(
            "20240115T093000.org", fm_parse_errors=("E008",)
        )
        out = list(check_e008(n, make_context([n])))
        assert _codes(out) == ["E008"]

    def test_read_error_fires_synthetic_e008(self) -> None:
        n = make_note(
            "20240115T093000.org",
            no_front_matter=True,
            read_error="file is not valid UTF-8",
        )
        out = list(check_e008(n, make_context([n])))
        assert _codes(out) == ["E008"]
        assert "UTF-8" in out[0].message


class TestW002:
    def test_mismatch_fires(self) -> None:
        n = make_note(
            "20240115T093000--my-note.org",
            fm_title="A Different Title",
        )
        out = list(check_w002(n, make_context([n])))
        assert _codes(out) == ["W002"]

    def test_match_silent(self) -> None:
        n = make_note(
            "20240115T093000--my-note.org",
            fm_title="My Note",
        )
        assert list(check_w002(n, make_context([n]))) == []

    def test_missing_filename_slug_silent(self) -> None:
        n = make_note("20240115T093000.org", fm_title="My Note")
        assert list(check_w002(n, make_context([n]))) == []


class TestSluggifyTitle:
    def test_basic(self) -> None:
        assert sluggify_title("My Note") == "my-note"

    def test_punctuation(self) -> None:
        # Denote's title blocklist *strips* punctuation (apostrophes,
        # colons, exclamation marks) rather than treating them as word
        # separators, so "It's" becomes "its", not "it-s".
        assert sluggify_title("It's: A test!") == "its-a-test"

    def test_collapses_repeats(self) -> None:
        assert sluggify_title("a---b   c") == "a-b-c"

    def test_strips_edges(self) -> None:
        assert sluggify_title("--foo--") == "foo"

    def test_preserves_non_ascii(self) -> None:
        assert sluggify_title("Café Östra") == "café-östra"


class TestW003:
    def test_extra_in_filename_fires(self) -> None:
        n = make_note(
            "20240115T093000__a_b.org",
            fm_keywords=("a",),
        )
        out = list(check_w003(n, make_context([n])))
        assert _codes(out) == ["W003"]
        assert "only in filename" in out[0].message

    def test_extra_in_frontmatter_fires(self) -> None:
        n = make_note(
            "20240115T093000__a.org",
            fm_keywords=("a", "b"),
        )
        out = list(check_w003(n, make_context([n])))
        assert _codes(out) == ["W003"]
        assert "only in front matter" in out[0].message

    def test_match_silent(self) -> None:
        n = make_note(
            "20240115T093000__a_b.org",
            fm_keywords=("a", "b"),
        )
        assert list(check_w003(n, make_context([n]))) == []

    def test_both_empty_silent(self) -> None:
        n = make_note("20240115T093000.org")
        assert list(check_w003(n, make_context([n]))) == []


class TestW004:
    def test_day_mismatch_fires(self) -> None:
        n = make_note(
            "20240115T093000.org",
            fm_date=datetime(2024, 1, 16),
        )
        out = list(check_w004(n, make_context([n])))
        assert _codes(out) == ["W004"]

    def test_same_day_silent(self) -> None:
        n = make_note(
            "20240115T093000.org",
            fm_date=datetime(2024, 1, 15, 12, 0, 0),
        )
        assert list(check_w004(n, make_context([n]))) == []

    def test_no_fm_date_silent(self) -> None:
        n = make_note("20240115T093000.org", fm_date=None)
        assert list(check_w004(n, make_context([n]))) == []

    def test_no_id_dt_silent(self) -> None:
        # Bad identifier means no identifier_dt, so W004 has nothing to compare.
        n = make_note("not-an-id.org", fm_date=datetime(2024, 1, 15))
        assert list(check_w004(n, make_context([n]))) == []
