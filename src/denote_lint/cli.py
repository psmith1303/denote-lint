"""Top-level CLI: argument parsing, orchestration, exit codes.

Pipeline (per the spec):

1. Resolve config from argv.
2. Discover files honouring extensions / exclude / follow-symlinks.
3. First pass: load each file into a Note.
4. Corpus pass: build identifier index and link graph.
5. Run enabled checks.
6. Render via the chosen reporter; emit summary to stderr unless --quiet.
7. Exit 0/1/2 according to the spec.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Sequence
from pathlib import Path

from denote_lint import __version__
from denote_lint.checks import run_checks
from denote_lint.config import Config
from denote_lint.corpus import (
    CorpusOptions,
    build_context,
    discover_files,
    load_note,
)
from denote_lint.reporter import (
    Report,
    color_enabled,
    format_compilation,
    format_json,
    format_summary,
    format_text,
)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="denote-lint",
        description="Static analysis for Emacs Denote note collections.",
    )
    p.add_argument("paths", nargs="+", type=Path, help="Files or directories to scan.")
    p.add_argument(
        "--format",
        choices=["compilation", "json", "text"],
        default="compilation",
        help="Output format (default: compilation).",
    )
    p.add_argument(
        "--severity",
        choices=["error", "warning", "info"],
        default="warning",
        help="Minimum severity to report (default: warning).",
    )
    p.add_argument(
        "--checks",
        default="",
        help="Comma-separated codes to enable exclusively (whitelist).",
    )
    p.add_argument(
        "--disable",
        default="",
        help="Comma-separated codes to disable.",
    )
    p.add_argument(
        "--extensions",
        default="org,md,txt",
        help="File extensions to treat as notes (default: org,md,txt).",
    )
    p.add_argument(
        "--image-extensions",
        default="png,jpg,jpeg,gif,svg,webp",
        help="Extensions treated as images for W008.",
    )
    p.add_argument(
        "--image-tag",
        default="image",
        help="Required keyword for image files (default: image).",
    )
    p.add_argument(
        "--attachment-extensions",
        default="pdf",
        help="Other extensions indexed as attachments so links to them "
        "resolve; not subject to W008 (default: pdf).",
    )
    p.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Glob pattern to skip. Repeatable.",
    )
    p.add_argument("--follow-symlinks", action="store_true")
    p.add_argument(
        "--allow-attachment-aliases",
        action="store_true",
        help="Allow one note to share an identifier with one attachment.",
    )
    p.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero on warnings as well as errors.",
    )
    p.add_argument("--no-color", action="store_true")
    p.add_argument("--quiet", action="store_true", help="Suppress the summary line.")
    p.add_argument(
        "--verbose",
        action="store_true",
        help="Log skipped files and progress to stderr.",
    )
    p.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"denote-lint {__version__}",
    )
    return p


def _split_codes(s: str) -> tuple[str, ...]:
    return tuple(c.strip() for c in s.split(",") if c.strip())


def _split_exts(s: str) -> frozenset[str]:
    return frozenset(e.strip().lower().lstrip(".") for e in s.split(",") if e.strip())


def config_from_args(args: argparse.Namespace) -> Config:
    return Config(
        paths=tuple(args.paths),
        output_format=args.format,
        min_severity=args.severity,
        checks=_split_codes(args.checks),
        disable=_split_codes(args.disable),
        note_extensions=_split_exts(args.extensions),
        image_extensions=_split_exts(args.image_extensions),
        image_tag=args.image_tag,
        attachment_extensions=_split_exts(args.attachment_extensions),
        exclude=tuple(args.exclude),
        follow_symlinks=args.follow_symlinks,
        strict=args.strict,
        no_color=args.no_color,
        quiet=args.quiet,
        verbose=args.verbose,
        allow_attachment_aliases=args.allow_attachment_aliases,
    )


def run(config: Config) -> int:
    for path in config.paths:
        if not path.exists():
            print(f"denote-lint: path does not exist: {path}", file=sys.stderr)
            return 2

    opts = CorpusOptions(
        note_extensions=config.note_extensions,
        image_extensions=config.image_extensions,
        image_tag=config.image_tag,
        attachment_extensions=config.attachment_extensions,
        exclude=config.exclude,
        follow_symlinks=config.follow_symlinks,
        allow_attachment_aliases=config.allow_attachment_aliases,
    )

    start = time.monotonic()
    notes = []
    scanned = 0
    for path, indexed_only in discover_files(list(config.paths), opts):
        if config.verbose:
            tag = "indexing" if indexed_only else "scanning"
            print(f"denote-lint: {tag} {path}", file=sys.stderr)
        notes.append(load_note(path, opts, indexed_only=indexed_only))
        if not indexed_only:
            scanned += 1

    corpus_roots = tuple(_resolve_root(p) for p in config.paths)
    ctx = build_context(notes, opts, corpus_roots=corpus_roots)
    enabled = config.enabled_codes()
    issues = run_checks(notes, ctx, enabled)
    elapsed = time.monotonic() - start

    report = Report(issues=issues, scanned=scanned, elapsed=elapsed)
    _emit(report, config)

    return _exit_code(report, strict=config.strict)


def _emit(report: Report, config: Config) -> None:
    if config.output_format == "compilation":
        body = format_compilation(report)
    elif config.output_format == "json":
        body = format_json(report, __version__)
    else:
        use_color = color_enabled(no_color_flag=config.no_color)
        body = format_text(report, use_color=use_color)

    if body:
        print(body)

    if not config.quiet:
        print(format_summary(report), file=sys.stderr)


def _resolve_root(path: Path) -> Path:
    """Resolve a CLI input path for in-corpus comparison.

    Files become their parent directory: ``denote-lint a/b/note.org`` is
    really asking us to scope checks to ``a/b/``. Symlinks are followed
    so that file-link existence checks can compare resolved targets
    against resolved roots without surprises.
    """
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path.absolute()
    if resolved.is_file():
        return resolved.parent
    return resolved


def _exit_code(report: Report, *, strict: bool) -> int:
    has_error = any(i.severity == "error" for i in report.issues)
    has_warning = any(i.severity == "warning" for i in report.issues)
    if has_error:
        return 1
    if strict and has_warning:
        return 1
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config = config_from_args(args)
    except (KeyError, ValueError) as e:
        print(f"denote-lint: invalid configuration: {e}", file=sys.stderr)
        return 2
    return run(config)
