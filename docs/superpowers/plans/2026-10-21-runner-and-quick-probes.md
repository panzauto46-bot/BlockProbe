# Runner and Quick Probes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `blockprobe run --profile quick` runs P01, P02, P03, P04, P06 and P10 inside an isolated OpenMinion home and writes `runs/<id>/results.json` plus `building-blocks-tested.md`.

**Architecture:** Probes implement one small protocol and receive a frozen context; the runner owns repeats, timeout, budget and status aggregation, so probe code only performs assertions. `env.py` sets and restores the three `OPENMINION_*` roots for the duration of a run. The SDK is imported lazily inside probes, so the package installs and tests without the `probe` extra.

**Tech Stack:** Python 3.11+, pydantic 2, standard library (`concurrent.futures`, `statistics`, `subprocess`), `openminion` 0.1.x as an optional dependency.

**Spec:** `PRD.md` §7 (FR-01…FR-07), §8 (probe catalog), §10 (SDK surfaces), §11 (project structure); `.superpowers/sdd/2026-10-20-cli-surface-report-layer/phase0-findings.md` F-007…F-013.

## Global Constraints

- Python `>=3.11`; Windows PowerShell and Linux must both pass.
- Probe statuses are exactly `PASS`, `FLAKY`, `FAIL`, `SKIP`, `ERROR`; format them with `str(...)`.
- Exit codes: `0` = only PASS/SKIP/FLAKY, `1` = any FAIL or ERROR, `2` = usage, `3` = budget exhausted, `4` = environment missing.
- Progress goes to stderr; data goes to stdout.
- One probe failing never aborts the run.
- Evidence and messages are redacted before storage and before display.
- `openminion` is the optional `probe` extra: import it inside probes, never at module import time.
- Unit tests never touch the network and never require a credential.
- A run writes only inside `runs/<id>/`; `runs/` is gitignored.
- Every probe declares `doc_ref` and the versions it applies to.

## Review Focus

1. A probe raising an unexpected exception becomes `ERROR`; the run continues (Task 4).
2. Exhausting the budget mid-run turns the remaining probes into `SKIP` and exits 3 (Tasks 1, 4, 12).
3. `OPENMINION_*` variables are restored even when a probe raises (Task 3).
4. A machine without `openminion` reports `SKIP`/exit 4, never a traceback (Tasks 6–12).
5. A probe that exceeds its timeout becomes `ERROR` and the run continues (Task 4).

---

### Task 1: Call budget

**Files:**
- Create: `src/blockprobe/budget.py`
- Create: `tests/test_budget.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `class BudgetExhausted(Exception)`.
  - `class CallBudget`: `__init__(self, limit: int | None = None)`, read-only `used: int`, `remaining: int | None`, `exhausted: bool`, `take(self, calls: int = 1) -> None`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_budget.py
import pytest

from blockprobe.budget import BudgetExhausted, CallBudget


def test_unlimited_budget_never_raises():
    budget = CallBudget()
    for _ in range(100):
        budget.take()
    assert budget.used == 100
    assert budget.remaining is None
    assert budget.exhausted is False


def test_budget_stops_at_the_limit():
    budget = CallBudget(limit=2)
    budget.take()
    budget.take()
    assert budget.remaining == 0
    assert budget.exhausted is True
    with pytest.raises(BudgetExhausted):
        budget.take()


def test_take_more_than_remaining_raises_without_counting():
    budget = CallBudget(limit=3)
    with pytest.raises(BudgetExhausted):
        budget.take(4)
    assert budget.used == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_budget.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'blockprobe.budget'`

- [ ] **Step 3: Implement `budget.py`**

`take` raises before mutating, so a refused batch does not consume budget. `exhausted` is true when `limit` is not `None` and `used >= limit`. A negative limit is a `ValueError`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_budget.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/blockprobe/budget.py tests/test_budget.py
git commit -m "feat: add the model-call budget"
```

---

### Task 2: Probe protocol

**Files:**
- Create: `src/blockprobe/probes/__init__.py`
- Create: `src/blockprobe/probes/base.py`
- Create: `tests/test_probe_base.py`

**Interfaces:**
- Consumes: `CallBudget` from `blockprobe.budget`.
- Produces:
  - `@dataclass(frozen=True) class ProbeContext`: `run_id: str`, `provider: str`, `model: str`, `home: Path`, `data_root: Path`, `generated_root: Path`, `timeout_s: float`, `budget: CallBudget`, `config_path: Path | None = None`.
  - `@dataclass class ProbeAttempt`: `passed: bool`, `latency_s: float`, `calls: int = 0`, `evidence: list[str] = field(default_factory=list)`, `message: str | None = None`, `skipped: bool = False`, `error: bool = False`.
  - `@runtime_checkable class Probe(Protocol)`: `probe_id: str`, `label: str`, `building_block: str`, `doc_ref: str`, `requires_model: bool`, `run(self, ctx: ProbeContext) -> ProbeAttempt`.
  - `src/blockprobe/probes/__init__.py` is empty apart from a docstring in this task.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_probe_base.py
from pathlib import Path

import pytest

from blockprobe.budget import CallBudget
from blockprobe.probes.base import Probe, ProbeAttempt, ProbeContext


def context() -> ProbeContext:
    return ProbeContext(
        run_id="r", provider="echo", model="echo",
        home=Path("."), data_root=Path("."), generated_root=Path("."),
        timeout_s=5.0, budget=CallBudget(),
    )


def test_context_defaults_config_path_to_none():
    assert context().config_path is None


def test_attempt_defaults_are_neutral():
    attempt = ProbeAttempt(passed=True, latency_s=0.1)
    assert attempt.calls == 0
    assert attempt.evidence == []
    assert attempt.message is None
    assert attempt.skipped is False
    assert attempt.error is False


def test_probe_is_a_runtime_checkable_protocol():
    class Fake:
        probe_id = "P99"
        label = "fake"
        building_block = "Test"
        doc_ref = "x"
        requires_model = False

        def run(self, ctx):
            return ProbeAttempt(passed=True, latency_s=0.0)

    assert isinstance(Fake(), Probe)
    assert not isinstance(object(), Probe)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_probe_base.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'blockprobe.probes'`

