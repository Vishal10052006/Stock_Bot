"""Tests for the mode-aware STOCK_BOT runtime CLI."""

from __future__ import annotations

from trading.runtime_cli import RuntimeMode, _config_from_args, build_parser, run_live, run_readiness


def test_parser_exposes_distinct_runtime_modes() -> None:
    parser = build_parser()
    for mode in RuntimeMode:
        args = parser.parse_args(["--mode", mode.value])
        assert args.mode == mode.value


def test_config_normalizes_symbol() -> None:
    parser = build_parser()
    args = parser.parse_args(["--mode", "shadow", "--symbol", " reliance "])
    config = _config_from_args(args)
    assert config.mode is RuntimeMode.SHADOW
    assert config.symbol == "RELIANCE"


def test_live_mode_requires_explicit_confirmation(capsys) -> None:
    parser = build_parser()
    args = parser.parse_args(["--mode", "live"])
    config = _config_from_args(args)
    assert run_live(config) == 2
    assert "--confirm-live" in capsys.readouterr().out


def test_live_mode_remains_locked_after_confirmation(capsys) -> None:
    parser = build_parser()
    args = parser.parse_args(["--mode", "live", "--confirm-live"])
    config = _config_from_args(args)
    assert run_live(config) == 3
    output = capsys.readouterr().out
    assert "LIVE ORDER SUBMISSION: LOCKED" in output
    assert "live broker execution" in output


def test_readiness_mode_is_fail_closed(capsys) -> None:
    assert run_readiness() == 2
    output = capsys.readouterr().out
    assert "READY                : False" in output
    assert "Live broker execution: LOCKED" in output
    assert "historical_data_validated" in output


def test_live_paper_requires_verified_artifact_arguments() -> None:
    parser = build_parser()
    args = parser.parse_args(["--mode", "live-paper"])
    config = _config_from_args(args)

    assert config.mode is RuntimeMode.LIVE_PAPER
    assert config.model_artifact is None
    assert config.model_sha256 is None
    assert config.initial_equity == 100_000.0


def test_live_paper_config_carries_virtual_session_settings() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "--mode",
            "live-paper",
            "--symbol",
            " reliance ",
            "--benchmark-symbol",
            " nifty50 ",
            "--model-artifact",
            "model.pkl",
            "--model-sha256",
            "a" * 64,
            "--session-id",
            "TEST-SESSION",
            "--max-candles",
            "2",
        ]
    )
    config = _config_from_args(args)

    assert config.symbol == "RELIANCE"
    assert config.benchmark_symbol == "NIFTY50"
    assert config.model_artifact.name == "model.pkl"
    assert config.model_sha256 == "a" * 64
    assert config.session_id == "TEST-SESSION"
    assert config.max_candles == 2
