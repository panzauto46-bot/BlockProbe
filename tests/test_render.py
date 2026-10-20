# tests/test_render.py
import json
from pathlib import Path

from blockprobe.models import RunSummary
from blockprobe.report.render import (
    render_counts, render_footer, render_probe_line, render_run,
    render_table, summarise,
)

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "results_sample.json").read_text())


def summary() -> RunSummary:
    return RunSummary.model_validate(FIXTURE)


def test_probe_line_shape():
    line = render_probe_line(summary().probes[0], colour=False)
    assert line.startswith("  ▸ P01 contract")
    assert "PASS" in line
    assert "0.4s" in line


def test_probe_line_shows_pass_rate_when_partial():
    flaky = [p for p in summary().probes if p.status == "FLAKY"][0]
    line = render_probe_line(flaky, colour=False)
    assert "2/3" in line


def test_counts_omit_zero_categories():
    text = render_counts(summary())
    assert "4 pass" in text
    assert "skip" not in text


def test_table_has_five_columns_and_one_row_per_probe():
    rows = render_table(summary(), colour=False)
    assert rows[0].split() == ["Building", "block", "Probe", "Result", "Pass", "p50"]
    assert len(rows) == 1 + len(summary().probes)


def test_footer_points_at_the_next_command():
    footer = render_footer(summary())
    assert footer[0].strip().startswith("run:")
    assert "blockprobe diff" in footer[1]


def test_render_run_contains_probe_lines_table_and_footer():
    screen = "\n".join(render_run(summary(), colour=False))
    assert "P01 contract" in screen
    assert "Building block" in screen
    assert "blockprobe diff" in screen


def test_summarise_counts():
    counts = summarise(summary())
    assert counts["pass"] == 4
    assert counts["flaky"] == 1
    assert counts["fail"] == 1
    assert counts["total"] == 6
