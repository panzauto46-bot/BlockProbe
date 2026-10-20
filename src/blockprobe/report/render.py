"""The terminal rendering of a probe run.

A run is shown twice. While it is happening, each probe gets one line as it
finishes, so the latency and the status are visible at the moment they are
measured. Once it is over, the same results appear as a five-column table -
the six PRD columns minus Evidence/note, which does not fit at 80 columns -
followed by the run id and the next command to type.

Every function returns plain text; colour is an opt-in layer applied only
when *colour* is true, so the whole module is testable without a terminal.
The status counts live in :func:`summarise` and nowhere else; the counts line
reads that dictionary rather than recounting the statuses.
"""

from blockprobe.models import ProbeResult, RunSummary
from blockprobe.redact import redact_text
from blockprobe.terminal import GLYPHS, status_colour, style, terminal_width

#: The status vocabulary, in the order the counts line reads.
STATUS_ORDER = ["PASS", "FLAKY", "FAIL", "SKIP", "ERROR"]

#: Statuses whose cause is worth printing next to the line.
_FAILURE_STATUSES = frozenset({"FLAKY", "FAIL", "ERROR"})

#: A failure message longer than this is cut; the terminal is not a log file.
_MESSAGE_LIMIT = 40

#: A rule is fixed-width structure, not content (UX design D10).
_RULE_WIDTH = 60

#: Below this width the table does not fit and the list layout is used.
_TABLE_MIN_WIDTH = 60


def _display_status(status: str) -> str:
    """Return a status the renderer can show.

    A value outside the vocabulary is shown as ``ERROR``: a newer probe set
    must not make the renderer raise, and an arbitrary token would break the
    fixed status column.
    """
    return status if status in STATUS_ORDER else "ERROR"


def summarise(summary: RunSummary) -> dict:
    """Return the machine-readable counts for *summary*.

    The five status keys are lowercase; ``total``, ``duration_s`` and
    ``total_calls`` carry the run totals. A status outside the vocabulary is
    counted as ``error``: a newer probe set must not make the renderer raise
    or silently lose a result.
    """
    counts = {name.lower(): 0 for name in STATUS_ORDER}
    for probe in summary.probes:
        status = str(probe.status)
        key = status.lower() if status in STATUS_ORDER else "error"
        counts[key] += 1
    counts["total"] = len(summary.probes)
    counts["duration_s"] = summary.duration_s
    counts["total_calls"] = summary.total_calls
    return counts


def render_probe_line(probe: ProbeResult, colour: bool = True) -> str:
    """Return the live one-line result for *probe*, without a newline.

    The label, status and latency are in fixed columns so consecutive probe
    lines line up. A partial pass rate appears only when it is informative,
    and a failure message - redacted and cut to 40 characters - appears for
    the statuses whose cause matters.
    """
    status = _display_status(str(probe.status))
    status_cell = f"{status:<7}"
    if colour:
        status_cell = style(status_cell, status_colour(status))

    line = f"  {GLYPHS.probe} {probe.probe_id} {probe.label:<16}{status_cell}"
    latency = _latency_text(probe.latency_p50_s)
    if latency:
        line += f"{latency:>6}"
    if probe.passed != probe.repeats:
        line += f"   {probe.passed}/{probe.repeats}"
    line += _message_suffix(probe, status)
    return line


def render_probe_list(probe: ProbeResult, colour: bool = True) -> str:
    """Return the narrow-terminal variant of :func:`render_probe_line`.

    One space between fields and no padding, so the line costs only as much
    width as its content needs.
    """
    status = _display_status(str(probe.status))
    status_text = style(status, status_colour(status)) if colour else status
    fields = [f"  {GLYPHS.probe} {probe.probe_id}", probe.label, status_text]
    latency = _latency_text(probe.latency_p50_s)
    if latency:
        fields.append(latency)
    if probe.passed != probe.repeats:
        fields.append(f"{probe.passed}/{probe.repeats}")
    message = _message_text(probe, status)
    if message:
        fields.append(message)
    return " ".join(fields)