- [ ] **Step 3: Implement `probes/base.py` and `probes/__init__.py`**

Use `@dataclass(frozen=True)` for the context and a plain `@dataclass` for the attempt. The protocol uses `@runtime_checkable`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_probe_base.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/blockprobe/probes/__init__.py src/blockprobe/probes/base.py tests/test_probe_base.py
git commit -m "feat: define the probe protocol"
```

---

### Task 3: Run paths and isolation

**Files:**
- Create: `src/blockprobe/env.py`
- Create: `tests/test_env.py`

**Interfaces:**
- Consumes: nothing.
- Produces (in `blockprobe.env`):
  - `ISOLATION_VARS = ("OPENMINION_HOME", "OPENMINION_DATA_ROOT", "OPENMINION_GENERATED_ROOT")`.
  - `@dataclass(frozen=True) class RunPaths`: `root: Path`, `home: Path`, `data: Path`, `generated: Path`.
  - `new_run_id(now: datetime | None = None) -> str` — `YYYY-MM-DD-HHMM` in local time.
  - `prepare_run_paths(root: Path, run_id: str) -> RunPaths` — creates `root/run_id/{home,data,generated}` and returns them.
  - `isolated_environment(paths: RunPaths, config_path: Path | None = None)` — context manager that sets the three variables (and `OPENMINION_CONFIG_PATH` when given), restoring every previous value, including removing variables that were unset, even when the body raises.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_env.py
import os
from datetime import datetime
from pathlib import Path

import pytest

from blockprobe.env import (
    new_run_id, prepare_run_paths, isolated_environment,
)


def test_new_run_id_is_sortable():
    assert new_run_id(datetime(2026, 10, 21, 10, 15)) == "2026-10-21-1015"


def test_prepare_creates_the_three_roots(tmp_path):
    paths = prepare_run_paths(tmp_path, "2026-10-21-1015")
    assert paths.root == tmp_path / "2026-10-21-1015"
    assert paths.home.is_dir()
    assert paths.data.is_dir()
    assert paths.generated.is_dir()


def test_environment_is_set_inside_and_restored_after(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENMINION_HOME", raising=False)
    monkeypatch.delenv("OPENMINION_DATA_ROOT", raising=False)
    monkeypatch.delenv("OPENMINION_GENERATED_ROOT", raising=False)
    paths = prepare_run_paths(tmp_path, "r")
    with isolated_environment(paths):
        assert os.environ["OPENMINION_HOME"] == str(paths.home)
        assert os.environ["OPENMINION_DATA_ROOT"] == str(paths.data)
        assert os.environ["OPENMINION_GENERATED_ROOT"] == str(paths.generated)
    assert "OPENMINION_HOME" not in os.environ
    assert "OPENMINION_DATA_ROOT" not in os.environ
    assert "OPENMINION_GENERATED_ROOT" not in os.environ


def test_environment_is_restored_when_the_body_raises(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENMINION_HOME", raising=False)
    paths = prepare_run_paths(tmp_path, "r")
    with pytest.raises(RuntimeError):
        with isolated_environment(paths):
            raise RuntimeError("probe exploded")
    assert "OPENMINION_HOME" not in os.environ


def test_previous_values_win_on_exit(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENMINION_HOME", "before")
    paths = prepare_run_paths(tmp_path, "r")
    with isolated_environment(paths):
        assert os.environ["OPENMINION_HOME"] == str(paths.home)
    assert os.environ["OPENMINION_HOME"] == "before"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_env.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'blockprobe.env'`

- [ ] **Step 3: Implement `env.py`**

