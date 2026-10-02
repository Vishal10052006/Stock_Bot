from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from multi_stock.correlation import build_correlation_matrix


TS = datetime(2026, 10, 2, 10, tzinfo=timezone.utc)


def test_m04_correlation_is_deterministic_and_causal():
    rows = []
    values = {
        "AAA": [1.0, 2.0, 3.0],
        "BBB": [2.0, 4.0, 6.0],
        "CCC": [3.0, 2.0, 1.0],
    }
    for i in range(3):
        stamp = TS - timedelta(minutes=10 * (2 - i))
        for symbol, series in values.items():
            rows.append({"timestamp": stamp, "symbol": symbol, "return_1": series[i]})
    rows.append({"timestamp": TS + timedelta(minutes=1), "symbol": "AAA", "return_1": 999.0})

    result = build_correlation_matrix(
        timestamp=TS,
        returns=pd.DataFrame(rows),
        universe_symbols=["CCC", "AAA", "BBB"],
    )
    assert result.symbols == ("AAA", "BBB", "CCC")
    assert result.matrix[0][1] == pytest.approx(1.0)
    assert result.matrix[0][2] == pytest.approx(-1.0)
    assert result.matrix[0][0] == 1.0
    assert result.observations == 3
    assert result.authority == "OBSERVATION_ONLY"


def test_m04_insufficient_overlap_is_not_inferred():
    frame = pd.DataFrame(
        [
            {"timestamp": TS, "symbol": "AAA", "return_1": 1.0},
            {"timestamp": TS, "symbol": "BBB", "return_1": 2.0},
        ]
    )
    result = build_correlation_matrix(
        timestamp=TS,
        returns=frame,
        universe_symbols=["AAA", "BBB"],
        min_observations=2,
    )
    assert result.matrix == ((None, None), (None, None))


def test_m04_duplicate_and_invalid_schema_fail_closed():
    frame = pd.DataFrame(
        [{"timestamp": TS, "symbol": "AAA", "return_1": 1.0}]
    )
    duplicate = pd.concat([frame, frame], ignore_index=True)
    with pytest.raises(ValueError, match="duplicate"):
        build_correlation_matrix(
            timestamp=TS,
            returns=duplicate,
            universe_symbols=["AAA"],
        )
    with pytest.raises(ValueError, match="missing columns"):
        build_correlation_matrix(
            timestamp=TS,
            returns=frame.drop(columns=["return_1"]),
            universe_symbols=["AAA"],
        )
