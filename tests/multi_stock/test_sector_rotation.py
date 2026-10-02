from datetime import datetime, timezone

import pandas as pd
import pytest

from multi_stock.sector_rotation import build_sector_rotation


TS = datetime(2026, 10, 2, 10, tzinfo=timezone.utc)


def test_m02_sector_rotation_uses_latest_causal_row_per_sector():
    frame = pd.DataFrame(
        [
            {
                "timestamp": datetime(2026, 10, 2, 9, tzinfo=timezone.utc),
                "sector_index_symbol": "NIFTY IT",
                "return_1": 0.01,
                "return_3": 0.02,
                "return_12": 0.05,
            },
            {
                "timestamp": datetime(2026, 10, 2, 10, tzinfo=timezone.utc),
                "sector_index_symbol": "NIFTY IT",
                "return_1": 0.03,
                "return_3": 0.04,
                "return_12": 0.07,
            },
            {
                "timestamp": datetime(2026, 10, 2, 11, tzinfo=timezone.utc),
                "sector_index_symbol": "NIFTY IT",
                "return_1": 0.99,
                "return_3": 0.99,
                "return_12": 0.99,
            },
            {
                "timestamp": datetime(2026, 10, 2, 10, tzinfo=timezone.utc),
                "sector_index_symbol": "NIFTY BANK",
                "return_1": -0.01,
                "return_3": 0.01,
                "return_12": 0.03,
            },
        ]
    )

    result = build_sector_rotation(timestamp=TS, sector_context=frame)

    assert [row.sector_index_symbol for row in result.rows] == [
        "NIFTY BANK",
        "NIFTY IT",
    ]
    assert result.rows[1].return_1 == pytest.approx(0.03)
    assert result.rows[0].return_1 == pytest.approx(-0.01)
    assert result.authority == "OBSERVATION_ONLY"


def test_m02_future_only_context_is_empty():
    result = build_sector_rotation(
        timestamp=TS,
        sector_context=[
            {
                "timestamp": datetime(2026, 10, 2, 11, tzinfo=timezone.utc),
                "sector_index_symbol": "NIFTY IT",
                "return_1": 0.03,
                "return_3": 0.04,
                "return_12": 0.07,
            }
        ],
    )
    assert result.rows == ()


def test_m02_requires_complete_derived_sector_schema():
    with pytest.raises(ValueError, match="sector_context missing columns"):
        build_sector_rotation(
            timestamp=TS,
            sector_context=[
                {
                    "timestamp": TS,
                    "sector_index_symbol": "NIFTY IT",
                    "return_1": 0.03,
                }
            ],
        )
