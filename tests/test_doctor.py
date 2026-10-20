from blockprobe.doctor import (
    CheckResult, EnvironmentInfo, capture_environment, doctor_exit_code,
    render_doctor,
)


def info(**overrides) -> EnvironmentInfo:
    checks = [
        CheckResult(name="os", value="windows 10.0.19045", ok=True),
        CheckResult(name="python", value="3.11.9", ok=True),
        CheckResult(name="openminion", value="0.1.4", ok=True),
        CheckResult(name="provider", value="portal/gemma-4", ok=True),
        CheckResult(name="budget", value="40 calls", ok=True),
        CheckResult(name="check-turn", value="ok", ok=True),
    ]
    base = dict(
        os_name="windows 10.0.19045", python_version="3.11.9",
        openminion_version="0.1.4", install_source="pip",
        provider="portal/gemma-4", model="gemma-4", budget_calls=40,
        check_turn="ok", timestamp="2026-10-20T14:32:00Z",
        checks=checks,
    )
    base.update(overrides)
    return EnvironmentInfo(**base)


def test_render_lists_each_check_and_a_verdict():
    lines = render_doctor(info(), colour=False)
    assert any("check-turn" in line for line in lines)
    assert lines[-1].startswith("6 checks passed")


def test_render_shows_next_step_for_a_failing_check():
    lines = render_doctor(info(checks=[
        CheckResult(name="check-turn", value="unreachable", ok=False,
                    next_step="openminion setup"),
    ]), colour=False)
    assert any(line.strip() == "next: openminion setup" for line in lines)


def test_exit_code_is_zero_when_all_checks_pass():
    assert doctor_exit_code(info()) == 0


def test_exit_code_is_four_when_provider_unavailable():
    assert doctor_exit_code(info(checks=[CheckResult(name="check-turn", value="unreachable", ok=False)])) == 4


def test_no_secret_appears_in_the_output():
    text = "\n".join(render_doctor(info(provider="portal/gemma-4"), colour=False))
    assert "sk-" not in text


def test_capture_builds_checks_from_the_environment(monkeypatch):
    monkeypatch.setenv("BLOCKPROBE_PROVIDER", "cortensor")
    monkeypatch.setenv("BLOCKPROBE_MODEL", "gpt-oss-20b")
    monkeypatch.setenv("BLOCKPROBE_BUDGET", "40")
    captured = capture_environment()
    assert [check.name for check in captured.checks] == [
        "os", "python", "openminion", "provider", "budget", "check-turn",
    ]
    assert captured.checks[3].value == "cortensor/gpt-oss-20b"
    assert captured.budget_calls == 40


def test_capture_redacts_provider_values(monkeypatch):
    monkeypatch.setenv("BLOCKPROBE_PROVIDER", "contact someone@example.com")
    captured = capture_environment()
    assert "someone@example.com" not in captured.checks[3].value
