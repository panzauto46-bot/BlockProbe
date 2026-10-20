"""Data model for probe results, run summaries and analyst findings.

These three models are the contract between the probe runner, the renderer
and the CLI. Field names and defaults are stable API: later layers read and
write them directly.
"""

from enum import Enum

from pydantic import BaseModel, Field


class ProbeStatus(str, Enum):
    """Outcome of a single probe."""

    PASS = "PASS"
    FLAKY = "FLAKY"
    FAIL = "FAIL"
    SKIP = "SKIP"
    ERROR = "ERROR"

    # Python 3.11+ made Enum.__format__ follow Enum.__str__, and a plain str
    # mixin does not override Enum.__str__, so f"{ProbeStatus.PASS}" would
    # render "ProbeStatus.PASS" instead of "PASS". Restore str's own
    # behaviour so status renders (and pads) as its value.
    __str__ = str.__str__


class ProbeResult(BaseModel):
    """The outcome of probing one building block."""

    probe_id: str
    label: str
    building_block: str
    status: ProbeStatus
    repeats: int = 1
    passed: int = 0
    latency_p50_s: float | None = None
    latency_p95_s: float | None = None
    doc_ref: str | None = None
    evidence: list[str] = Field(default_factory=list)
    message: str | None = None


class RunSummary(BaseModel):
    """Everything one probe run produced, including its environment."""

    run_id: str
    started_at: str
    openminion_version: str = "unknown"
    python_version: str = "unknown"
    os_name: str = "unknown"
    provider: str = "unknown"
    model: str = "unknown"
    probes: list[ProbeResult] = Field(default_factory=list)
    total_calls: int = 0
    duration_s: float = 0.0


class Finding(BaseModel):
    """An analyst observation about one probe result."""

    title: str
    probe_id: str
    building_block: str
    severity: str
    summary: str
    evidence_refs: list[str] = Field(default_factory=list)
    suggested_improvement: str = ""
