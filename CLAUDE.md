# CLAUDE.md — Project context for denote-lint

## What this project is

denote-lint is a static analysis tool for Emacs Denote note collections. It walks a directory tree, parses Denote-format filenames and front matter, extracts cross-note links, and emits issues classified as error/warning/info. It runs 30 checks across 5 categories. Pure Python — no Emacs dependency.

## Architecture

```
cli.py              Argument parsing, orchestration, exit codes (0/1/2)
config.py           Config dataclass, severity ranking, code filtering
corpus.py           File discovery (.ignore, excludes, symlink loop guard), two-pass loading
models.py           Core data: ParsedFilename, FrontMatter, Link, Note, Issue, Context
parser/
  filename.py       Denote filename grammar parser
  frontmatter.py    Org / YAML / TOML / plain-text front-matter dispatch
  links.py          Denote link and file/markdown link extraction
checks/
  filename.py       W001, W007, E002, E003, E009, E010
  identifier.py     E001 (corpus-level: duplicate IDs)
  frontmatter.py    E005–E008, W002–W004
  links.py          E004, W005, W006
  hygiene.py        W008 (image keyword policy), I001–I004 (orphans, stubs, untagged)
reporter.py         Output formatters: compilation-mode, JSON, coloured text
sluggify.py         Canonical slugification mirroring Denote's own behaviour
```

**Two-pass pipeline** (cli.py):
1. Discover files (honouring `.ignore` and `--exclude`)
2. First pass: parse each file → `Note` (filename, front matter, links)
3. Corpus pass: build identifier index + reverse link graph; run corpus-level checks (E001, E004, I003)
4. Per-note pass: run remaining checks
5. Filter by severity/codes; emit via chosen reporter

## Key design decisions

- **Check registry pattern**: `@register_per_note(code, severity, category)` / `@register_corpus(...)` decorators. Each check is `(note, ctx) -> Iterable[Issue]`. Adding a check = write a function + one decorator; no wiring elsewhere.
- **Severity is metadata**: The registry holds severity/category for filtering only. Control flow and user-facing flags (`--checks`, `--disable`) use codes exclusively. This keeps codes stable across versions.
- **`.ignore` directories**: Files within are still indexed (so cross-tree denote links resolve), but checks skip them and emit no issues about them.
- **Two-pass design**: Parse-time issues (E002, E003, E008–E010) are raised during Note construction. Corpus-level issues (E001, E004, I003) need the full index and run separately.
- **Strict typing**: mypy in strict mode throughout. New code must pass mypy clean.
- **Defensive file reading**: BOM and CRLF normalised; non-UTF-8 caught gracefully. Code blocks (org `#+begin_src`, markdown fences) are masked before link extraction.

## Check codes

| Range | Category |
|-------|----------|
| E001–E010 | Errors: duplicate IDs, malformed identifiers, front-matter mismatches, broken links |
| W001–W008 | Warnings: filename inconsistencies, front-matter/link mismatches, image keyword policy |
| I001–I004 | Info: orphans, duplicate tags, stubs, untagged notes |

## Running

```bash
pip install -e '.[dev]'          # install with dev tools

denote-lint PATH                 # errors + warnings (default)
denote-lint --severity info PATH # include info checks
denote-lint --checks E001,E004 PATH
denote-lint --disable I003 PATH
denote-lint --format json PATH
denote-lint --strict PATH        # exit non-zero on warnings too
python -m denote_lint PATH       # direct module invocation
```

## Running tests

```bash
pytest                   # 279+ tests
ruff check src tests     # lint
mypy src tests           # type check (strict)
```

End-to-end regression test in `tests/test_e2e_corpus.py` runs denote-lint against `tests/fixtures/corpus-small/` and asserts the exact issue set (documented in `MANIFEST.org` inside the fixture).

## Adding a new check

1. Write a function in the appropriate `checks/*.py` file:
   - Per-note: `def check_foo(note: Note, ctx: Context) -> Iterable[Issue]`
   - Corpus: `def check_foo(ctx: Context) -> Iterable[Issue]`
2. Decorate with `@register_per_note("Xnnn", Severity.X, Category.Y)` or `@register_corpus(...)`
3. Add positive + negative test cases in `tests/`
4. If the new code can appear in `corpus-small`, update `MANIFEST.org`

## Dependencies

- **Runtime**: PyYAML only (for YAML front matter)
- **Dev**: pytest, ruff, mypy
- **Python**: 3.11+ (uses `tomllib`, `Self`, structural pattern matching)