Capture `os.environ.get(name)` for every variable before setting it; on exit, set it back or `pop` it when it was absent. Use `try/finally` so an exception in the body still restores.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_env.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add src/blockprobe/env.py tests/test_env.py
git commit -m "feat: isolate each run in its own OpenMinion roots"
```

---

### Task 4: Runner

**Files:**
- Create: `src/blockprobe/runner.py`
- Create: `tests/test_runner.py`

**Interfaces:**
- Consumes: `BudgetExhausted`, `CallBudget`; `Probe`, `ProbeAttempt`, `ProbeContext`; `ProbeResult`, `ProbeStatus`, `RunSummary`.
- Produces (in `blockprobe.runner`):
  - `@dataclass(frozen=True) class RunMeta`: `run_id: str`, `started_at: str`, `openminion_version: str = "unknown"`, `python_version: str = "unknown"`, `os_name: str = "unknown"`, `provider: str = "unknown"`, `model: str = "unknown"`.
  - `@dataclass class RunOutcome`: `summary: RunSummary`, `budget_exhausted: bool = False`.
  - `run_probes(probes: Sequence[Probe], ctx: ProbeContext, meta: RunMeta, repeats: int = 3) -> RunOutcome`.
  - `run_attempt(probe: Probe, ctx: ProbeContext) -> ProbeAttempt`.

**Behaviour:**
- One attempt runs in a worker thread and is abandoned after `ctx.timeout_s`; a timeout yields `ProbeAttempt(passed=False, error=True, message=f"timed out after {timeout_s:g}s")`.
- Any other exception yields `passed=False, error=True, message=str(exc)`, except `BudgetExhausted`, which propagates to the runner.
- Status: every attempt skipped → `SKIP`; any error → `ERROR`; all attempts pass → `PASS`; some pass → `FLAKY`; none pass → `FAIL`.
- `ProbeResult.repeats` is the number of attempts actually run; `passed` is the number that passed; `latency_p50_s` is the median of attempt latencies; `latency_p95_s` is the nearest-rank 95th percentile.
- On `BudgetExhausted`, the current probe keeps its completed attempts (or becomes `SKIP` with `repeats=1` when none ran) and every later probe becomes `SKIP` with `message="budget exhausted"`, `repeats=1`.
- `summary.total_calls` is the sum of `attempt.calls`; `duration_s` is wall time.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_runner.py
import time

from blockprobe.budget import CallBudget
from blockprobe.probes.base import ProbeAttempt, ProbeContext
from blockprobe.runner import RunMeta, run_probes


class FakeProbe:
    label = "fake"
    building_block = "Test"
    doc_ref = "x"
    requires_model = False

    def __init__(self, probe_id, outcomes):
        self.probe_id = probe_id
        self.outcomes = list(outcomes)

    def run(self, ctx):
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return ProbeAttempt(passed=outcome, latency_s=0.1, calls=1)


def context(timeout_s=5.0):
    return ProbeContext(
        run_id="r", provider="echo", model="echo",
        home=__import__("pathlib").Path("."),
        data_root=__import__("pathlib").Path("."),
        generated_root=__import__("pathlib").Path("."),
        timeout_s=timeout_s, budget=CallBudget(),
    )


def meta():
    return RunMeta(run_id="r", started_at="2026-10-21T10:15:00Z")


def test_three_passes_are_pass():
    outcome = run_probes([FakeProbe("P99", [True, True, True])], context(), meta())
    probe = outcome.summary.probes[0]
    assert str(probe.status) == "PASS"
    assert probe.repeats == 3 and probe.passed == 3
    assert outcome.budget_exhausted is False


def test_partial_passes_are_flaky():
    probe = run_probes([FakeProbe("P99", [True, False, True])], context(), meta()).summary.probes[0]
    assert str(probe.status) == "FLAKY"
    assert probe.passed == 2


def test_no_passes_is_fail():
    probe = run_probes([FakeProbe("P99", [False, False, False])], context(), meta()).summary.probes[0]
    assert str(probe.status) == "FAIL"


def test_an_exception_is_error_and_the_run_continues():
    outcome = run_probes(
        [
            FakeProbe("P99", [RuntimeError("boom"), RuntimeError("boom"), RuntimeError("boom")]),
            FakeProbe("P98", [True, True, True]),
        ],
        context(), meta(),
    )
    assert str(outcome.summary.probes[0].status) == "ERROR"
    assert "boom" in outcome.summary.probes[0].message
    assert str(outcome.summary.probes[1].status) == "PASS"


def test_timeout_is_error_and_the_run_continues():
    class Slow(FakeProbe):
        def run(self, ctx):
            time.sleep(0.3)
            return ProbeAttempt(passed=True, latency_s=0.3)

    outcome = run_probes(
        [Slow("P99", [True]), FakeProbe("P98", [True])],
        context(timeout_s=0.01), meta(), repeats=1,
    )
    assert str(outcome.summary.probes[0].status) == "ERROR"
    assert "timed out" in outcome.summary.probes[0].message
    assert str(outcome.summary.probes[1].status) == "PASS"


def test_budget_exhaustion_skips_the_rest():
    class Spender(FakeProbe):
        def run(self, ctx):
            ctx.budget.take()
            return ProbeAttempt(passed=True, latency_s=0.1, calls=1)

    ctx = context()
    ctx = ProbeContext(**{**ctx.__dict__, "budget": CallBudget(limit=1)})
    outcome = run_probes([Spender("P99", [True, True]), Spender("P98", [True])], ctx, meta(), repeats=2)
    assert outcome.budget_exhausted is True
    assert str(outcome.summary.probes[1].status) == "SKIP"
    assert outcome.summary.probes[1].message == "budget exhausted"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'blockprobe.runner'`

- [ ] **Step 3: Implement `runner.py`**

