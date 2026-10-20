from blockprobe.models import ProbeResult, ProbeStatus
from blockprobe.redact import HOME_PLACEHOLDER, redact_model, redact_text, redact_value


def test_redacts_api_keys_and_tokens():
    text = "key=sk-abcdef0123456789 and ghp_0123456789abcdefghij"
    out = redact_text(text)
    assert "sk-abcdef0123456789" not in out
    assert "ghp_0123456789abcdefghij" not in out


def test_redacts_emails():
    out = redact_text("sent to someone@example.com today")
    assert "someone@example.com" not in out
    assert "@example.com" not in out


def test_redacts_windows_and_posix_home_paths():
    out = redact_text(r"C:\Users\dan\AppData\local\run.log and /home/dan/run.log")
    assert "dan" not in out
    assert HOME_PLACEHOLDER in out


def test_redact_value_walks_nested_structures():
    payload = {"a": ["x@y.com"], "b": {"c": "sk-1234567890"}}
    out = redact_value(payload)
    assert "x@y.com" not in str(out)
    assert "sk-1234567890" not in str(out)


def test_redact_model_copies_and_redacts():
    result = ProbeResult(
        probe_id="P01", label="contract", building_block="Public contract",
        status=ProbeStatus.FAIL, message="failed for someone@example.com",
    )
    out = redact_model(result)
    assert "someone@example.com" not in out.message
    assert result.message == "failed for someone@example.com"  # original untouched
