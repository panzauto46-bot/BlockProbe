# tests/test_terminal.py
import io
import os
import shutil

from blockprobe.terminal import (
    Glyphs, colour_enabled, status_colour, style, terminal_width,
)


class _TtyStream:
    """A stream that reports itself as a TTY, for the gating tests."""

    def __init__(self, tty: bool = True):
        self._tty = tty

    def isatty(self) -> bool:
        return self._tty


def test_colour_disabled_for_non_tty():
    assert colour_enabled(io.StringIO()) is False


def test_colour_enabled_for_tty_without_no_color():
    assert colour_enabled(_TtyStream(), env={}) is True


def test_colour_disabled_by_no_color_env():
    assert colour_enabled(_TtyStream(), env={"NO_COLOR": "1"}) is False


def test_colour_disabled_by_force_off():
    assert colour_enabled(_TtyStream(), force_off=True, env={}) is False


def test_style_wraps_with_ansi():
    assert style("PASS", "32") == "\x1b[32mPASS\x1b[0m"


def test_style_with_no_codes_is_unchanged():
    assert style("PASS") == "PASS"


def test_status_colour_mapping():
    assert status_colour("PASS") == "32"
    assert status_colour("FLAKY") == "33"
    assert status_colour("FAIL") == "31"
    assert status_colour("SKIP") == "90"
    assert status_colour("ERROR") == "90"


def test_unknown_status_is_treated_as_failure_colour():
    assert status_colour("WEIRD") == "31"


def test_ascii_glyphs_fallback():
    ascii_glyphs = Glyphs(ascii_mode=True)
    assert ascii_glyphs.rule == "-"
    assert ascii_glyphs.arrow == "->"


def test_terminal_width_has_a_floor(monkeypatch):
    monkeypatch.setattr(
        shutil, "get_terminal_size", lambda fallback=None: os.terminal_size((20, 24))
    )
    assert terminal_width() == 40
