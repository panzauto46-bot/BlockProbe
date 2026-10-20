"""Environment capture and rendering for the doctor command.

doctor is the gate that stops a run from failing later for an obvious
reason: a missing SDK, an unset provider, or no call budget. It reports one
row per check, states the cause and the fixing command for a blocked row
(the convention ``openminion status readiness`` uses), and exits non-zero
unless every check is green.

Provider and budget come from BlockProbe's own ``BLOCKPROBE_*`` names, not
``OPENMINION_*``: openminion 0.1.8 has no provider/model/budget variables,
and provider credentials live in the provider config, never in environment
capture. Every captured value passes through :func:`redact_text` before it
is stored.
"""

import os
import platform
from collections.abc import Callable
from datetime import datetime, timezone
from importlib import metadata as importlib_metadata

from pydantic import BaseModel, Field

from blockprobe.redact import redact_text
from blockprobe.terminal import GLYPHS, dim, green, red

PROVIDER_ENV = "BLOCKPROBE_PROVIDER"
MODEL_ENV = "BLOCKPROBE_MODEL"
BUDGET_ENV = "BLOCKPROBE_BUDGET"

_OPENMINION_NEXT_STEP = "pip install openminion>=0.1.4,<0.2"


class CheckResult(BaseModel):
    """One environment check: a name, the observed value, and whether it is ok."""

    name: str
    value: str
    ok: bool
    detail: str = ""
    next_step: str = ""


class EnvironmentInfo(BaseModel):
    """Everything doctor captured about the machine and the configured provider."""

    os_name: str
    python_version: str
    openminion_version: str
    install_source: str
    provider: str
    model: str
    budget_calls: int | None
    check_turn: str
    timestamp: str
    checks: list[CheckResult] = Field(default_factory=list)


def capture_environment(probe_turn: Callable[[], str] | None = None) -> EnvironmentInfo:
    """Gather the environment facts and the six doctor checks.

    *probe_turn*, when supplied, is called to execute one real turn (the CLI
    passes a runner for ``openminion doctor --check-turn --json``); any
    failure it reports or raises becomes a blocked check-turn row, never an
    exception out of doctor.
    """
    openminion_version, install_source = _openminion_install()
    provider = redact_text(os.environ.get(PROVIDER_ENV, "")).strip()
    model = redact_text(os.environ.get(MODEL_ENV, "")).strip()
    budget_calls = _budget()
    check_turn = "not run"
    if probe_turn is not None:
        try:
            check_turn = redact_text(probe_turn()).strip()
        except Exception:
            check_turn = "unreachable"

    os_value = redact_text(platform.platform())
    python_value = redact_text(platform.python_version())
    checks = [
        CheckResult(name="os", value=os_value, ok=True),
        CheckResult(name="python", value=python_value, ok=True),
        CheckResult(
            name="openminion",
            value=openminion_version,
            ok=openminion_version != "unknown",
            next_step="" if openminion_version != "unknown" else _OPENMINION_NEXT_STEP,
        ),
        _provider_check(provider, model),
        _budget_check(budget_calls),
        CheckResult(
            name="check-turn",
            value=check_turn,
            ok=check_turn == "ok",
            next_step="" if check_turn == "ok" else "openminion setup",
        ),
    ]
    return EnvironmentInfo(
        os_name=os_value,
        python_version=python_value,
        openminion_version=openminion_version,
        install_source=install_source,
        provider=provider or "unknown",
        model=model or "unknown",
        budget_calls=budget_calls,
        check_turn=check_turn,
        timestamp=datetime.now(timezone.utc).isoformat(),
        checks=checks,
    )


def render_doctor(info: EnvironmentInfo, colour: bool = True) -> list[str]:
    """Return one row per check, a blank line, and the closing verdict."""
    lines = []
    for check in info.checks:
        value = check.value
        if colour:
            value = green(value) if check.ok else red(value)
        lines.append(f"{check.name:<20}{value}")
        if not check.ok and check.next_step:
            hint = f"    next: {check.next_step}"
            lines.append(dim(hint) if colour else hint)
    lines.append("")
    lines.append(_verdict(info))
    return lines


def doctor_exit_code(info: EnvironmentInfo) -> int:
    """Return 0 when every check is ok, 4 when the environment is unavailable."""
    return 0 if all(check.ok for check in info.checks) else 4


def _verdict(info: EnvironmentInfo) -> str:
    passed = sum(1 for check in info.checks if check.ok)
    provider_checks = [check for check in info.checks if check.name == "provider"]
    if provider_checks:
        provider_state = "reachable" if provider_checks[0].ok else "unreachable"
    else:
        provider_state = "unknown"
    budget_state = "budget set" if info.budget_calls is not None else "budget not set"
    return (
        f"{passed} checks passed"
        f" {GLYPHS.dot} provider {provider_state}"
        f" {GLYPHS.dot} {budget_state}"
    )


def _provider_check(provider: str, model: str) -> CheckResult:
    if not provider:
        return CheckResult(
            name="provider", value="not set", ok=False,
            next_step=f"export {PROVIDER_ENV}=<provider>",
        )
    value = f"{provider}/{model}" if model else provider
    return CheckResult(name="provider", value=value, ok=True)


def _budget_check(budget_calls: int | None) -> CheckResult:
    if budget_calls is None:
        return CheckResult(
            name="budget", value="not set", ok=False,
            next_step=f"export {BUDGET_ENV}=<max model calls>",
        )
    return CheckResult(name="budget", value=f"{budget_calls} calls", ok=True)


def _budget() -> int | None:
    raw = os.environ.get(BUDGET_ENV, "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _openminion_install() -> tuple[str, str]:
    """Return the installed openminion version and install source.

    The version comes from package metadata, so no module is imported. A
    missing package yields ("unknown", "unknown"); the source is read from
    the distribution's own installer records.
    """
    try:
        version = importlib_metadata.version("openminion")
    except importlib_metadata.PackageNotFoundError:
        return "unknown", "unknown"
    distribution = importlib_metadata.distribution("openminion")
    return redact_text(version), _install_source(distribution)


def _install_source(distribution: importlib_metadata.Distribution) -> str:
    direct_url = distribution.read_text("direct_url.json") or ""
    if '"editable": true' in direct_url:
        return "editable"
    installer = (distribution.read_text("INSTALLER") or "").strip()
    if installer in {"pip", "uv"}:
        return installer
    if installer:
        return "pip"
    return "unknown"
