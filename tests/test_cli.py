"""CLI integration tests. The end-to-end fixture-based test lives in
test_e2e_corpus.py; here we exercise individual CLI behaviours.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from denote_lint import __version__
from denote_lint.cli import build_parser, config_from_args, main, run
from denote_lint.config import Config


def _write(p: Path, content: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


class TestArgParser:
    def test_paths_required(self) -> None:
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_defaults(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["foo"])
        cfg = config_from_args(args)
        assert cfg.output_format == "compilation"
        assert cfg.min_severity == "warning"
        assert cfg.strict is False
        assert cfg.allow_attachment_aliases is False
        assert "org" in cfg.note_extensions

    def test_checks_and_disable_split(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            ["x", "--checks", "E001, E002", "--disable", "W001"]
        )
        cfg = config_from_args(args)
        assert cfg.checks == ("E001", "E002")
        assert cfg.disable == ("W001",)

    def test_extensions_strip_dots(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["x", "--extensions", ".org, .md"])
        cfg = config_from_args(args)
        assert cfg.note_extensions == frozenset({"org", "md"})

    def test_attachment_extensions(self) -> None:
        parser = build_parser()
        assert config_from_args(parser.parse_args(["x"])).attachment_extensions == {
            "pdf"
        }
        args = parser.parse_args(["x", "--attachment-extensions", "pdf,.epub"])
        cfg = config_from_args(args)
        assert cfg.attachment_extensions == frozenset({"pdf", "epub"})


class TestRun:
    def test_clean_corpus_exits_zero(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        _write(
            tmp_path / "20240115T093000--note__t.org",
            "#+title: Note\n#+identifier: 20240115T093000\n#+filetags: :t:\n\nbody\n",
        )
        cfg = Config(paths=(tmp_path,))
        rc = run(cfg)
        assert rc == 0

    def test_error_exits_one(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        # Two files with the same identifier -> E001.
        _write(
            tmp_path / "20240115T093000--a.org",
            "#+title: A\n#+identifier: 20240115T093000\n",
        )
        _write(
            tmp_path / "20240115T093000--b.org",
            "#+title: B\n#+identifier: 20240115T093000\n",
        )
        cfg = Config(paths=(tmp_path,))
        rc = run(cfg)
        assert rc == 1
        out = capsys.readouterr()
        assert "E001" in out.out

    def test_link_to_pdf_attachment_resolves(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _write(
            tmp_path / "20240115T093000--note__t.org",
            "#+title: Note\n#+identifier: 20240115T093000\n#+filetags: :t:\n\n"
            "See [[denote:20240116T100000][the paper]].\n",
        )
        _write(tmp_path / "20240116T100000--paper.pdf", "%PDF-1.4")
        assert run(Config(paths=(tmp_path,))) == 0
        assert "W008" not in capsys.readouterr().out
        # Without PDFs indexed, the link is broken.
        cfg = Config(paths=(tmp_path,), attachment_extensions=frozenset())
        assert run(cfg) == 1
        assert "E004" in capsys.readouterr().out

    def test_strict_promotes_warning(self, tmp_path: Path) -> None:
        # Unsorted keywords -> W001 only. Without --strict, exit 0.
        _write(
            tmp_path / "20240115T093000--n__zeta_alpha.org",
            "#+title: N\n#+identifier: 20240115T093000\n#+filetags: :alpha:zeta:\n",
        )
        cfg_lax = Config(paths=(tmp_path,))
        assert run(cfg_lax) == 0
        cfg_strict = Config(paths=(tmp_path,), strict=True)
        assert run(cfg_strict) == 1

    def test_missing_path_exits_two(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        cfg = Config(paths=(tmp_path / "does-not-exist",))
        rc = run(cfg)
        assert rc == 2
        err = capsys.readouterr().err
        assert "does not exist" in err

    def test_json_output(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _write(
            tmp_path / "20240115T093000--n.org",
            "#+title: N\n#+identifier: 20240115T093000\n",
        )
        cfg = Config(paths=(tmp_path,), output_format="json")
        run(cfg)
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["version"] == __version__
        assert data["scanned"] == 1
        assert isinstance(data["issues"], list)

    def test_quiet_suppresses_summary(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _write(
            tmp_path / "20240115T093000--n.org",
            "#+title: N\n#+identifier: 20240115T093000\n",
        )
        cfg = Config(paths=(tmp_path,), quiet=True)
        run(cfg)
        err = capsys.readouterr().err
        assert "scanned" not in err

    def test_disable_silences_a_check(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Without disable, E007 (missing title) fires.
        _write(
            tmp_path / "20240115T093000--n.org",
            "#+identifier: 20240115T093000\n",
        )
        cfg_default = Config(paths=(tmp_path,))
        assert run(cfg_default) == 1
        capsys.readouterr()  # drain

        cfg_disabled = Config(paths=(tmp_path,), disable=("E007",))
        # E006 still fires? No, because we *do* have an identifier here.
        # Only E007 was firing; disabling it should leave a clean run.
        assert run(cfg_disabled) == 0


class TestMain:
    def test_main_returns_int(self, tmp_path: Path) -> None:
        _write(
            tmp_path / "20240115T093000--n.org",
            "#+title: N\n#+identifier: 20240115T093000\n",
        )
        rc = main([str(tmp_path)])
        assert rc == 0

    def test_main_version_flag(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as excinfo:
            main(["--version"])
        assert excinfo.value.code == 0
        out = capsys.readouterr().out
        assert __version__ in out
