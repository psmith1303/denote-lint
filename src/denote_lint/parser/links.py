"""Denote-link and file-link extraction from note bodies.

Org denote syntax::

    [[denote:20240115T093000]]
    [[denote:20240115T093000][Description text]]
    [[denote:20240115T093000::*Some heading]]

Markdown denote syntax::

    [Description text](denote:20240115T093000)

The ``::SEARCH`` suffix is org-only; we strip it from the target id but
preserve nothing else about it.

Org file-shaped links (handled by :func:`extract_file_links`):

    [[file:./other.org]]
    [[file:/abs/path.pdf][Description]]
    [[file:./notes.org::*Heading]]
    [[./bare-relative.org]]
    [[../parent/note.org]]
    [[/abs/from/root]]
    [[~/under-home]]

Markdown file-shaped links: any inline link whose target has no URI
scheme is treated as a path::

    [Description](./other.md)
    [alt](images/foo.png)

URLs (``http://...``, ``mailto:...``) and ``denote:...`` targets are
deliberately filtered out: they're not in scope for W006.

Code regions (org ``#+begin_src`` / ``#+begin_example`` blocks and
markdown ```` ``` ```` / ``~~~`` fences) are masked out before
extraction so links inside them don't false-positive E004 / I005 /
W006.
"""

from __future__ import annotations

import re

from denote_lint.models import FileLink, Link

_ORG_DENOTE_LINK_RE = re.compile(
    r"\[\[denote:(?P<target>[^\]\n]+?)\](?:\[(?P<desc>[^\]\n]+?)\])?\]"
)
_MD_DENOTE_LINK_RE = re.compile(
    r"\[(?P<desc>[^\]\n]*?)\]\(denote:(?P<target>[^)\n]+?)\)"
)
_ORG_BRACKET_RE = re.compile(
    r"\[\[(?P<target>[^\]\n]+?)\](?:\[(?P<desc>[^\]\n]+?)\])?\]"
)
_MD_INLINE_RE = re.compile(
    r"\[(?P<desc>[^\]\n]*?)\]\((?P<target>[^)\n]+?)\)"
)
# RFC 3986 scheme: ALPHA *( ALPHA / DIGIT / "+" / "-" / "." ) ":"
_URI_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+\-.]*:")
_ORG_BLOCK_BEGIN_RE = re.compile(
    r"^[ \t]*#\+begin_(src|example)\b", re.IGNORECASE
)
_ORG_BLOCK_END_RE = re.compile(
    r"^[ \t]*#\+end_(src|example)\b", re.IGNORECASE
)
_MD_FENCE_OPEN_RE = re.compile(r"^[ \t]*(`{3,}|~{3,})")


def extract_links(
    extension: str, body: str, *, first_line: int = 1
) -> tuple[Link, ...]:
    """Return all ``denote:`` links found in ``body``.

    ``first_line`` is the file line number of the body's first line, so
    reported positions are file-relative rather than body-relative.

    Code regions are masked out first so that links inside source or
    example blocks do not generate false E004 / I005.
    """
    ext = extension.lower()
    if ext == "org":
        regex = _ORG_DENOTE_LINK_RE
    elif ext == "md":
        regex = _MD_DENOTE_LINK_RE
    else:
        return ()
    masked = _mask_code_blocks(ext, body)

    links: list[Link] = []
    for m in regex.finditer(masked):
        target = m.group("target")
        desc = m.group("desc")
        target_id, _, _ = target.partition("::")
        target_id = target_id.strip()
        line, col = _line_col(masked, m.start(), first_line)
        links.append(
            Link(
                target_id=target_id,
                description=desc.strip() if desc else None,
                line=line,
                col=col,
            )
        )
    return tuple(links)


def extract_file_links(
    extension: str, body: str, *, first_line: int = 1
) -> tuple[FileLink, ...]:
    """Return file-shaped links found in ``body``.

    Org: ``file:`` prefix or bare paths starting with ``/``, ``./``,
    ``../``, ``~/``. Heading / search-term / anchor links
    (``[[*Heading]]``, ``[[#id]]``, ``[[search]]``) are filtered out.

    Markdown: any inline ``[text](target)`` where the target has no URI
    scheme. Optional CommonMark titles (``"Title"`` / ``'Title'``) and
    URL fragments / queries are stripped before resolution.

    Code regions are masked out first. ``first_line`` is as for
    :func:`extract_links`.
    """
    ext = extension.lower()
    if ext not in ("org", "md"):
        return ()
    masked = _mask_code_blocks(ext, body)
    if ext == "org":
        return _extract_org_file_links(masked, first_line)
    return _extract_md_file_links(masked, first_line)


