"""Configuration: severity ranking, the Config dataclass, and code resolution."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from denote_lint.models import Severity

OutputFormat = Literal["compilation", "json", "text"]

SEVERITY_RANK: dict[Severity, int] = {"info": 1, "warning": 2, "error": 3}


@dataclass
class Config:
    """Resolved configuration. Built once from CLI args."""

    paths: tuple[Path, ...] = ()
    output_format: OutputFormat = "compilation"
    min_severity: Severity = "warning"
    checks: tuple[str, ...] = ()
    disable: tuple[str, ...] = ()
    note_extensions: frozenset[str] = frozenset({"org", "md", "txt"})
    image_extensions: frozenset[str] = frozenset(
        {"png", "jpg", "jpeg", "gif", "svg", "webp"}
    )
    image_tag: str = "image"
    attachment_extensions: frozenset[str] = frozenset({"pdf"})
    exclude: tuple[str, ...] = ()
    follow_symlinks: bool = False
    strict: bool = False
    no_color: bool = False
    quiet: bool = False
    verbose: bool = False
    allow_attachment_aliases: bool = False

    def enabled_codes(self) -> frozenset[str]:
        """Return the codes that should run, after applying --checks /
        --disable / --severity rules.

        --checks acts as a whitelist; if it's set, --severity is ignored
        for selection. --disable always subtracts. The intersection of
        --checks and --disable resolves in --disable's favour.
        """
        from denote_lint.checks import REGISTRY

        if self.checks:
            base = set(self.checks) & set(REGISTRY)
        else:
            floor = SEVERITY_RANK[self.min_severity]
            base = {
                code
                for code, record in REGISTRY.items()
                if SEVERITY_RANK[record.severity] >= floor
            }
        base -= set(self.disable)
        return frozenset(base)
