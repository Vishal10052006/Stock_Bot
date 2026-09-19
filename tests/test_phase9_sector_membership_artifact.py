from datetime import date
from pathlib import Path

from market.data.context import load_sector_mappings_csv


MAPPING_PATH = Path(
    "data/reference/nse/sector_membership/sector_membership.csv"
)


def test_phase9_mapping_artifact_loads_and_is_nonempty():
    mappings = load_sector_mappings_csv(MAPPING_PATH)
    assert mappings


def test_phase9_welcorp_is_not_metal_after_august_31_review():
    mappings = load_sector_mappings_csv(MAPPING_PATH)
    provider = next(
        mapping
        for mapping in mappings
        if mapping.symbol == "WELCORP"
    )
    assert provider.sector_index_symbol == "NIFTY_METAL"
    assert provider.effective_from == date(2026, 3, 30)
    assert provider.effective_to == date(2026, 8, 30)


def test_phase9_research_dates_have_expected_known_memberships():
    mappings = load_sector_mappings_csv(MAPPING_PATH)

    def has(symbol: str, sector: str, as_of: date) -> bool:
        return any(
            m.symbol == symbol
            and m.sector_index_symbol == sector
            and m.effective_from <= as_of
            and (m.effective_to is None or as_of <= m.effective_to)
            for m in mappings
        )

    assert has("RELIANCE", "NIFTY_OIL_AND_GAS", date(2026, 6, 29))
    assert has("RELIANCE", "NIFTY_OIL_AND_GAS", date(2026, 9, 11))
    assert has("WELCORP", "NIFTY_METAL", date(2026, 8, 26))
    assert not has("WELCORP", "NIFTY_METAL", date(2026, 9, 11))


def test_phase9_known_bank_memberships_are_point_in_time_stable():
    mappings = load_sector_mappings_csv(MAPPING_PATH)

    for symbol in ("AXISBANK", "HDFCBANK", "ICICIBANK", "KOTAKBANK"):
        assert any(
            m.symbol == symbol
            and m.sector_index_symbol == "NIFTY_BANK"
            and m.effective_from == date(2026, 3, 30)
            and m.effective_to is None
            for m in mappings
        )
