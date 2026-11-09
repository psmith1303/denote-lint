"""Hygiene check coverage: W008, I001, I002, I003, I004."""

from __future__ import annotations

from denote_lint.checks.hygiene import (
    _edit_distance,
    _is_near_miss,
    check_i001,
    check_i002,
    check_i003,
    check_i004,
    check_w008,
)
from denote_lint.models import Issue, Link
from tests.conftest import make_context, make_note


def _codes(issues: list[Issue]) -> list[str]:
    return [i.code for i in issues]


class TestW008:
    def test_image_without_tag_fires(self) -> None:
        n = make_note("20240115T093000--photo.jpg")
        out = list(check_w008(n, make_context([n])))
        assert _codes(out) == ["W008"]

    def test_image_with_filename_image_tag_silent(self) -> None:
        n = make_note("20240115T093000--photo__image.jpg")
        assert list(check_w008(n, make_context([n]))) == []

    def test_non_image_silent(self) -> None:
        n = make_note("20240115T093000--note.org")
        assert list(check_w008(n, make_context([n]))) == []

    def test_image_uppercase_extension_still_detected(self) -> None:
        # We lowercase the extension before comparison.
        n = make_note("20240115T093000--photo.JPG")
        out = list(check_w008(n, make_context([n])))
        assert _codes(out) == ["W008"]


class TestI002:
    def test_stub_fires(self) -> None:
        n = make_note(
            "20240115T093000.org", fm_title="x", body="   \n\n"
        )
        out = list(check_i002(n, make_context([n])))
        assert _codes(out) == ["I002"]

    def test_with_body_silent(self) -> None:
        n = make_note(
            "20240115T093000.org", fm_title="x", body="Some content.\n"
        )
        assert list(check_i002(n, make_context([n]))) == []

    def test_attachment_silent(self) -> None:
        n = make_note("20240115T093000--photo.jpg")
        assert list(check_i002(n, make_context([n]))) == []


class TestI003:
    def test_orphan_fires(self) -> None:
        n = make_note("20240115T093000.org")
        out = list(check_i003(n, make_context([n])))
        assert _codes(out) == ["I003"]

    def test_outgoing_link_silent(self) -> None:
        target = make_note("20240116T100000.org")
        n = make_note(
            "20240115T093000.org",
            links=(
                Link(target_id="20240116T100000", description=None, line=1, col=1),
            ),
        )
        ctx = make_context([n, target])
        assert list(check_i003(n, ctx)) == []

    def test_incoming_link_silent(self) -> None:
        source = make_note(
            "20240115T093000.org",
            links=(
                Link(target_id="20240116T100000", description=None, line=1, col=1),
            ),
        )
        n = make_note("20240116T100000.org")
        ctx = make_context([source, n])
        assert list(check_i003(n, ctx)) == []

    def test_attachment_silent(self) -> None:
        n = make_note("20240115T093000--photo.jpg")
        assert list(check_i003(n, make_context([n]))) == []


class TestI004:
    def test_untagged_fires(self) -> None:
        n = make_note("20240115T093000.org")
        out = list(check_i004(n, make_context([n])))
        assert _codes(out) == ["I004"]

    def test_filename_tag_silent(self) -> None:
        n = make_note("20240115T093000__t.org")
        assert list(check_i004(n, make_context([n]))) == []

    def test_frontmatter_tag_silent(self) -> None:
        n = make_note("20240115T093000.org", fm_keywords=("t",))
        assert list(check_i004(n, make_context([n]))) == []


class TestI001:
    def test_singular_plural_pair_fires(self) -> None:
        a = make_note("20240115T093000__tag.org")
        b = make_note("20240116T100000__tags.org")
        ctx = make_context([a, b])
        out = list(check_i001(ctx))
        assert _codes(out) == ["I001"]
        assert "tag" in out[0].message and "tags" in out[0].message

    def test_edit_distance_one_fires(self) -> None:
        a = make_note("20240115T093000__color.org")
        b = make_note("20240116T100000__colour.org")
        # Edit distance is 1 (insert 'u') -> fires.
        ctx = make_context([a, b])
        out = list(check_i001(ctx))
        assert _codes(out) == ["I001"]

    def test_distinct_tags_silent(self) -> None:
        a = make_note("20240115T093000__alpha.org")
        b = make_note("20240116T100000__beta.org")
        ctx = make_context([a, b])
        assert list(check_i001(ctx)) == []

    def test_each_pair_reported_once(self) -> None:
        a = make_note("20240115T093000__tag.org")
        b = make_note("20240116T100000__tag.org")  # same tag, deduped via set
        c = make_note("20240117T120000__tags.org")
        ctx = make_context([a, b, c])
        out = list(check_i001(ctx))
        assert len(out) == 1


class TestNearMiss:
    def test_singular_plural_true(self) -> None:
        assert _is_near_miss("tag", "tags") is True

    def test_same_false(self) -> None:
        assert _is_near_miss("tag", "tag") is False

    def test_completely_different_false(self) -> None:
        assert _is_near_miss("alpha", "beta") is False


class TestEditDistance:
    def test_equal(self) -> None:
        assert _edit_distance("a", "a") == 0

    def test_one_insert(self) -> None:
        assert _edit_distance("color", "colour") == 1

    def test_one_substitution(self) -> None:
        assert _edit_distance("cat", "bat") == 1

    def test_two_changes_returns_high(self) -> None:
        assert _edit_distance("alpha", "beta") > 1
