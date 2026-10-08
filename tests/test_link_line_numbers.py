"""Link positions are file-relative, not relative to the stripped body.

Regression: front-matter parsers return only the body, so links used to be
reported at body-relative lines and Emacs ``next-error`` jumped to the wrong
place in any note with a header.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from denote_lint.corpus import CorpusOptions, load_note
from denote_lint.parser.links import extract_file_links, extract_links

ORG_LINK = "[[denote:20990101T000000][x]]"
ORG_FILE = "[[file:./missing.pdf][p]]"
MD_LINK = "[x](denote:20990101T000000)"
MD_FILE = "[p](./missing.pdf)"

# Each case: extension, content, (line, col) of the denote link, and the
# line of the file link that follows it.
CASES = [
    pytest.param(
        "org",
        "# -*- comment -*-\n:PROPERTIES:\n:ID: x\n:END:\n"
        "#+title: N\n#+identifier: 20240115T093000\n#+filetags: :t:\n\n"
        f"para\n  {ORG_LINK}\n  {ORG_FILE}\n",
        (10, 3),
        11,
        id="org-comment-drawer-keywords",
    ),
    pytest.param(
        "org", f"para\n{ORG_LINK}\n{ORG_FILE}\n", (2, 1), 3, id="org-no-header"
    ),
    pytest.param(
        "md",
        "---\ntitle: N\nidentifier: 20240115T093000\ntags: [t]\n---\n\n"
        f"para\n{MD_LINK}\n{MD_FILE}\n",
        (8, 1),
        9,
        id="md-yaml",
    ),
    pytest.param(
        "md",
        '+++\ntitle = "N"\nidentifier = "20240115T093000"\n+++\n\n'
        f"para\n{MD_LINK}\n{MD_FILE}\n",
        (7, 1),
        8,
        id="md-toml",
    ),
    pytest.param(
        "md", f"para\n{MD_LINK}\n{MD_FILE}\n", (2, 1), 3, id="md-no-front-matter"
    ),
    pytest.param(
        "md",
        f"---\ntitle: N\n---\n{MD_LINK}\n{MD_FILE}\n",
        (4, 1),
        5,
        id="md-link-directly-after-fence",
    ),
    pytest.param(
        "md",
        f"---\ntitle: N\n{MD_LINK}\n{MD_FILE}\n",
        (3, 1),
        4,
        id="md-unclosed-fence-body-is-whole-file",
    ),
]


@pytest.mark.parametrize(("ext", "content", "link_pos", "file_line"), CASES)
def test_links_report_file_lines(
    tmp_path: Path,
    ext: str,
    content: str,
    link_pos: tuple[int, int],
    file_line: int,
) -> None:
    f = tmp_path / f"20240115T093000--n.{ext}"
    f.write_text(content, encoding="utf-8")
    note = load_note(f, CorpusOptions())
    assert [(lk.line, lk.col) for lk in note.links] == [link_pos]
    assert [fl.line for fl in note.file_links] == [file_line]


def test_link_inside_code_block_does_not_shift_lines(tmp_path: Path) -> None:
    content = (
        "#+title: N\n#+identifier: 20240115T093000\n\n"
        "#+begin_src sh\n[[denote:20990101T000009]]\n#+end_src\n"
        f"{ORG_LINK}\n"
    )
    f = tmp_path / "20240115T093000--n.org"
    f.write_text(content, encoding="utf-8")
    note = load_note(f, CorpusOptions())
    assert [lk.line for lk in note.links] == [7]


def test_crlf_file_lines_match(tmp_path: Path) -> None:
    content = f"#+title: N\n#+identifier: 20240115T093000\n\npara\n{ORG_LINK}\n"
    f = tmp_path / "20240115T093000--n.org"
    f.write_bytes(content.replace("\n", "\r\n").encode())
    assert [lk.line for lk in load_note(f, CorpusOptions()).links] == [5]


def test_extractors_default_to_body_relative_lines() -> None:
    """Direct callers that pass no ``first_line`` keep the old behaviour."""
    body = f"a\n{ORG_LINK}\n{ORG_FILE}\n"
    assert [lk.line for lk in extract_links("org", body)] == [2]
    assert [fl.line for fl in extract_file_links("org", body)] == [3]
    assert extract_links("org", body, first_line=10)[0].line == 11
    assert extract_file_links("org", body, first_line=10)[0].line == 12


@pytest.mark.parametrize("ext", ["org", "md", "txt"])
def test_header_only_file_without_trailing_newline(tmp_path: Path, ext: str) -> None:
    f = tmp_path / f"20240115T093000--n.{ext}"
    f.write_text("#+title: N" if ext == "org" else "---\ntitle: N\n---", encoding="utf-8")
    assert load_note(f, CorpusOptions()).links == ()
