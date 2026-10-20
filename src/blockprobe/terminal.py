"""Terminal primitives: colour decisions, ANSI styling, glyphs, width.

The render layer (task 5) needs a handful of facts about the terminal it
is writing to, and needs them decided in one place: whether colour may be
used, how wide the output is, and which glyph set to draw with (Unicode
glyphs with a documented ASCII fallback for terminals that cannot print
them).

Colour is opt-in, not opt-out: :func:`style` is unconditional and writes
raw ANSI escapes, so callers ask :func:`colour_enabled` first and only
then wrap text. That keeps the decision (environment, TTY, flags) apart
from the bytes, and makes it impossible for a piped report to gain escape
sequences just because a caller forgot the check.

No third-party dependency: the escapes are raw ANSI, and the glyph tables
are plain dictionaries.
"""

import os
import shutil
from collections.abc import Mapping

#: Glyph set for terminals that cannot be trusted with box-drawing or
#: arrow characters (legacy consoles, redirected output, CI logs).
GLYPHS_ASCII = {"probe": ">", "arrow": "->", "dot": "-", "rule": "-"}

#: Glyph set for terminals that can print the real characters.
GLYPHS_UNICODE = {"probe": "▸", "arrow": "→", "dot": "·", "rule": "─"}


class Glyphs:
    """One glyph set, selected by *ascii_mode*."""

    def __init__(self, ascii_mode: bool = False) -> None:
        table = GLYPHS_ASCII if ascii_mode else GLYPHS_UNICODE
        self.probe = table["probe"]
        self.arrow = table["arrow"]
        self.dot = table["dot"]
        self.rule = table["rule"]


#: The default glyph set: Unicode, with ``Glyphs(ascii_mode=True)`` as the
#: documented fallback.
GLYPHS = Glyphs()


def is_tty(stream: object) -> bool:
    """Return True when *stream* reports itself as a terminal.

    The ``isatty`` method is looked up with ``getattr``, so a stream that
    does not have one (a simple writer object, a pasted-in double) is
    simply not a TTY rather than an error.
    """
    isatty = getattr(stream, "isatty", None)
    if isatty is None:
        return False
    return bool(isatty())


def colour_enabled(
    stream: object,
    force_off: bool = False,
    env: Mapping[str, str] | None = None,
) -> bool:
    """Return whether ANSI colour may be written to *stream*.

    The decision order is fixed: ``force_off`` wins, then the
    ``NO_COLOR`` environment variable (set to any non-empty value, per
    no-color.org), then the TTY check. *env* defaults to ``os.environ``.
    """
    if force_off:
        return False
    if env is None:
        env = os.environ
    if env.get("NO_COLOR"):
        return False
    return is_tty(stream)


def terminal_width(default: int = 80) -> int:
    """Return the terminal width in columns, floored at 40.

    *default* is the fallback used only when neither the ``COLUMNS``
    environment variable nor the OS reports a size; the floor then keeps a
    misreported width from squeezing the report below 40 columns.
    """
    columns = shutil.get_terminal_size(fallback=(default, 24)).columns
    return max(columns, 40)


def style(text: str, *codes: str) -> str:
    """Wrap *text* in the ANSI *codes*, joined with ``;``.

    Unconditional: callers check :func:`colour_enabled` first. With no
    codes the text is returned unchanged, so ``style(text)`` is a no-op
    that keeps call sites uniform.
    """
    if not codes:
        return text
    return f"\x1b[{';'.join(codes)}m{text}\x1b[0m"


def dim(text: str) -> str:
    """Return *text* wrapped in the dim code."""
    return style(text, "2")


def bold(text: str) -> str:
    """Return *text* wrapped in the bold code."""
    return style(text, "1")


def green(text: str) -> str:
    """Return *text* wrapped in the green code."""
    return style(text, "32")


def yellow(text: str) -> str:
    """Return *text* wrapped in the yellow code."""
    return style(text, "33")


def red(text: str) -> str:
    """Return *text* wrapped in the red code."""
    return style(text, "31")


#: Probe status to ANSI code. The vocabulary is the exact uppercase set;
#: comparison is raw, and an unknown status is coloured as a failure.
_STATUS_COLOURS = {
    "PASS": "32",
    "FLAKY": "33",
    "FAIL": "31",
    "SKIP": "90",
    "ERROR": "90",
}


def status_colour(status: str) -> str:
    """Return the ANSI code for a probe *status*; unknown gets failure red."""
    return _STATUS_COLOURS.get(status, "31")


#: Finding severity to ANSI code. The vocabulary is the exact lowercase
#: set; comparison is raw, and an unknown severity is coloured as high.
_SEVERITY_COLOURS = {"high": "31", "medium": "33", "low": "90"}


def severity_colour(severity: str) -> str:
    """Return the ANSI code for a finding *severity*; unknown gets high red."""
    return _SEVERITY_COLOURS.get(severity, "31")
