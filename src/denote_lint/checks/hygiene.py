"""Hygiene checks: W008 (image-needs-tag), I001 (near-duplicate tags),
I002 (stub note), I003 (orphan), I004 (untagged).
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from denote_lint.checks import register_corpus, register_per_note
from denote_lint.models import Context, Issue, Note


def _issue(note: Note, code: str, severity: str, message: str) -> Issue:
    return Issue(
        path=note.path,
        line=1,
        col=1,
        severity=severity,  # type: ignore[arg-type]
        code=code,
        message=message,
    )


@register_per_note("W008", "warning", "policy")
def check_w008(note: Note, ctx: Context) -> Iterable[Issue]:
    ext = note.filename.extension.lower()
    if ext not in ctx.image_extensions:
        return
    if ctx.image_tag == '' or ctx.image_tag in note.filename.keywords:
        return
    if note.front_matter is not None and ctx.image_tag in note.front_matter.keywords:
        return
    yield _issue(
        note,
        "W008",
        "warning",
        f"image file is missing the {ctx.image_tag!r} keyword",
    )


@register_per_note("I002", "info", "hygiene")
def check_i002(note: Note, _ctx: Context) -> Iterable[Issue]:
    if note.is_attachment or note.front_matter is None:
        return
    if note.read_error is not None:
        return
    if note.body.strip():
        return
    yield _issue(note, "I002", "info", "stub note (front matter only, no body)")


@register_per_note("I003", "info", "hygiene")
def check_i003(note: Note, ctx: Context) -> Iterable[Issue]:
    if note.is_attachment:
        return
    ident = note.filename.identifier
    if not ident:
        return
    has_outgoing = any(link.target_id for link in note.links)
    has_incoming = bool(ctx.incoming_links.get(ident))
    if has_outgoing or has_incoming:
        return
    yield _issue(
        note, "I003", "info", "orphan note (no incoming or outgoing denote links)"
    )


@register_per_note("I004", "info", "hygiene")
def check_i004(note: Note, _ctx: Context) -> Iterable[Issue]:
    if note.is_attachment:
        return
    if note.filename.keywords:
        return
    if note.front_matter is not None and note.front_matter.keywords:
        return
    yield _issue(note, "I004", "info", "untagged note (no keywords)")


@register_corpus("I001", "info", "hygiene")
def check_i001(ctx: Context) -> Iterable[Issue]:
    """Probable duplicate tag: pairs differing only by trailing 's' or
    edit distance 1. Reported once per pair, anchored to the first note
    holding either tag (so compilation-mode navigation lands somewhere
    real).
    """
    keyword_to_path: dict[str, Path] = {}
    # Prefer to anchor to a checked (non-indexed-only) note so the issue
    # survives orchestrator filtering and lands somewhere in the user's
    # lint scope.
    for indexed_only in (False, True):
        for notes in ctx.notes_by_id.values():
            for note in notes:
                if note.indexed_only is not indexed_only:
                    continue
                for kw in note.filename.keywords:
                    keyword_to_path.setdefault(kw, note.path)
                if note.front_matter is not None:
                    for kw in note.front_matter.keywords:
                        keyword_to_path.setdefault(kw, note.path)

    keywords = sorted(ctx.all_keywords)
    seen_pairs: set[tuple[str, str]] = set()
    for i, a in enumerate(keywords):
        for b in keywords[i + 1 :]:
            if not _is_near_miss(a, b):
                continue
            pair = (a, b)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            anchor = keyword_to_path.get(a) or keyword_to_path.get(b) or Path("<corpus>")
            yield Issue(
                path=anchor,
                line=1,
                col=1,
                severity="info",
                code="I001",
                message=f"probable duplicate tag pair: {a!r} and {b!r}",
            )


def _is_near_miss(a: str, b: str) -> bool:
    if a == b:
        return False
    if a + "s" == b or b + "s" == a:
        return True
    return _edit_distance(a, b) <= 1


def _edit_distance(a: str, b: str) -> int:
    """Levenshtein distance, with an early bail when the answer would
    exceed 1. Cheap enough for the small tag sets we expect.
    """
    if a == b:
        return 0
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return 99
    if la > lb:
        a, b, la, lb = b, a, lb, la
    if la == lb:
        diff = sum(1 for x, y in zip(a, b) if x != y)
        return diff
    for i in range(lb):
        if b[:i] + b[i + 1 :] == a:
            return 1
    return 99
