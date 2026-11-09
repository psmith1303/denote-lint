"""End-to-end test against the corpus-small fixture.

The fixture's MANIFEST.org enumerates the planted issues; this test
asserts the exact set of (filename, code) pairs emitted at default
severity. If you change a check or add a new one, update both the
fixture and the manifest accordingly.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from denote_lint.cli import run
from denote_lint.config import Config

FIXTURE = Path(__file__).parent / "fixtures" / "corpus-small"


# Each entry is (filename_in_fixture, code). One entry per emitted issue.
EXPECTED_DEFAULT_SEVERITY: list[tuple[str, str]] = [
    ("20240115T093000--clean__alpha_beta.org", "E001"),
    ("20240116T100000--mismatched-id.org", "E005"),
    ("20240117T120000--missing-title.org", "E007"),
    ("20240118T130000--missing-id.org", "E006"),
    ("20240119T140000--unsorted__zeta_alpha.org", "W001"),
    ("20240120T150000--bad-tag-chars__multi-word_tag.org", "W007"),
    ("20240123T180000--photo.jpg", "W008"),
    ("20240126T200000--invalid-link.org", "E004"),
    ("20240127T210000--titlemismatch__a.org", "W002"),
    ("20240128T220000--datemismatch__a.org", "W004"),
    ("20240129T230000--Bad-Filename.org", "E009"),
    ("20240129T230000--Bad-Filename.org", "W002"),
    ("20240130T100000--broken-file-link.org", "W006"),
    ("20240131T100000--md-broken-link.md", "W006"),
]


def _config(**kwargs: object) -> Config:
    base = {
        "paths": (FIXTURE,),
        "exclude": ("MANIFEST.org",),
        "output_format": "json",
        "quiet": True,
    }
    base.update(kwargs)
    return Config(**base)  # type: ignore[arg-type]


def _run_and_parse(cfg: Config, capsys: pytest.CaptureFixture[str]) -> dict[str, Any]:
    run(cfg)
    out = capsys.readouterr().out
    data: dict[str, Any] = json.loads(out)
    return data


def test_default_severity_exact_set(capsys: pytest.CaptureFixture[str]) -> None:
    data = _run_and_parse(_config(), capsys)
    actual = sorted(
        (Path(i["path"]).name, i["code"]) for i in data["issues"]
    )
    expected = sorted(EXPECTED_DEFAULT_SEVERITY)
    assert actual == expected
    assert data["scanned"] == 17  # 17 fixture files (excluding MANIFEST.org)


def test_severity_info_adds_orphan_untagged_and_i005(
    capsys: pytest.CaptureFixture[str],
) -> None:
    data = _run_and_parse(_config(min_severity="info"), capsys)
    issues_by_name: dict[str, list[str]] = {}
    for i in data["issues"]:
        issues_by_name.setdefault(Path(i["path"]).name, []).append(i["code"])

    orphan = issues_by_name.get("20240122T170000--orphan-untagged.org", [])
    assert "I003" in orphan
    assert "I004" in orphan


def test_disable_silences_a_code(capsys: pytest.CaptureFixture[str]) -> None:
    data = _run_and_parse(_config(disable=("E001",)), capsys)
    codes = {i["code"] for i in data["issues"]}
    assert "E001" not in codes
    # Other codes still present.
    assert "E007" in codes


def test_checks_whitelist_isolates(
    capsys: pytest.CaptureFixture[str],
) -> None:
    data = _run_and_parse(_config(checks=("W008",)), capsys)
    codes = {i["code"] for i in data["issues"]}
    assert codes == {"W008"}


def test_strict_mode_with_only_warnings_exits_one(tmp_path: Path) -> None:
    # Build a single file that only triggers a warning, then verify
    # strict promotion. We use the unsorted-keywords file directly via
    # an explicit file argument, no exclusion needed.
    src = FIXTURE / "20240119T140000--unsorted__zeta_alpha.org"
    cfg_lax = Config(
        paths=(src,), output_format="json", quiet=True
    )
    cfg_strict = Config(
        paths=(src,), output_format="json", quiet=True, strict=True
    )
    assert run(cfg_lax) == 0
    assert run(cfg_strict) == 1


def test_allow_attachment_aliases_does_not_change_two_notes(
    capsys: pytest.CaptureFixture[str],
) -> None:
    data = _run_and_parse(
        _config(allow_attachment_aliases=True), capsys
    )
    # Two .org files share an id; even with the flag, that's still E001.
    e001 = [i for i in data["issues"] if i["code"] == "E001"]
    assert len(e001) == 1