Use `ThreadPoolExecutor(max_workers=1)` per attempt and `future.result(timeout=ctx.timeout_s)`; on `TimeoutError` call `executor.shutdown(wait=False, cancel_futures=True)` and return the timeout attempt. Catch `BudgetExhausted` before the generic `Exception`. Percentiles: `statistics.median` and nearest-rank (`sorted_latencies[math.ceil(0.95 * n) - 1]`).

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_runner.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add src/blockprobe/runner.py tests/test_runner.py
git commit -m "feat: run probes with repeats, timeout and budget"
```

---

### Task 5: results.json

**Files:**
- Create: `src/blockprobe/report/results.py`
- Create: `tests/test_results.py`

**Interfaces:**
- Consumes: `RunSummary`; `RunPaths`; `redact_model`.
- Produces (in `blockprobe.report.results`):
  - `RESULTS_FILENAME = "results.json"`.
  - `write_results(summary: RunSummary, paths: RunPaths) -> Path` — redacts a copy, writes `paths.root / RESULTS_FILENAME` as indented JSON, returns the path.
  - `read_results(path: Path) -> RunSummary` — parses a results file; raises `ValueError` on bad JSON or validation failure.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_results.py
import json

import pytest

from blockprobe.env import prepare_run_paths
from blockprobe.models import ProbeResult, ProbeStatus, RunSummary
from blockprobe.report.results import RESULTS_FILENAME, read_results, write_results


def sample() -> RunSummary:
    return RunSummary(
        run_id="2026-10-21-1015", started_at="2026-10-21T10:15:00Z",
        probes=[ProbeResult(
            probe_id="P01", label="contract", building_block="Public contract",
            status=ProbeStatus.PASS, repeats=3, passed=3,
            evidence=[r"C:\Users\dan\run.log"],
        )],
        total_calls=3, duration_s=1.2,
    )


def test_write_and_read_round_trip(tmp_path):
    paths = prepare_run_paths(tmp_path, "2026-10-21-1015")
    written = write_results(sample(), paths)
    assert written == paths.root / RESULTS_FILENAME
    assert read_results(written) == sample()


def test_written_evidence_is_redacted(tmp_path):
    paths = prepare_run_paths(tmp_path, "r")
    written = write_results(sample(), paths)
    assert "dan" not in written.read_text(encoding="utf-8")


def test_read_results_rejects_bad_json(tmp_path):
    bad = tmp_path / "results.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError):
        read_results(bad)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_results.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'blockprobe.report.results'`

- [ ] **Step 3: Implement `results.py`**

`write_results` calls `redact_model(summary)` (cast back to `RunSummary`) and `model_dump_json(indent=2)` with a trailing newline. `read_results` catches `OSError`/`ValueError` from `model_validate_json` and re-raises `ValueError` with the path in the message.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_results.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/blockprobe/report/results.py tests/test_results.py
git commit -m "feat: write and read results.json"
```

---

### Task 6: Contract data and P01

**Files:**
- Create: `contracts/0.1.x.json`
- Create: `src/blockprobe/probes/p01_contract.py`
- Create: `tests/test_p01_contract.py`

**Interfaces:**
- Consumes: `ProbeAttempt`, `ProbeContext`; `redact_text`.
- Produces:
  - `contracts/0.1.x.json` with exactly this content:

```json
{
  "line": "0.1.x",
  "source": "API_COMPATIBILITY.md, last updated 2026-10-14",
  "root_exports": ["APIRuntime", "Agent", "AgentOutputValidationError", "AgentRunResult", "Handoff", "MemoryBundle", "OpenMinionConfig", "ProviderError", "subagent", "tool", "__version__", "TurnTimeoutError"],
  "api_exports": ["APIRuntime", "Agent", "AgentOutputValidationError", "AgentRunResult", "Handoff", "ProviderError", "RuntimeTurnHandle", "ToolCallSummary", "TurnChunk", "TurnError", "TurnResponse", "TurnTelemetry", "dispatch_request", "subagent", "TurnTimeoutError"],
  "console_scripts": ["openminion", "telemetryctl", "opsctl", "openminiond", "openminion-tool", "identityctl", "openminion-controlplane", "runtimectl", "brainctl", "memctl", "sessctl", "contextctl", "ctxctl", "agentregctl", "artifactctl", "openminion-controlplane-telegram", "openminion-controlplane-slack", "skill", "skillctl", "a2actl", "rlmctl", "retrievectl", "policyctl"]
}
```

  - `load_contract(path: Path | None = None) -> dict` — reads the packaged JSON (default path resolved from `__file__` two parents up, then `contracts/0.1.x.json`).
  - `check_contract(pkg, api, root_names, api_names, which, scripts) -> list[str]` — returns evidence strings in this order: `missing root export: <name>`, `missing api export: <name>`, `missing console script: <name>`, `__version__ is not a string`.
  - `class ContractProbe`: `probe_id="P01"`, `label="contract"`, `building_block="Public contract"`, `doc_ref="API_COMPATIBILITY.md#public-python-import-roots"`, `requires_model=False`, `run(ctx)`.
  - `PROBE = ContractProbe()`.

**Behaviour:** `run` imports `openminion` and `openminion.api` inside a `try`; `ImportError` returns a skipped attempt with `message="openminion is not installed"`. Otherwise it passes `shutil.which` and the contract lists to `check_contract`; `passed` is `not evidence`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_p01_contract.py
from types import SimpleNamespace

from blockprobe.probes.p01_contract import check_contract, load_contract


def test_contract_file_matches_the_documented_surface():
    contract = load_contract()
    assert contract["line"] == "0.1.x"
    assert len(contract["root_exports"]) == 12
    assert len(contract["api_exports"]) == 15
    assert len(contract["console_scripts"]) == 23
    assert "TurnTimeoutError" in contract["root_exports"]


def test_check_contract_reports_missing_names_in_order():
    pkg = SimpleNamespace(Agent=object, __version__="0.1.8")
    api = SimpleNamespace(Agent=object)
    evidence = check_contract(
        pkg, api, ["Agent", "Nope"], ["Agent", "Nope2"],
        which=lambda name: None, scripts=["openminion"],
    )
    assert evidence == [
        "missing root export: Nope",
        "missing api export: Nope2",
        "missing console script: openminion",
    ]


def test_check_contract_accepts_a_complete_surface():
    pkg = SimpleNamespace(Agent=object, __version__="0.1.8")
    api = SimpleNamespace(Agent=object)
    evidence = check_contract(
        pkg, api, ["Agent"], ["Agent"],
        which=lambda name: f"/bin/{name}", scripts=["openminion"],
    )
    assert evidence == []


def test_check_contract_flags_a_non_string_version():
    pkg = SimpleNamespace(Agent=object, __version__=8)
    evidence = check_contract(
        pkg, SimpleNamespace(Agent=object), ["Agent"], ["Agent"],
        which=lambda name: "/bin/x", scripts=[],
    )
    assert evidence == ["__version__ is not a string"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_p01_contract.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'blockprobe.probes.p01_contract'`

