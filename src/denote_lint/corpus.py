"""File discovery, file reading, and corpus-level index construction.

The pipeline is:

1. :func:`discover_files` walks the input paths, yielding
   ``(path, indexed_only)`` tuples for files that match the configured
   extensions, honouring exclude patterns and guarding against symlink
   loops via ``(dev, inode)`` tracking. ``indexed_only`` is True for
   files under a directory marked with a ``.ignore`` file: such files
   are still loaded into the corpus index (so cross-tree denote links
   resolve) but the check phase ignores them.
2. :func:`load_note` parses a single file into a :class:`Note` (read +
   filename + front matter + links).
3. :func:`build_context` indexes the notes by identifier, computes the
   reverse link graph, and collects the global keyword set.
"""

from __future__ import annotations

import fnmatch
import os
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

from denote_lint.models import Context, FileLink, FrontMatter, Link, Note
from denote_lint.parser.filename import parse_filename
from denote_lint.parser.frontmatter import parse_frontmatter
from denote_lint.parser.links import extract_file_links, extract_links


@dataclass
class CorpusOptions:
    """Inputs to discovery and loading. Mirrors the CLI surface."""

    note_extensions: frozenset[str] = frozenset({"org", "md", "txt"})
    image_extensions: frozenset[str] = frozenset(
        {"png", "jpg", "jpeg", "gif", "svg", "webp"}
    )
    image_tag: str = "image"
    attachment_extensions: frozenset[str] = frozenset({"pdf"})
    exclude: tuple[str, ...] = ()
    follow_symlinks: bool = False
    allow_attachment_aliases: bool = False
    candidate_extensions: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if not self.candidate_extensions:
            self.candidate_extensions = (
                self.note_extensions
                | self.image_extensions
                | self.attachment_extensions
            )


def discover_files(
    paths: Iterable[Path], opts: CorpusOptions
) -> Iterator[tuple[Path, bool]]:
    """Yield ``(path, indexed_only)`` for files reachable from ``paths``.

    A file is considered if its extension is in ``candidate_extensions``
    (notes + images + other attachments by default). Files passed explicitly are yielded
    regardless of extension and are never indexed-only; directories are
    walked. A directory containing a ``.ignore`` file flips
    ``indexed_only`` to True for its whole subtree.
    """
    visited: set[tuple[int, int]] = set()
    for root in paths:
        if root.is_file():
            if not _excluded(root, opts.exclude):
                yield root, False
            continue
        if not root.is_dir():
            continue
        try:
            stat = root.stat()
        except OSError:
            continue
        visited.add((stat.st_dev, stat.st_ino))
        yield from _walk(root, opts, visited, indexed_only=False)


def _walk(
    root: Path,
    opts: CorpusOptions,
    visited: set[tuple[int, int]],
    *,
    indexed_only: bool,
) -> Iterator[tuple[Path, bool]]:
    try:
        entries = list(os.scandir(root))
    except OSError:
        return
    if _has_ignore_marker(entries):
        indexed_only = True
    for entry in entries:
        path = Path(entry.path)
        if _excluded(path, opts.exclude):
            continue
        is_symlink = entry.is_symlink()
        if is_symlink and not opts.follow_symlinks:
            continue
        try:
            is_dir = entry.is_dir(follow_symlinks=opts.follow_symlinks)
            is_file = entry.is_file(follow_symlinks=opts.follow_symlinks)
        except OSError:
            continue
        if is_dir:
            try:
                stat = entry.stat(follow_symlinks=opts.follow_symlinks)
            except OSError:
                continue
            key = (stat.st_dev, stat.st_ino)
            if key in visited:
                continue
            visited.add(key)
            yield from _walk(path, opts, visited, indexed_only=indexed_only)
        elif is_file:
            ext = _extension(path.name).lower()
            if ext in opts.candidate_extensions:
                yield path, indexed_only


def _has_ignore_marker(entries: Iterable[os.DirEntry[str]]) -> bool:
    for entry in entries:
        if entry.name == ".ignore":
            try:
                if entry.is_file():
                    return True
            except OSError:
                return False
    return False


def _extension(basename: str) -> str:
    if "." not in basename:
        return ""
    return basename.rpartition(".")[2]


def _excluded(path: Path, patterns: tuple[str, ...]) -> bool:
    if not patterns:
        return False
    name = path.name
    str_path = str(path)
    for pat in patterns:
        if fnmatch.fnmatch(name, pat) or fnmatch.fnmatch(str_path, pat):
            return True
        try:
            if path.match(pat):
                return True
        except ValueError:
            pass
    return False


def read_file(path: Path) -> tuple[str | None, str | None]:
    """Read ``path`` as UTF-8 text, BOM-stripped and CRLF-normalised.

    Returns ``(text, None)`` on success or ``(None, message)`` on
    failure (unreadable / not valid UTF-8).
    """
    try:
        raw = path.read_bytes()
    except OSError as e:
        return None, f"could not read: {e}"
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as e:
        return None, f"file is not valid UTF-8: {e}"
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text, None


def load_note(
    path: Path, opts: CorpusOptions, *, indexed_only: bool = False
) -> Note:
    """Build a :class:`Note` for a single file."""
    pf = parse_filename(path.name)
    ext = pf.extension.lower()
    is_attachment = ext not in opts.note_extensions

    text, read_error = read_file(path)
    if text is None:
        return Note(
            path=path,
            filename=pf,
            front_matter=None,
            body="",
            links=(),
            is_attachment=is_attachment,
            read_error=read_error,
            indexed_only=indexed_only,
        )

    fm: FrontMatter | None = None
    body = text
    links: tuple[Link, ...] = ()
    file_links: tuple[FileLink, ...] = ()
    if not is_attachment:
        fm, body = parse_frontmatter(ext, text)
        # body is a suffix of text, so its first line follows the prefix's.
        first_line = text.count("\n", 0, len(text) - len(body)) + 1
        links = extract_links(ext, body, first_line=first_line)
        file_links = extract_file_links(ext, body, first_line=first_line)

    return Note(
        path=path,
        filename=pf,
        front_matter=fm,
        body=body,
        links=links,
        file_links=file_links,
        is_attachment=is_attachment,
        indexed_only=indexed_only,
    )


def build_context(
    notes: list[Note],
    opts: CorpusOptions,
    *,
    corpus_roots: tuple[Path, ...] = (),
) -> Context:
    """Assemble the corpus-level index passed to checks."""
    notes_by_id: dict[str, list[Note]] = {}
    incoming: dict[str, list[Note]] = {}
    all_keywords: set[str] = set()

    for note in notes:
        ident = note.filename.identifier
        if ident:
            notes_by_id.setdefault(ident, []).append(note)
        for kw in note.filename.keywords:
            all_keywords.add(kw)
        if note.front_matter is not None:
            for kw in note.front_matter.keywords:
                all_keywords.add(kw)
        for link in note.links:
            if link.target_id:
                incoming.setdefault(link.target_id, []).append(note)

    return Context(
        notes_by_id=notes_by_id,
        incoming_links=incoming,
        all_keywords=all_keywords,
        note_extensions=opts.note_extensions,
        image_extensions=opts.image_extensions,
        image_tag=opts.image_tag,
        allow_attachment_aliases=opts.allow_attachment_aliases,
        corpus_roots=corpus_roots,
    )