def render_counts(summary: RunSummary) -> str:
    """Return the status counts, omitting categories with no probes."""
    counts = summarise(summary)
    parts = [
        f"{counts[name.lower()]} {name.lower()}"
        for name in STATUS_ORDER
        if counts[name.lower()]
    ]
    return f" {GLYPHS.dot} ".join(parts)


def render_footer(summary: RunSummary) -> list[str]:
    """Return the run id and the next command to type."""
    return [
        f"  run:  runs/{summary.run_id}",
        "  next: blockprobe diff runs/<a> runs/<b>",
    ]


def render_table(summary: RunSummary, colour: bool = True) -> list[str]:
    """Return the five-column results table, or ``[]`` when there are no probes."""
    if not summary.probes:
        return []

    header = "  " + "  ".join(
        [
            f"{'Building block':<20}",
            f"{'Probe':<5}",
            f"{'Result':<6}",
            f"{'Pass':<4}",
            f"{'p50':>5}",
        ]
    )
    rows = [header]
    for probe in summary.probes:
        status = _display_status(str(probe.status))
        status_cell = f"{status:<6}"
        if colour:
            status_cell = style(status_cell, status_colour(status))
        latency = _latency_text(probe.latency_p50_s) or "n/a"
        pass_cell = f"{probe.passed}/{probe.repeats}"
        rows.append(
            "  "
            + "  ".join(
                [
                    f"{probe.building_block:<20}",
                    f"{probe.probe_id:<5}",
                    status_cell,
                    f"{pass_cell:<4}",
                    f"{latency:>5}",
                ]
            )
        )
    return rows


def render_run(
    summary: RunSummary,
    colour: bool = True,
    width: int | None = None,
) -> list[str]:
    """Return the full screen for *summary*.

    At 60 columns or more the table fits after the live lines; below that the
    compact list layout is used and the table is dropped rather than allowed
    to wrap into misaligned columns. *width* defaults to the terminal width.
    """
    effective_width = terminal_width() if width is None else width
    lines: list[str] = []

    if effective_width >= _TABLE_MIN_WIDTH:
        lines.extend(render_probe_line(probe, colour) for probe in summary.probes)
    else:
        lines.extend(render_probe_list(probe, colour) for probe in summary.probes)

    rule = GLYPHS.rule * _RULE_WIDTH
    lines.append(style(rule, "2") if colour else rule)
    lines.append(f"  {_summary_text(summary)}")

    if effective_width >= _TABLE_MIN_WIDTH:
        table = render_table(summary, colour)
        if table:
            lines.append("")
            lines.extend(table)

    lines.append("")
    lines.extend(render_footer(summary))
    return lines


def _summary_text(summary: RunSummary) -> str:
    """Return the counts line: status counts, duration and call count."""
    counts_line = render_counts(summary) if summary.probes else "0 probes"
    parts = [
        counts_line,
        f"{summary.duration_s:.1f}s",
        f"{summary.total_calls} calls",
    ]
    return f" {GLYPHS.dot} ".join(part for part in parts if part)


def _latency_text(seconds: float | None) -> str:
    """Return a latency as ``0.4s``, or an empty string when it was not measured."""
    if seconds is None:
        return ""
    return f"{seconds:.1f}s"


def _message_text(probe: ProbeResult, status: str) -> str:
    """Return the redacted, truncated cause for a failure, or an empty string."""
    if status not in _FAILURE_STATUSES or not probe.message:
        return ""
    collapsed = " ".join(redact_text(probe.message).split())
    return collapsed[:_MESSAGE_LIMIT]


def _message_suffix(probe: ProbeResult, status: str) -> str:
    """Return the cause prefixed for the wide line, or an empty string."""
    message = _message_text(probe, status)
    return f"  {message}" if message else ""