- [ ] **Step 3: Implement `contracts/0.1.x.json` and `p01_contract.py`**

Package the contract file with the repo (it is read from the source tree in this plan). `load_contract` uses `Path(__file__).resolve().parents[3] / "contracts" / "0.1.x.json"`. `run` wraps the timing and returns a `ProbeAttempt` with `calls=0`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_p01_contract.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add contracts/0.1.x.json src/blockprobe/probes/p01_contract.py tests/test_p01_contract.py
git commit -m "feat: add the 0.1.x contract probe"
```

---

### Task 7: SDK loader and P02 agent execution

**Files:**
- Create: `src/blockprobe/probes/sdk.py`
- Create: `src/blockprobe/probes/p02_agent.py`
- Create: `tests/test_p02_agent.py`

**Interfaces:**
- Consumes: `ProbeAttempt`, `ProbeContext`; `redact_text`.
- Produces:
  - `probes/sdk.py`: `load_openminion()` — imports and returns the `openminion` module; `sdk_available() -> bool` — true when `importlib.util.find_spec("openminion")` is not `None`.
  - `probes/p02_agent.py`: `class AgentProbe` with `probe_id="P02"`, `label="agent_run"`, `building_block="Agent execution"`, `doc_ref="docs/sdk/agents.md#agent-run"`, `requires_model=True`, `run(ctx)`; `PROBE = AgentProbe()`.
  - `evaluate_result(result) -> list[str]` — pure check returning evidence strings.

**Behaviour:** `run` calls `ctx.budget.take()`, then `with sdk.Agent(instructions=..., config_path=str(ctx.config_path) if ctx.config_path else None, model=ctx.model) as agent: result = agent.run("Reply with the single word: pong.")`. Evidence: `empty text`, `missing session_id`, `missing result id`, `stats is not a dict`. `ImportError` → skipped attempt. A `ProviderError` → `error=True` with the redacted message.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_p02_agent.py
from types import SimpleNamespace

from blockprobe.probes.p02_agent import evaluate_result


def result(**overrides):
    base = dict(text="pong", session_id="s1", id="r1", stats={})
    base.update(overrides)
    return SimpleNamespace(**base)


def test_a_complete_result_has_no_evidence():
    assert evaluate_result(result()) == []


def test_empty_text_is_reported():
    assert evaluate_result(result(text="  ")) == ["empty text"]


def test_missing_ids_are_reported():
    assert evaluate_result(result(session_id=None, id=None)) == [
        "missing session_id", "missing result id",
    ]


def test_non_dict_stats_are_reported():
    assert evaluate_result(result(stats=[])) == ["stats is not a dict"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_p02_agent.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'blockprobe.probes.p02_agent'`

- [ ] **Step 3: Implement `sdk.py` and `p02_agent.py`**

Keep `evaluate_result` free of SDK imports so the test runs without the extra. In `run`, import through `sdk.load_openminion()` and catch `ImportError` separately.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_p02_agent.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/blockprobe/probes/sdk.py src/blockprobe/probes/p02_agent.py tests/test_p02_agent.py
git commit -m "feat: add the agent execution probe"
```

---

### Task 8: P03 tools

**Files:**
- Create: `src/blockprobe/probes/p03_tools.py`
- Create: `tests/test_p03_tools.py`

**Interfaces:**
- Consumes: `ProbeAttempt`, `ProbeContext`; `load_openminion`; `evaluate_tool_call`.
- Produces:
  - `class ToolsProbe` with `probe_id="P03"`, `label="tool_call"`, `building_block="Tools"`, `doc_ref="docs/sdk/tools.md#tool-decorator"`, `requires_model=True`, `run(ctx)`; `PROBE = ToolsProbe()`.
  - `evaluate_tool_call(seen, expected) -> list[str]` — pure check.

**Behaviour:** define a decorated `record(value: int) -> str` that stores `value` in a dict; run `Agent(..., tools=[record], forced_tools=["record"])` with the prompt `Call record with value 7.`; evidence is `tool was not called` when nothing was recorded and `wrong argument type: <type>` when the value is not an `int` equal to 7. Also assert `sdk.tool(plain, description="x")` returns a callable and record `functional tool() returned a non-callable` otherwise. Budget `take()` before the agent call.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_p03_tools.py
from blockprobe.probes.p03_tools import evaluate_tool_call


def test_no_call_is_reported():
    assert evaluate_tool_call({}, expected=7) == ["tool was not called"]


def test_wrong_type_is_reported():
    assert evaluate_tool_call({"value": "7"}, expected=7) == [
        "wrong argument type: str",
    ]


def test_wrong_value_is_reported():
    assert evaluate_tool_call({"value": 8}, expected=7) == [
        "wrong argument value: 8",
    ]


def test_a_correct_call_has_no_evidence():
    assert evaluate_tool_call({"value": 7}, expected=7) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_p03_tools.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'blockprobe.probes.p03_tools'`

