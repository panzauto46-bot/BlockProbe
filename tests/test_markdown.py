import json
from pathlib import Path

from blockprobe.models import RunSummary
from blockprobe.report.markdown import (
    REPORT_FILENAME, render_building_blocks_md, write_building_blocks_md,
)

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "results_sample.json").read_text())


def test_markdown_has_the_six_prd_columns():
    text = render_building_blocks_md(RunSummary.model_validate(FIXTURE))
    header = [line for line in text.splitlines() if line.startswith("|")][0]
    for column in ["Building block", "Probe", "Result", "Pass rate", "p50 latency", "Evidence / note"]:
        assert column in header


def test_markdown_has_one_row_per_probe():
    text = render_building_blocks_md(RunSummary.model_validate(FIXTURE))
    rows = [
        line for line in text.splitlines()
        if line.startswith("|")
        and not line.startswith("| Building block")
        and not line.startswith("| ---")
    ]
    assert len(rows) == 6


def test_write_does_not_overwrite_without_force(tmp_path):
    summary = RunSummary.model_validate(FIXTURE)
    first = write_building_blocks_md(summary, tmp_path)
    first.write_text("hand edited")
    again = write_building_blocks_md(summary, tmp_path)
    assert again.read_text() == "hand edited"


def test_write_force_overwrites(tmp_path):
    summary = RunSummary.model_validate(FIXTURE)
    path = write_building_blocks_md(summary, tmp_path)
    path.write_text("hand edited")
    write_building_blocks_md(summary, tmp_path, force=True)
    assert "hand edited" not in path.read_text()


def test_written_file_is_redacted(tmp_path):
    summary = RunSummary.model_validate(FIXTURE)
    summary.probes[0].evidence = [r"C:\Users\dan\AppData\run\P01.log"]
    path = write_building_blocks_md(summary, tmp_path)
    assert "dan" not in path.read_text()
