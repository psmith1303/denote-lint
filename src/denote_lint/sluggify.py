"""Python re-implementation of Denote's default sluggifiers.

Mirrors ``denote-sluggify-and-apply-rules`` and its component-specific
helpers in ``denote.el``. Used both for canonical-form validation
(:mod:`denote_lint.parser.filename`) and for slug-equivalence checks
(W002 in :mod:`denote_lint.checks.frontmatter`).

The shape is:

1. Strip a component-specific blocklist of punctuation.
2. Hyphenate (titles) or equal-sign (signatures) word separators.
3. Lowercase.
4. Trim trailing token characters.

Non-ASCII letters are preserved at every step — Denote's default
sluggifier does not ASCII-fold.

If upstream Denote changes its strip set, update the blocklists here
and re-check the trim/collapse helpers.
"""

from __future__ import annotations

import re

# Mirrored verbatim from denote.el's `denote-sluggify-title`,
# `denote-sluggify-signature`, and `denote-sluggify-keyword`.
TITLE_BLOCKLIST = frozenset("[]{}!@#$%^&*()+'\"?,.|;:~`‘’“”/=")  # noqa: RUF001
SIGNATURE_BLOCKLIST = frozenset("[]{}!@#$%^&*()+'\"?,.|;:~`‘’“”/-")  # noqa: RUF001
KEYWORD_BLOCKLIST = frozenset("[]{}!@#$%^&*()+'\"?,.|;:~`‘’“”/_ =-")  # noqa: RUF001

_WS_OR_UNDERSCORE_RE = re.compile(r"[_\s]+")
_HYPHEN_RUN_RE = re.compile(r"-{2,}")
_EQUALS_RUN_RE = re.compile(r"={2,}")
_AT_RUN_RE = re.compile(r"@{2,}")
_TITLE_RIGHT_TRIM_RE = re.compile(r"[=@_]+$")
_NON_TITLE_RIGHT_TRIM_RE = re.compile(r"[=@_-]+$")


def _strip_blocklist(s: str, blocklist: frozenset[str]) -> str:
    return "".join(ch for ch in s if ch not in blocklist)


def _slug_hyphenate(s: str) -> str:
    """Mirror of ``denote-slug-hyphenate``."""
    s = _WS_OR_UNDERSCORE_RE.sub("-", s)
    s = _HYPHEN_RUN_RE.sub("-", s)
    return s.strip("-")


def _slug_put_equals(s: str) -> str:
    """Mirror of ``denote-slug-put-equals``."""
    s = _WS_OR_UNDERSCORE_RE.sub("=", s)
    s = _EQUALS_RUN_RE.sub("=", s)
    return s.strip("=")


def sluggify_title(s: str) -> str:
    """Reproduce ``(denote-sluggify-and-apply-rules 'title s)``."""
    out = _strip_blocklist(s, TITLE_BLOCKLIST)
    out = _slug_hyphenate(out)
    out = out.lower()
    out = _AT_RUN_RE.sub("@", out)
    return _TITLE_RIGHT_TRIM_RE.sub("", out)


def sluggify_signature(s: str) -> str:
    """Reproduce ``(denote-sluggify-and-apply-rules 'signature s)``."""
    out = _strip_blocklist(s, SIGNATURE_BLOCKLIST)
    out = _slug_put_equals(out)
    out = out.lower()
    out = _AT_RUN_RE.sub("@", out)
    return _NON_TITLE_RIGHT_TRIM_RE.sub("", out)


def sluggify_keyword(s: str) -> str:
    """Reproduce ``(denote-sluggify-and-apply-rules 'keyword s)``."""
    out = _strip_blocklist(s, KEYWORD_BLOCKLIST)
    out = out.lower()
    out = _AT_RUN_RE.sub("@", out)
    return _NON_TITLE_RIGHT_TRIM_RE.sub("", out)