- [ ] **Step 3: Implement `p03_tools.py`**

Order of evidence checks: no call, wrong type, wrong value. The functional-tool check runs before the agent call so a broken `tool()` is reported even when the model call fails.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_p03_tools.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/blockprobe/probes/p03_tools.py tests/test_p03_tools.py
git commit -m "feat: add the tool calling probe"
```

---

### Task 9: P04 sessions

**Files:**
- Create: `src/blockprobe/probes/p04_sessions.py`
- Create: `tests/test_p04_sessions.py`

**Interfaces:**
- Consumes: `ProbeAttempt`, `ProbeContext`; `load_openminion`.
- Produces:
  - `class SessionsProbe` with `probe_id="P04"`, `label="sessions"`, `building_block="Sessions"`, `doc_ref="docs/sdk/sessions.md#session-id"`, `requires_model=True`, `run(ctx)`; `PROBE = SessionsProbe()`.
  - `evaluate_sessions(first, second, third, session_id) -> list[str]`.

**Behaviour:** run three agents: two with `session_id=f"blockprobe-{ctx.run_id}"`, one with `f"blockprobe-{ctx.run_id}-other"`. Evidence: `first session_id differs`, `second session_id differs`, `other session_id was reused` (it must not equal the first), and `context was not retained` when the second answer does not contain the word planted in the first prompt (`"pineapple"`). Budget `take()` once per agent call.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_p04_sessions.py
from types import SimpleNamespace

from blockprobe.probes.p04_sessions import evaluate_sessions


def result(session_id, text="ok"):
    return SimpleNamespace(session_id=session_id, text=text)


def test_matching_ids_and_retained_context_pass():
    assert evaluate_sessions(
        result("s"), result("s", "pineapple"), result("other"), "s",
    ) == []


def test_a_different_first_id_is_reported():
    assert "first session_id differs" in evaluate_sessions(
        result("x"), result("s", "pineapple"), result("other"), "s",
    )


def test_a_reused_other_id_is_reported():
    assert "other session_id was reused" in evaluate_sessions(
        result("s"), result("s", "pineapple"), result("s"), "s",
    )


def test_lost_context_is_reported():
    assert "context was not retained" in evaluate_sessions(
        result("s"), result("s", "nothing"), result("other"), "s",
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_p04_sessions.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'blockprobe.probes.p04_sessions'`

- [ ] **Step 3: Implement `p04_sessions.py`**

Prompt 1: `Remember the word pineapple. Reply with: stored.` Prompt 2: `Which word did I ask you to remember? Reply with it.` Prompt 3 uses the other id with `Reply with: ok.` Evidence order as listed above.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_p04_sessions.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/blockprobe/probes/p04_sessions.py tests/test_p04_sessions.py
git commit -m "feat: add the sessions probe"
```

---

### Task 10: P06 errors and timeouts

**Files:**
- Create: `src/blockprobe/probes/p06_errors.py`
- Create: `tests/test_p06_errors.py`

**Interfaces:**
- Consumes: `ProbeAttempt`, `ProbeContext`; `load_openminion`.
- Produces:
  - `class ErrorsProbe` with `probe_id="P06"`, `label="errors"`, `building_block="Errors"`, `doc_ref="API_COMPATIBILITY.md#provider-failures"`, `requires_model=False`, `run(ctx)`; `PROBE = ErrorsProbe()`.
  - `write_broken_config(path: Path) -> Path` — writes a minimal `agents.json` whose active agent uses provider `ollama`, model `llama3.1`, `base_url` `http://127.0.0.1:9`, `timeout_seconds` 2, `runtime.provider_retry_max_attempts` 1, `runtime.chat_turn_timeout_seconds` 1, and `storage.path` under the run root.
  - `evaluate_provider_failure(exc, returned, sdk, provider_error_type) -> list[str]` — pure check; `provider_error_type` is the SDK's `ProviderError` class.

**Behaviour:** create the broken config under `ctx.home / "p06"`, call `Agent(config_path=..., model="llama3.1").run("ping")` inside `try`:
- `ProviderError` → no evidence, add `TurnTimeoutError` evidence when the SDK lacks the export: `TurnTimeoutError not exported before 0.1.5`.
- any other exception → evidence `unexpected error: <type>`.
- a returned result → evidence `provider failure was returned as an answer`.
The probe passes when the evidence is empty; `calls=1`; `requires_model=False` because no model is reached.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_p06_errors.py
from types import SimpleNamespace

from blockprobe.probes.p06_errors import evaluate_provider_failure


class ProviderError(Exception):
    pass


def sdk(exported=True):
    namespace = SimpleNamespace()
    if exported:
        namespace.TurnTimeoutError = type("TurnTimeoutError", (Exception,), {})
    return namespace


def test_a_provider_error_passes():
    assert evaluate_provider_failure(ProviderError("bad"), None, sdk(), ProviderError) == []


def test_a_returned_answer_is_reported():
    evidence = evaluate_provider_failure(
        None, SimpleNamespace(text="error"), sdk(), ProviderError,
    )
    assert evidence == ["provider failure was returned as an answer"]


def test_a_missing_export_is_recorded():
    evidence = evaluate_provider_failure(
        ProviderError("bad"), None, sdk(exported=False), ProviderError,
    )
    assert evidence == ["TurnTimeoutError not exported before 0.1.5"]


