import pytest
from pydantic import ValidationError

from blockprobe.models import ProbeResult, ProbeStatus, RunSummary


def test_probe_status_members_are_uppercase_names():
    assert ProbeStatus.PASS == "PASS"
    assert ProbeStatus.FLAKY == "FLAKY"
    assert ProbeStatus.FAIL == "FAIL"
    assert ProbeStatus.SKIP == "SKIP"
    assert ProbeStatus.ERROR == "ERROR"


def test_probe_result_defaults():
    result = ProbeResult(probe_id="P01", label="contract", building_block="Public contract", status=ProbeStatus.PASS)
    assert result.repeats == 1
    assert result.passed == 0
    assert result.latency_p50_s is None
    assert result.evidence == []


def test_run_summary_defaults_to_empty_probes():
    summary = RunSummary(run_id="2026-10-20-1432", started_at="2026-10-20T14:32:00Z")
    assert summary.probes == []
    assert summary.total_calls == 0


def test_missing_required_field_raises():
    with pytest.raises(ValidationError):
        ProbeResult(probe_id="P01")


def test_status_formats_as_its_value():
    assert str(ProbeStatus.PASS) == "PASS"
    assert f"{ProbeStatus.PASS:<7}" == "PASS   "
    assert ProbeStatus.PASS == "PASS"