def _extract_org_file_links(body: str, first_line: int) -> tuple[FileLink, ...]:
    links: list[FileLink] = []
    for m in _ORG_BRACKET_RE.finditer(body):
        path = _normalize_org_file_target(m.group("target"))
        if path is None:
            continue
        line, col = _line_col(body, m.start(), first_line)
        desc = m.group("desc")
        links.append(
            FileLink(
                target=path,
                description=desc.strip() if desc else None,
                line=line,
                col=col,
            )
        )
    return tuple(links)


def _extract_md_file_links(body: str, first_line: int) -> tuple[FileLink, ...]:
    links: list[FileLink] = []
    for m in _MD_INLINE_RE.finditer(body):
        path = _normalize_md_file_target(m.group("target"))
        if path is None:
            continue
        line, col = _line_col(body, m.start(), first_line)
        desc = m.group("desc")
        links.append(
            FileLink(
                target=path,
                description=desc.strip() if desc else None,
                line=line,
                col=col,
            )
        )
    return tuple(links)


def _normalize_org_file_target(target: str) -> str | None:
    """Return a filesystem path for an org link target, or ``None`` if
    the link isn't file-shaped.

    Strips the org ``::SEARCH`` suffix, recognises an explicit
    ``file:`` prefix, and otherwise accepts only paths with an
    unambiguous prefix (``/``, ``./``, ``../``, ``~/``). Anything with
    another URI scheme or that looks like an internal org link is
    rejected so we don't false-positive on ``[[*Heading]]`` /
    ``[[#anchor]]`` / search-term links.
    """
    path, _, _ = target.partition("::")
    path = path.strip()
    if not path:
        return None
    if path.startswith("file:"):
        bare = path[len("file:") :].strip()
        return bare or None
    if _URI_SCHEME_RE.match(path):
        return None
    if path.startswith(("/", "./", "../", "~/")):
        return path
    return None


def _normalize_md_file_target(raw: str) -> str | None:
    """Return a filesystem path for a markdown link target, or ``None``
    if it isn't file-shaped.

    Strips a CommonMark-style trailing title (``"text"`` / ``'text'``)
    and any URL ``#fragment`` / ``?query``. Targets with a URI scheme
    are rejected; what remains is treated as a path.
    """
    target = raw.strip()
    if not target:
        return None
    target = _strip_md_title(target)
    if _URI_SCHEME_RE.match(target):
        return None
    target, _, _ = target.partition("#")
    target, _, _ = target.partition("?")
    target = target.strip()
    return target or None


def _strip_md_title(target: str) -> str:
    """Strip a trailing ``"title"`` or ``'title'`` from a markdown link
    target. The space before the quote is the disambiguator: a path
    with embedded spaces but no quotes is left intact.
    """
    for quote in ('"', "'"):
        idx = target.rfind(f" {quote}")
        if idx >= 0 and target.rstrip().endswith(quote):
            return target[:idx].rstrip()
    return target


def _mask_code_blocks(extension: str, body: str) -> str:
    """Replace text inside fenced regions with spaces, leaving newlines
    intact so line/col offsets are unchanged.

    Org: ``#+begin_src`` / ``#+begin_example`` ... ``#+end_src`` /
    ``#+end_example``. Org quote and verse blocks are intentionally
    left alone -- they carry meaningful prose and links.

    Markdown: ```` ``` ```` and ``~~~`` fences (CommonMark info-string
    handling: closing fence must be the same character, at least as
    long as the opener, on its own line).
    """
    if extension == "org":
        return _mask_org_blocks(body)
    if extension == "md":
        return _mask_md_fences(body)
    return body


def _mask_org_blocks(body: str) -> str:
    chars = list(body)
    in_block = False
    pos = 0
    for line in body.split("\n"):
        line_len = len(line)
        if not in_block:
            if _ORG_BLOCK_BEGIN_RE.match(line):
                in_block = True
        else:
            if _ORG_BLOCK_END_RE.match(line):
                in_block = False
            else:
                for i in range(pos, pos + line_len):
                    chars[i] = " "
        pos += line_len + 1  # +1 for the \n that split() consumed
    return "".join(chars)


def _mask_md_fences(body: str) -> str:
    chars = list(body)
    fence_char: str | None = None
    fence_len = 0
    pos = 0
    for line in body.split("\n"):
        line_len = len(line)
        if fence_char is None:
            m = _MD_FENCE_OPEN_RE.match(line)
            if m:
                tok = m.group(1)
                fence_char = tok[0]
                fence_len = len(tok)
        else:
            stripped = line.strip()
            if (
                stripped
                and len(stripped) >= fence_len
                and all(c == fence_char for c in stripped)
            ):
                fence_char = None
                fence_len = 0
            else:
                for i in range(pos, pos + line_len):
                    chars[i] = " "
        pos += line_len + 1
    return "".join(chars)


def _line_col(text: str, offset: int, first_line: int) -> tuple[int, int]:
    line_start = text.rfind("\n", 0, offset) + 1
    line = text.count("\n", 0, offset) + first_line
    col = offset - line_start + 1
    return line, col