def test_an_unexpected_exception_is_reported():
    evidence = evaluate_provider_failure(ValueError("nope"), None, sdk(), ProviderError)
    assert evidence == ["unexpected error: ValueError"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_p06_errors.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'blockprobe.probes.p06_errors'`

- [ ] **Step 3: Implement `p06_errors.py`**

`evaluate_provider_failure(exc, returned, sdk, provider_error_type)` receives the caught exception, the returned result (one of them is `None`), the loaded SDK module and the SDK's `ProviderError` class. Check `isinstance(exc, provider_error_type)`; never import the SDK at module scope.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_p06_errors.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/blockprobe/probes/p06_errors.py tests/test_p06_errors.py
git commit -m "feat: add the provider error probe"
```

---

### Task 11: P10 diagnostics

**Files:**
- Create: `src/blockprobe/probes/p10_diagnostics.py`
- Create: `tests/test_p10_diagnostics.py`

**Interfaces:**
- Consumes: `ProbeAttempt`, `ProbeContext`.
- Produces:
  - `class DiagnosticsProbe` with `probe_id="P10"`, `label="diagnostics"`, `building_block="Diagnostics"`, `doc_ref="docs/cli/doctor.md#check-turn"`, `requires_model=False`, `run(ctx)`; `PROBE = DiagnosticsProbe()`.
  - `parse_doctor_output(text: str) -> list[str]` — evidence for unparseable or failing output.
  - `parse_readiness(text: str) -> list[str]` — evidence when readiness is neither ready nor demo.

**Behaviour:** run `openminion doctor --check-turn --json` and `openminion status readiness` through `subprocess.run([...], capture_output=True, text=True, timeout=ctx.timeout_s, env=os.environ)`; a non-zero exit is evidence `doctor exited <code>`, invalid JSON is `doctor output is not JSON`, and readiness output without `ready` or `demo` is `readiness output is not recognised`. The probe passes when the evidence is empty; `calls=0`. `FileNotFoundError` → skipped with `message="openminion is not installed"`. Subprocess failures (`OSError`, `subprocess.TimeoutExpired`) are evidence, not crashes.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_p10_diagnostics.py
from blockprobe.probes.p10_diagnostics import parse_doctor_output, parse_readiness


def test_valid_doctor_json_has_no_evidence():
    assert parse_doctor_output('{"ok": true}') == []


def test_invalid_doctor_json_is_reported():
    assert parse_doctor_output("not json") == ["doctor output is not JSON"]


def test_ready_is_accepted():
    assert parse_readiness("status: ready") == []


def test_demo_is_accepted():
    assert parse_readiness("status: demo (echo provider)") == []


def test_unknown_readiness_is_reported():
    assert parse_readiness("status: broken") == [
        "readiness output is not recognised",
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_p10_diagnostics.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'blockprobe.probes.p10_diagnostics'`

- [ ] **Step 3: Implement `p10_diagnostics.py`**

Use `shutil.which("openminion")` first; when absent return a skipped attempt. Parse the doctor JSON with `json.loads`; the readiness check is a case-insensitive substring test for `ready` or `demo`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_p10_diagnostics.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add src/blockprobe/probes/p10_diagnostics.py tests/test_p10_diagnostics.py
git commit -m "feat: add the diagnostics probe"
```

---

### Task 12: Probe catalog and `run` command

**Files:**
- Create: `src/blockprobe/probes/catalog.py`
- Modify: `src/blockprobe/cli.py`
- Create: `tests/test_cli_run.py`

**Interfaces:**
- Consumes: every `PROBE`; `run_probes`, `RunMeta`; `prepare_run_paths`, `isolated_environment`, `new_run_id`; `write_results`; `write_building_blocks_md`; `capture_environment`.
- Produces:
  - `probes/catalog.py`: `QUICK = ("P01", "P02", "P03", "P04", "P06", "P10")`, `PROFILES = {"quick": QUICK}`, `build_probes(profile: str) -> list[Probe]` — raises `KeyError` for an unknown profile.
  - `cli.py`: `blockprobe run` with `--profile quick` (default), `--provider`, `--model`, `--repeats 3`, `--budget`, `--out runs`, `--run-id`, `--config`, `--force`, `--no-color`.
  - `main` dispatches `run` alongside `doctor` and `report`.

**Behaviour:**
- If `importlib.util.find_spec("openminion")` is `None`, print the three-part environment error to stderr and return `EXIT_ENVIRONMENT`.
- `--profile full` prints `error: profile 'full' is not implemented yet.` plus `hint: use --profile quick` and returns `EXIT_USAGE`.
- The run prints each finished probe line to **stderr** (progress) and, at the end, `render_run(...)` to **stdout**.
- It writes `results.json` and `building-blocks-tested.md` into the run directory (`--force` reaches the Markdown writer).
- Exit code: `EXIT_BUDGET` when `outcome.budget_exhausted`, else `EXIT_FAILURE` when any probe is `FAIL`/`ERROR`, else `EXIT_OK`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_run.py
from pathlib import Path

from blockprobe.cli import main
from blockprobe.probes.base import ProbeAttempt


class FakeProbe:
    probe_id = "P99"
    label = "fake"
    building_block = "Test"
    doc_ref = "x"
    requires_model = False

    def run(self, ctx):
        return ProbeAttempt(passed=True, latency_s=0.1, calls=0)


def test_run_writes_both_files(tmp_path, monkeypatch):
    monkeypatch.setattr("blockprobe.cli.build_probes", lambda profile: [FakeProbe()])
    monkeypatch.setattr("blockprobe.cli.sdk_available", lambda: True)
    code = main([
        "run", "--provider", "echo", "--model", "echo",
        "--repeats", "1", "--out", str(tmp_path), "--run-id", "2026-10-21-1015",
    ])
    run_dir = tmp_path / "2026-10-21-1015"
    assert code == 0
    assert (run_dir / "results.json").is_file()
    assert (run_dir / "building-blocks-tested.md").is_file()


def test_run_without_the_sdk_is_an_environment_error(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("blockprobe.cli.sdk_available", lambda: False)
    code = main(["run", "--out", str(tmp_path)])
    assert code == 4
    assert "openminion" in capsys.readouterr().err.lower()


def test_full_profile_is_not_implemented(tmp_path, capsys):
    code = main(["run", "--profile", "full", "--out", str(tmp_path)])
    assert code == 2
    assert "not implemented" in capsys.readouterr().err
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli_run.py -v`
Expected: FAIL — `run` is not a known command.

- [ ] **Step 3: Implement the catalog and the `run` command**

Add `run` to `USAGE_GROUPS` under `probe`. Build `RunMeta` from `capture_environment()` plus the arguments; create the id with `new_run_id()` when `--run-id` is absent. Wrap the probe loop in `isolated_environment(paths, config_path=args.config)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_cli_run.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/blockprobe/probes/catalog.py src/blockprobe/cli.py tests/test_cli_run.py
git commit -m "feat: add the run command and quick profile"
```

---

### Task 13: Echo-provider harness and CI lane

**Files:**
- Create: `tests/test_probe_catalog_echo.py`
- Modify: `pyproject.toml` (register the `probe` marker)
- Modify: `.github/workflows/ci.yml` (second job)

**Interfaces:**
- Consumes: `build_probes`; `sdk_available`; `prepare_run_paths`; `isolated_environment`; `run_probes`, `RunMeta`; `CaptureEnvironment`/`capture_environment`.
- Produces: tests marked `@pytest.mark.probe`, skipped with `pytest.mark.skipif(not sdk_available())`.

**Behaviour:** initialise the echo provider inside the isolated home with `subprocess.run([sys.executable, "-m", "openminion", "config", "init", "--provider", "echo"], env=os.environ, check=True, timeout=120)`, then run the quick catalog with `repeats=1`. The test asserts the run returns six probe results, none raises, and every status is one of the five; it does not assert PASS, because the echo provider is intentionally not a model.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_probe_catalog_echo.py
import os
import subprocess
import sys

import pytest

from blockprobe.budget import CallBudget
from blockprobe.env import isolated_environment, prepare_run_paths
from blockprobe.probes.base import ProbeContext
from blockprobe.probes.catalog import QUICK, build_probes
from blockprobe.probes.sdk import sdk_available
from blockprobe.runner import RunMeta, run_probes

pytestmark = [
    pytest.mark.probe,
    pytest.mark.skipif(not sdk_available(), reason="openminion is not installed"),
]


def test_the_quick_catalog_runs_on_the_echo_provider(tmp_path):
    paths = prepare_run_paths(tmp_path, "echo")
    with isolated_environment(paths):
        subprocess.run(
            [sys.executable, "-m", "openminion", "config", "init", "--provider", "echo"],
            check=True, timeout=120, capture_output=True, text=True,
        )
        ctx = ProbeContext(
            run_id="echo", provider="echo", model="echo",
            home=paths.home, data_root=paths.data, generated_root=paths.generated,
            timeout_s=120.0, budget=CallBudget(limit=50),
            config_path=paths.home / ".openminion" / "agents.json",
        )
        outcome = run_probes(build_probes("quick"), ctx, RunMeta(run_id="echo", started_at="now"), repeats=1)
    assert [p.probe_id for p in outcome.summary.probes] == list(QUICK)
    assert all(str(p.status) in {"PASS", "FLAKY", "FAIL", "SKIP", "ERROR"} for p in outcome.summary.probes)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_probe_catalog_echo.py -v`
Expected: SKIPPED when `openminion` is absent; in the probe venv it fails because `catalog` or the harness is incomplete.

- [ ] **Step 3: Register the marker and add the CI job**

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
markers = ["probe: exercises the installed openminion SDK on the echo provider"]
```

Add a `probe` job to `.github/workflows/ci.yml` that installs `-e ".[dev,probe]"` and runs `python -m pytest -q -W error -m probe`.

- [ ] **Step 4: Run the focused test where the SDK exists**

Run (probe venv): `python -m pytest tests/test_probe_catalog_echo.py -v`
Expected: PASS (1 passed) once the echo config initialises.

- [ ] **Step 5: Commit**

```bash
git add tests/test_probe_catalog_echo.py pyproject.toml .github/workflows/ci.yml
git commit -m "test: run the quick catalog on the echo provider"
```

---

## Self-Review

- **Spec coverage:** FR-01 (Task 3/12 metadata), FR-02 (Task 3), FR-03 (Tasks 1/4), FR-04 (every probe's `doc_ref`), FR-05 (Task 12 catalog), FR-06 (Tasks 5/7–11), FR-07 (Task 5 + existing Markdown writer). FR-08…FR-17 are out of this plan (M2/M3).
- **Review Focus:** every line is pinned in the task named beside it.
- **Types:** `RunMeta`, `RunOutcome`, `ProbeContext`, `ProbeAttempt`, `RunPaths` are used with the same field names in every later task.
- **Proportion:** the plan carries signatures and assertions, not implementations.
