"""The Markdown report: the building-blocks-tested.md deliverable.

The terminal renderer is for the operator watching a run; this file is the
graded artefact that gets attached to a bug report. It carries all six PRD
columns (the terminal drops Evidence / note) and a metadata block naming the
environment the run was taken on, so a saved report still makes sense weeks
later.

The layout lives in a template file so the artefact's shape can be edited
without touching code; ``str.format`` fills the metadata block and the table
rows generated here. The writer is the redaction boundary: nothing reaches
disk unredacted.
"""

from pathlib import Path
from typing import cast

from blockprobe.models import ProbeResult, RunSummary
from blockprobe.redact import redact_model

REPORT_FILENAME = "building-blocks-tested.md"

_TEMPLATE_PATH = Path(__file__).parent / "templates" / REPORT_FILENAME


def render_building_blocks_md(summary: RunSummary) -> str:
    """Return building-blocks-tested.md for *summary*, ending with a newline."""
    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    return template.format(
        openminion_version=summary.openminion_version,
        python_version=summary.python_version,
        os_name=summary.os_name,
        provider=summary.provider,
        model=summary.model,
        run_id=summary.run_id,
        started_at=summary.started_at,
        rows="\n".join(_table_row(probe) for probe in summary.probes),
    )


def write_building_blocks_md(summary: RunSummary, out_dir: Path, force: bool = False) -> Path:
    """Write the report into *out_dir* and return its path.

    The summary is redacted before it is rendered, so the file on disk is
    safe to attach to a public issue. A note the operator edited by hand is
    never overwritten unless *force* is true.
    """
    out_dir = Path(out_dir)
    path = out_dir / REPORT_FILENAME
    if path.exists() and not force:
        return path
    redacted = cast(RunSummary, redact_model(summary))
    path.write_text(render_building_blocks_md(redacted), encoding="utf-8")
    return path


def _table_row(probe: ProbeResult) -> str:
    """Return one six-column Markdown row for *probe*."""
    note_parts = list(probe.evidence)
    if probe.message:
        note_parts.append(probe.message)
    latency = f"{probe.latency_p50_s:.1f}s" if probe.latency_p50_s is not None else "n/a"
    return "| {block} | {probe_id} | {status} | {passed}/{repeats} | {latency} | {note} |".format(
        block=probe.building_block,
        probe_id=probe.probe_id,
        status=str(probe.status),
        passed=probe.passed,
        repeats=probe.repeats,
        latency=latency,
        note=", ".join(note_parts),
    )
