import json
from pathlib import Path

from blockprobe.models import ProbeResult, ProbeStatus, RunSummary
from blockprobe.report.render import render_run, render_table, summarise

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "results_sample.json").read_text())


def test_empty_run_renders_without_crashing():
    empty = RunSummary(run_id="2026-10-20-1432", started_at="2026-10-20T14:32:00Z")
    screen = "\n".join(render_run(empty, colour=False))
    assert "0 probes" in screen
    assert render_table(empty, colour=False) == []


def test_unknown_status_is_treated_as_error():
    summary = RunSummary.model_validate(FIXTURE)
    # pydantic v2 does not validate on assignment by default, so this stores
    # the raw string and the renderer has to tolerate it.
    summary.probes[0].status = "NOT_A_STATUS"
    counts = summarise(summary)
    assert counts["error"] == 1


def test_narrow_terminal_uses_the_list_rendering():
    summary = RunSummary.model_validate(FIXTURE)
    screen = "\n".join(render_run(summary, colour=False, width=40))
    assert "Building block" not in screen
    assert "P01 contract" in screen


def test_home_path_in_a_failure_message_is_redacted_in_the_terminal():
    summary = RunSummary.model_validate(FIXTURE)
    summary.probes[0].status = "FAIL"
    summary.probes[0].message = r"could not read C:\Users\dan\AppData\run\P01.log"
    screen = "\n".join(render_run(summary, colour=False))
    assert "dan" not in screen
    assert "could not read" in screen


def test_probe_without_latency_renders_cleanly():
    summary = RunSummary.model_validate(FIXTURE)
    skipped = ProbeResult(probe_id="P05", label="stream", building_block="Streaming and cancel", status=ProbeStatus.SKIP)
    summary.probes.append(skipped)
    screen = "\n".join(render_run(summary, colour=False))
    assert "P05 stream" in screen
