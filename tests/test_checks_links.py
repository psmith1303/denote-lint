"""Link check coverage: E004, W006, I005."""

from __future__ import annotations

from pathlib import Path

import pytest

from denote_lint.checks.links import check_e004, check_i005, check_w006
from denote_lint.models import FileLink, Issue, Link
from tests.conftest import make_context, make_note


def _codes(issues: list[Issue]) -> list[str]:
    return [i.code for i in issues]


class TestE004:
    def test_target_missing_fires(self) -> None:
        a = make_note(
            "20240115T093000.org",
            links=(Link(target_id="20990101T000000", description=None, line=2, col=3),),
        )
        ctx = make_context([a])
        out = list(check_e004(a, ctx))
        assert _codes(out) == ["E004"]
        assert out[0].line == 2
        assert out[0].col == 3
        assert "20990101T000000" in out[0].message

    def test_target_present_silent(self) -> None:
        a = make_note(
            "20240115T093000.org",
            links=(Link(target_id="20240116T100000", description=None, line=1, col=1),),
        )
        b = make_note("20240116T100000.org")
        ctx = make_context([a, b])
        assert list(check_e004(a, ctx)) == []

    def test_empty_target_id_fires(self) -> None:
        a = make_note(
            "20240115T093000.org",
            links=(Link(target_id="", description=None, line=1, col=1),),
        )
        out = list(check_e004(a, make_context([a])))
        assert _codes(out) == ["E004"]
        assert "no identifier" in out[0].message


class TestI005:
    def test_description_mismatch_fires(self) -> None:
        target = make_note(
            "20240116T100000.org", fm_title="Real Title"
        )
        source = make_note(
            "20240115T093000.org",
            links=(
                Link(
                    target_id="20240116T100000",
                    description="Old Description",
                    line=1,
                    col=1,
                ),
            ),
        )
        ctx = make_context([source, target])
        out = list(check_i005(source, ctx))
        assert _codes(out) == ["I005"]

    def test_description_match_silent(self) -> None:
        target = make_note("20240116T100000.org", fm_title="Same")
        source = make_note(
            "20240115T093000.org",
            links=(
                Link(
                    target_id="20240116T100000",
                    description="Same",
                    line=1,
                    col=1,
                ),
            ),
        )
        ctx = make_context([source, target])
        assert list(check_i005(source, ctx)) == []

    def test_no_description_silent(self) -> None:
        target = make_note("20240116T100000.org", fm_title="Title")
        source = make_note(
            "20240115T093000.org",
            links=(
                Link(
                    target_id="20240116T100000",
                    description=None,
                    line=1,
                    col=1,
                ),
            ),
        )
        ctx = make_context([source, target])
        assert list(check_i005(source, ctx)) == []

    def test_target_missing_silent(self) -> None:
        source = make_note(
            "20240115T093000.org",
            links=(
                Link(
                    target_id="20990101T000000",
                    description="Whatever",
                    line=1,
                    col=1,
                ),
            ),
        )
        ctx = make_context([source])
        # I005 is silent when target isn't in the corpus; E004 covers that case.
        assert list(check_i005(source, ctx)) == []


class TestW006:
    @pytest.fixture
    def corpus_root(self, tmp_path: Path) -> Path:
        (tmp_path / "20240115T093000--note.org").write_text("hi", encoding="utf-8")
        (tmp_path / "existing.pdf").write_bytes(b"%PDF-1.4\n")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "child.org").write_text("hi", encoding="utf-8")
        return tmp_path.resolve()

    def test_existing_relative_target_silent(self, corpus_root: Path) -> None:
        note = make_note(
            "20240115T093000--note.org",
            path=corpus_root / "20240115T093000--note.org",
            file_links=(
                FileLink(target="./existing.pdf", description=None, line=1, col=1),
            ),
        )
        ctx = make_context([note], corpus_roots=(corpus_root,))
        assert list(check_w006(note, ctx)) == []

    def test_missing_relative_target_fires(self, corpus_root: Path) -> None:
        note = make_note(
            "20240115T093000--note.org",
            path=corpus_root / "20240115T093000--note.org",
            file_links=(
                FileLink(target="./missing.pdf", description=None, line=4, col=8),
            ),
        )
        ctx = make_context([note], corpus_roots=(corpus_root,))
        out = list(check_w006(note, ctx))
        assert _codes(out) == ["W006"]
        assert out[0].line == 4
        assert out[0].col == 8
        assert "missing.pdf" in out[0].message

    def test_missing_target_in_subdir_fires(self, corpus_root: Path) -> None:
        note = make_note(
            "20240115T093000--note.org",
            path=corpus_root / "20240115T093000--note.org",
            file_links=(
                FileLink(target="./sub/nope.org", description=None, line=1, col=1),
            ),
        )
        ctx = make_context([note], corpus_roots=(corpus_root,))
        assert _codes(list(check_w006(note, ctx))) == ["W006"]

    def test_existing_target_in_subdir_silent(self, corpus_root: Path) -> None:
        note = make_note(
            "20240115T093000--note.org",
            path=corpus_root / "20240115T093000--note.org",
            file_links=(
                FileLink(target="./sub/child.org", description=None, line=1, col=1),
            ),
        )
        ctx = make_context([note], corpus_roots=(corpus_root,))
        assert list(check_w006(note, ctx)) == []

    def test_out_of_corpus_target_silent(
        self, corpus_root: Path, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        # A path that resolves outside any corpus root must be skipped
        # even if the file does not exist -- we have no authority over
        # the user's broader filesystem.
        elsewhere = tmp_path_factory.mktemp("elsewhere").resolve()
        note = make_note(
            "20240115T093000--note.org",
            path=corpus_root / "20240115T093000--note.org",
            file_links=(
                FileLink(
                    target=str(elsewhere / "missing.pdf"),
                    description=None,
                    line=1,
                    col=1,
                ),
            ),
        )
        ctx = make_context([note], corpus_roots=(corpus_root,))
        assert list(check_w006(note, ctx)) == []

    def test_no_corpus_roots_silent(self, corpus_root: Path) -> None:
        # Without configured roots W006 is a no-op rather than warning
        # on every file: link.
        note = make_note(
            "20240115T093000--note.org",
            path=corpus_root / "20240115T093000--note.org",
            file_links=(
                FileLink(target="./missing.pdf", description=None, line=1, col=1),
            ),
        )
        ctx = make_context([note])
        assert list(check_w006(note, ctx)) == []

