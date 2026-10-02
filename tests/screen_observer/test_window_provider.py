import subprocess

from screen_observer.contracts import WindowObservation
from screen_observer.detection import WindowDetector
from screen_observer.window_provider import LinuxWindowProvider


WMCTRL_OUTPUT = """0x001  0 10 20 1200 800 Navigator.Firefox host browser
0x002  0 30 40 1600 900 google-chrome.Google-chrome host TradingView — RELIANCE
0x003  0 0 0 100 0 bad.invalid host Broken
malformed line
"""


def test_linux_window_provider_parses_wmctrl_output(monkeypatch):
    monkeypatch.setattr(
        "screen_observer.window_provider.shutil.which",
        lambda command: "/usr/bin/wmctrl" if command == "wmctrl" else None,
    )

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout=WMCTRL_OUTPUT,
            stderr="",
        )

    monkeypatch.setattr("screen_observer.window_provider.subprocess.run", fake_run)

    windows = LinuxWindowProvider()()

    assert len(windows) == 2
    assert windows[0] == WindowObservation(
        title="browser",
        application="Firefox",
        left=10,
        top=20,
        width=1200,
        height=800,
    )
    assert windows[1].application == "Google-chrome"
    assert windows[1].title.startswith("TradingView")


def test_linux_window_provider_returns_empty_when_wmctrl_missing(monkeypatch):
    monkeypatch.setattr(
        "screen_observer.window_provider.shutil.which",
        lambda _command: None,
    )

    assert LinuxWindowProvider()() == ()


def test_linux_window_provider_returns_empty_on_command_failure(monkeypatch):
    monkeypatch.setattr(
        "screen_observer.window_provider.shutil.which",
        lambda _command: "/usr/bin/wmctrl",
    )

    def fake_run(*_args, **_kwargs):
        raise subprocess.CalledProcessError(1, "wmctrl")

    monkeypatch.setattr("screen_observer.window_provider.subprocess.run", fake_run)

    assert LinuxWindowProvider()() == ()


def test_window_detector_selects_tradingview_from_realistic_window_list():
    windows = LinuxWindowProvider._parse_output(WMCTRL_OUTPUT)

    selected = WindowDetector().select(windows)

    assert selected is not None
    assert "TradingView" in selected.title
