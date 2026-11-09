"""Reporter coverage."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from denote_lint.models import Issue
from denote_lint.reporter import (
    Report,
    color_enabled,
    format_compilation,
    format_json,
    format_summary,
    format_text,
    sort_issues,
)


def _i(path: str, line: int, col: int, severity: str, code: str, msg: str) -> Issue:
    return Issue(
        path=Path(path),
        line=line,
        col=col,
        severity=severity,  # type: ignore[arg-type]
        code=code,
        message=msg,
    )


class TestCompilation:
    def test_basic_format(self) -> None:
        rep = Report(
            issues=[_i("/n/a.org", 1, 1, "error", "E001", "dup id 20240115T093000")],
            scanned=1,
            elapsed=0.0,
        )
        out = format_compilation(rep)
        assert out == "/n/a.org:1:1: error[E001]: dup id 20240115T093000"

    def test_empty(self) -> None:
        rep = Report(issues=[], scanned=0, elapsed=0.0)
        assert format_compilation(rep) == ""

    def test_sort_by_path_then_line(self) -> None:
        rep = Report(
            issues=[
                _i("/n/b.org", 1, 1, "error", "E001", "x"),
                _i("/n/a.org", 5, 1, "error", "E001", "x"),
                _i("/n/a.org", 1, 1, "error", "E001", "x"),
            ],
            scanned=2,
            elapsed=0.0,
        )
        out = format_compilation(rep)
        lines = out.splitlines()
        assert lines[0].startswith("/n/a.org:1:1")
        assert lines[1].startswith("/n/a.org:5:1")
        assert lines[2].startswith("/n/b.org:1:1")


class TestJson:
    def test_basic(self) -> None:
        rep = Report(
            issues=[_i("/n/a.org", 1, 1, "error", "E001", "msg")],
            scanned=3,
            elapsed=0.0,
        )
        out = format_json(rep, "0.1.0")
        data = json.loads(out)
        assert data["version"] == "0.1.0"
        assert data["scanned"] == 3
        assert len(data["issues"]) == 1
        assert data["issues"][0]["code"] == "E001"
        assert data["issues"][0]["path"] == "/n/a.org"

    def test_empty_issues(self) -> None:
        rep = Report(issues=[], scanned=10, elapsed=0.0)
        data = json.loads(format_json(rep, "0.1.0"))
        assert data["issues"] == []


class TestText:
    def test_groups_by_file(self) -> None:
        rep = Report(
            issues=[
                _i("/n/a.org", 1, 1, "error", "E001", "x"),
                _i("/n/b.org", 1, 1, "warning", "W001", "y"),
                _i("/n/a.org", 5, 1, "info", "I001", "z"),
            ],
            scanned=2,
            elapsed=0.0,
        )
        out = format_text(rep, use_color=False)
        # File a's heading appears before file b's.
        assert out.index("/n/a.org") < out.index("/n/b.org")
        # Indented severity bodies present.
        assert "error[E001]: x" in out
        assert "warning[W001]: y" in out
        assert "info[I001]: z" in out

    def test_color_codes_when_enabled(self) -> None:
        rep = Report(
            issues=[_i("/n/a.org", 1, 1, "error", "E001", "x")],
            scanned=1,
            elapsed=0.0,
        )
        out = format_text(rep, use_color=True)
        assert "\x1b[31m" in out  # red for error
        assert "\x1b[1m" in out   # bold for path

    def test_no_color_when_disabled(self) -> None:
        rep = Report(
            issues=[_i("/n/a.org", 1, 1, "error", "E001", "x")],
            scanned=1,
            elapsed=0.0,
        )
        out = format_text(rep, use_color=False)
        assert "\x1b[" not in out


class TestSummary:
    def test_counts(self) -> None:
        rep = Report(
            issues=[
                _i("/n/a.org", 1, 1, "error", "E001", "x"),
                _i("/n/a.org", 1, 1, "error", "E002", "x"),
                _i("/n/a.org", 1, 1, "warning", "W001", "x"),
                _i("/n/a.org", 1, 1, "info", "I001", "x"),
            ],
            scanned=10,
            elapsed=0.42,
        )
        out = format_summary(rep)
        assert "scanned 10 files" in out
        assert "2 errors" in out
        assert "1 warnings" in out
        assert "1 info" in out
        assert "0.4s" in out


class TestColorEnabled:
    def test_no_color_flag_disables(self) -> None:
        assert color_enabled(no_color_flag=True) is False

    def test_no_color_env_disables(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NO_COLOR", "1")
        assert color_enabled(no_color_flag=False) is False

    def test_non_tty_disables(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("NO_COLOR", raising=False)

        class _NotTTY:
            def isatty(self) -> bool:
                return False

        assert color_enabled(no_color_flag=False, stream=_NotTTY()) is False

    def test_tty_enables(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("NO_COLOR", raising=False)

        class _TTY:
            def isatty(self) -> bool:
                return True

        assert color_enabled(no_color_flag=False, stream=_TTY()) is True


class TestSortIssues:
    def test_stable_sort(self) -> None:
        a = _i("/x.org", 1, 1, "error", "E001", "x")
        b = _i("/x.org", 1, 1, "error", "E002", "y")
        out = sort_issues([b, a])
        assert out == [a, b]
