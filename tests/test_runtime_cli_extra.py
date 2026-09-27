"""Additional regression coverage for the mode-aware runtime CLI."""

from __future__ import annotations

from trading.runtime_cli import RuntimeConfig, RuntimeMode, _config_from_args, build_parser, run_live, run_readiness


def test_runtime_config_rejects_non_positive_candles() -> None:
    try:
        RuntimeConfig(mode=RuntimeMode.SHADOW, candles=0)
    except ValueError:
        return
    raise AssertionError("candles=0 must be rejected")


def test_parser_exposes_all_modes() -> None:
    parser = build_parser()
    parsed = {parser.parse_args(["--mode", mode.value]).mode for mode in RuntimeMode}
    assert parsed == {mode.value for mode in RuntimeMode}


def test_config_normalizes_symbol() -> None:
    parser = build_parser()
    args = parser.parse_args(["--mode", "shadow", "--symbol", " reliance "])
    config = _config_from_args(args)
    assert config.mode is RuntimeMode.SHADOW
    assert config.symbol == "RELIANCE"


def test_live_requires_explicit_confirmation(capsys) -> None:
    parser = build_parser()
    config = _config_from_args(parser.parse_args(["--mode", "live"]))
    assert run_live(config) == 2
    assert "--confirm-live" in capsys.readouterr().out


def test_live_stays_locked_after_confirmation(capsys) -> None:
    parser = build_parser()
    config = _config_from_args(parser.parse_args(["--mode", "live", "--confirm-live"]))
    assert run_live(config) == 3
    output = capsys.readouterr().out
    assert "LIVE ORDER SUBMISSION: LOCKED" in output


def test_readiness_is_fail_closed(capsys) -> None:
    assert run_readiness() == 2
    output = capsys.readouterr().out
    assert "READY                : False" in output
    assert "Live broker execution: LOCKED" in output
    assert "historical_data_validated" in output
