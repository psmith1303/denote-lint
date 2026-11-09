"""Filename-level check coverage."""

from __future__ import annotations

from denote_lint.checks.filename import (
    check_e002,
    check_e003,
    check_e009,
    check_e010,
    check_w001,
    check_w007,
)
from denote_lint.models import Issue
from tests.conftest import make_context, make_note


def _codes(issues: list[Issue]) -> list[str]:
    return [i.code for i in issues]


class TestE002:
    def test_fires_on_bad_id_shape(self) -> None:
        n = make_note("not-an-id.org")
        out = list(check_e002(n, make_context([n])))
        assert _codes(out) == ["E002"]

    def test_silent_on_good_id(self) -> None:
        n = make_note("20240115T093000.org")
        assert list(check_e002(n, make_context([n]))) == []


class TestE003:
    def test_fires_on_invalid_date(self) -> None:
        n = make_note("20240230T093000.org")
        out = list(check_e003(n, make_context([n])))
        assert _codes(out) == ["E003"]

    def test_silent_on_valid_date(self) -> None:
        n = make_note("20240115T093000.org")
        assert list(check_e003(n, make_context([n]))) == []


class TestE009:
    def test_fires_on_uppercase(self) -> None:
        n = make_note("20240115T093000--Bad.org")
        out = list(check_e009(n, make_context([n])))
        assert _codes(out) == ["E009"]

    def test_silent_on_well_formed(self) -> None:
        n = make_note("20240115T093000--good.org")
        assert list(check_e009(n, make_context([n]))) == []


class TestE010:
    def test_fires_on_trailing_double_underscore(self) -> None:
        n = make_note("20240115T093000__tag1__.org")
        out = list(check_e010(n, make_context([n])))
        assert _codes(out) == ["E010"]

    def test_silent_on_clean_keywords(self) -> None:
        n = make_note("20240115T093000__tag1.org")
        assert list(check_e010(n, make_context([n]))) == []


class TestW001:
    def test_fires_when_unsorted(self) -> None:
        n = make_note("20240115T093000__zeta_alpha.org")
        out = list(check_w001(n, make_context([n])))
        assert _codes(out) == ["W001"]
        assert "zeta" in out[0].message
        assert "alpha" in out[0].message

    def test_silent_when_sorted(self) -> None:
        n = make_note("20240115T093000__alpha_zeta.org")
        assert list(check_w001(n, make_context([n]))) == []

    def test_silent_with_single_keyword(self) -> None:
        n = make_note("20240115T093000__alpha.org")
        assert list(check_w001(n, make_context([n]))) == []


class TestW007:
    def test_fires_on_dashed_keyword(self) -> None:
        n = make_note("20240115T093000__multi-word_other.org")
        out = list(check_w007(n, make_context([n])))
        assert _codes(out) == ["W007"]
