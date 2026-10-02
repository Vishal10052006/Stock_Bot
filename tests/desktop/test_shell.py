from __future__ import annotations

import pytest

from desktop import DesktopShell, DesktopView


def test_shell_starts_with_first_view_active() -> None:
    shell = DesktopShell(
        (
            DesktopView("market", "Market", order=1),
            DesktopView("home", "Home", order=0),
        )
    )

    assert shell.active_view is not None
    assert shell.active_view.view_id == "market"
    assert [view.view_id for view in shell.views] == ["home", "market"]


def test_activate_changes_only_desktop_navigation_state() -> None:
    shell = DesktopShell((DesktopView("home", "Home"), DesktopView("risk", "Risk")))

    active = shell.activate("risk")

    assert active.view_id == "risk"
    assert shell.snapshot()["active_view"] == "risk"
    assert shell.snapshot()["authority"] == "OBSERVATION_ONLY"


def test_duplicate_and_unknown_views_fail_closed() -> None:
    shell = DesktopShell((DesktopView("home", "Home"),))

    with pytest.raises(ValueError, match="already registered"):
        shell.register_view(DesktopView("home", "Home"))

    with pytest.raises(KeyError, match="unknown desktop view"):
        shell.activate("missing")


@pytest.mark.parametrize(
    ("view_id", "title", "order", "message"),
    [
        ("", "Home", 0, "view_id must be non-empty"),
        ("home", "", 0, "title must be non-empty"),
        ("home", "Home", -1, "order must be non-negative"),
    ],
)
def test_view_metadata_is_validated(
    view_id: str, title: str, order: int, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        DesktopView(view_id, title, order=order)


def test_shell_snapshot_is_deterministic() -> None:
    shell = DesktopShell(
        (
            DesktopView("prediction", "Prediction", order=2),
            DesktopView("home", "Home", order=0),
            DesktopView("market", "Market", order=1),
        )
    )

    first = shell.snapshot()
    second = shell.snapshot()

    assert first == second
    assert [item["view_id"] for item in first["views"]] == [
        "home",
        "market",
        "prediction",
    ]
