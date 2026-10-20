# BlockProbe — CLI Surface & Report Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a working `blockprobe` command that renders a probe run to the terminal and to `building-blocks-tested.md` in the exact shape the design doc specifies, plus a `doctor` command, with the whole surface testable on the echo provider without any credential.

**Architecture:** Two layers. A **model layer** (`models.py`, `redact.py`) that owns the shape of a run and the removal of secrets. A **render layer** (`terminal.py`, `report/`) that turns a `RunSummary` into terminal lines, a Markdown report, and JSON. The **CLI** (`cli.py`, `doctor.py`) wires them together and owns exit codes. The render layer never talks to OpenMinion and never touches the network, so the entire surface is testable against fixture data with zero credentials.

**Tech Stack:** Python 3.11+, `pydantic` v2 for the data models, `pytest` for tests, standard library only for terminal handling (`os`, `sys`, `shutil`, `json`). No colour library, no templating engine, no CLI framework — `argparse` from the standard library.

**Spec:** `docs/superpowers/specs/2026-10-20-cli-ux-design.md`

**Scope note:** This plan covers the design doc's decisions for the CLI surface and report layer only: D1, D2, D3, D4, D10, D11, D12, D13, D15, D18, D19. The probe runner, the probes themselves, environment isolation and the version matrix are a separate plan; this plan produces the `RunSummary` type that plan will fill. Until that plan lands, `blockprobe report` reads a `results.json` produced by hand or by a fixture, which is exactly how the harness tests are meant to work.

## Global Constraints

- Python `>=3.11`. `openminion>=0.1.4,<0.2` pinned in `pyproject.toml` per PRD §13.
- Windows PowerShell and Linux are both first-class. Every test and every manual check runs on both.
- Assume 80 columns. Layouts must not require more.
- Colour is dropped when stdout is not a TTY, when `NO_COLOR` is set, or when `--no-color` is passed.
- Every user-facing string is English.
- Probe statuses are exactly `PASS`, `FLAKY`, `FAIL`, `SKIP`, `ERROR` (PRD §8).
- Exit codes: 0 = all probes PASS/SKIP/FLAKY; 1 = at least one FAIL or ERROR; 2 = usage error; 3 = budget exhausted; 4 = provider or environment unavailable. FLAKY alone exits 0.
- No emoji. Glyphs are limited to `▸` `→` `·` `─`, each with a documented ASCII fallback.
- Evidence and environment values are redacted before they are stored and before they are displayed.
- Probe ids (`P01`–`P11`) and building-block names are canonical from PRD §8. The short label is owned by the probe definition, not by the render layer.
- `building-blocks-tested.md` carries the six PRD §12 columns: Building block, Probe, Result, Pass rate, p50 latency, Evidence/note. The terminal rendering carries five of them (Evidence/note is dropped).
- `blockprobe report` never overwrites an existing `building-blocks-tested.md` unless `--force` is passed.
- Progress goes to stderr; data goes to stdout (D3).

## Review Focus

The five input classes the spec implies but no single task's tests exercise, most likely to bite first.

1. **A run with zero probes.** `results.json` with an empty `probes` list. The table must render as a valid empty table with a "0 probes" summary line, not crash and not print a stray rule.
2. **A status value the renderer does not know.** A newer probe set adds a status. The renderer must not raise; it treats an unknown status as `ERROR` and says so, rather than silently rendering nothing.
3. **A terminal narrower than the table.** A 40-column terminal. The table must not wrap into misaligned garbage — it truncates the Evidence column and, below 60 columns, prints a one-line-per-probe list instead of a table.
4. **An evidence path containing the user's home directory.** `C:\Users\dan\...` or `/home/dan/...`. It must be redacted before it reaches the terminal *and* before it reaches the Markdown file, because those files get attached to public issues.
5. **A malformed `results.json`.** Missing a required field. `blockprobe report` must fail with a clear message and exit 2 — never a traceback.

---

### Task 1: Repository skeleton and packaging

**Precondition:** the project folder is not yet a git repository. Run `git init -b main` in the project root and configure `user.name` and `user.email` before starting, because every task in this plan ends with a commit.

**Files:**
- Create: `pyproject.toml`
- Create: `Makefile`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `src/blockprobe/__init__.py`
- Create: `src/blockprobe/__main__.py`
- Create: `tests/test_package.py`

**Interfaces:**
- Consumes: nothing.
- Produces: an installable package `blockprobe` with `blockprobe.__version__` (string) and a console script `blockprobe` that runs `blockprobe.cli.main`. `src/blockprobe/__main__.py` calls `main()` and exits with its return value.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_package.py
import subprocess
import sys


def test_version_is_exported():
    import blockprobe
    assert blockprobe.__version__ == "0.1.0"


def test_module_entrypoint_exits_zero():
    result = subprocess.run(
        [sys.executable, "-m", "blockprobe", "--version"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "0.1.0" in result.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_package.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'blockprobe'`

- [ ] **Step 3: Implement the package skeleton**

`pyproject.toml` declares the package name `blockprobe`, `requires-python = ">=3.11"`, the `pydantic>=2.7,<3` dependency, a `[project.optional-dependencies] dev = ["pytest>=8"]` group, and a `src` layout so `src/blockprobe` is the package root. The `openminion` pin goes in a second extra, `probe = ["openminion>=0.1.4,<0.2"]`, so the render layer installs and tests without the SDK present — the pin still lives in `pyproject.toml` as PRD §13 requires, and `make setup` installs both extras. The console-script entry point is added in Task 8, when `blockprobe.cli` exists.

`src/blockprobe/__init__.py` sets `__version__ = "0.1.0"`.

`src/blockprobe/__main__.py` is a placeholder that Task 8 replaces:

```python
import sys

from . import __version__

if __name__ == "__main__":
    if "--version" in sys.argv:
        print(__version__)
    else:
        print("blockprobe")
```

`Makefile` provides the targets PRD §11 names: `setup`, `quick`, `full`, `matrix`, `test`, `demo`. In this plan only `setup` and `test` do real work; the others call `blockprobe` subcommands that later plans add, and their recipes are written now so the interface is fixed.

`.gitignore` ignores `runs/`, `.env`, `.venv/`, `__pycache__/`, `.pytest_cache/`, `.superpowers/`.

`.env.example` lists variable names only, no values: `OPENMINION_CONFIG_PATH`, `CORTENSOR_API_KEY`, `BLOCKPROBE_PROVIDER`, `BLOCKPROBE_MODEL`, `BLOCKPROBE_BUDGET`, `TWENTYFIRST_TOKEN`, `GITHUB_TOKEN`. The `BLOCKPROBE_*` names are BlockProbe's own; `openminion` 0.1.8 has no `OPENMINION_PROVIDER`, `OPENMINION_MODEL` or `OPENMINION_BUDGET`, and credentials are per provider (`CORTENSOR_API_KEY` for the Cortensor provider, whose default endpoint is a local router at `http://127.0.0.1:8080/api/v2/completions`).

- [ ] **Step 4: Run test to verify it passes**

Run: `pip install -e ".[dev]" && pytest tests/test_package.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml Makefile .gitignore .env.example src/blockprobe/__init__.py src/blockprobe/__main__.py tests/test_package.py
git commit -m "chore: scaffold blockprobe package and packaging"
```

---

### Task 2: Result models

**Files:**
- Create: `src/blockprobe/models.py`
- Create: `tests/test_models.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `class ProbeStatus(str, Enum)` with members `PASS`, `FLAKY`, `FAIL`, `SKIP`, `ERROR`, each equal to its uppercase name.
  - `class ProbeResult(BaseModel)` with fields: `probe_id: str`, `label: str`, `building_block: str`, `status: ProbeStatus`, `repeats: int = 1`, `passed: int = 0`, `latency_p50_s: float | None = None`, `latency_p95_s: float | None = None`, `doc_ref: str | None = None`, `evidence: list[str] = []`, `message: str | None = None`.
  - `class RunSummary(BaseModel)` with fields: `run_id: str`, `started_at: str`, `openminion_version: str = "unknown"`, `python_version: str = "unknown"`, `os_name: str = "unknown"`, `provider: str = "unknown"`, `model: str = "unknown"`, `probes: list[ProbeResult] = []`, `total_calls: int = 0`, `duration_s: float = 0.0`.
  - `class Finding(BaseModel)` with fields: `title: str`, `probe_id: str`, `building_block: str`, `severity: str`, `summary: str`, `evidence_refs: list[str] = []`, `suggested_improvement: str = ""`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_models.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'blockprobe.models'`

- [ ] **Step 3: Implement `models.py`**

Use pydantic v2 `BaseModel` for all three models, `class ProbeStatus(str, Enum)` for the status, and `Field(default_factory=list)` for the list fields so instances never share a mutable default. Add a `RunSummary.model_validate_json(text: str) -> RunSummary` convenience by inheriting the built-in classmethod — no extra code needed.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_models.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/blockprobe/models.py tests/test_models.py
git commit -m "feat: add probe result and run summary models"
```

---

### Task 3: Redaction

**Files:**
- Create: `src/blockprobe/redact.py`
- Create: `tests/test_redact.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `HOME_PLACEHOLDER = "<HOME>"`
  - `redact_text(text: str) -> str` — replaces secrets, emails and home paths in a string.
  - `redact_value(value: object) -> object` — recursive; `str` goes through `redact_text`, `dict` maps over keys and values, `list`/`tuple` map over items, everything else is returned unchanged.
  - `redact_model(model: BaseModel) -> BaseModel` — validates a copy of the model with every string field passed through `redact_text`, returning a new instance of the same class.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_redact.py
from blockprobe.models import ProbeResult, ProbeStatus
from blockprobe.redact import HOME_PLACEHOLDER, redact_text, redact_value


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_redact.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'blockprobe.redact'`

- [ ] **Step 3: Implement `redact.py`**

Compile these patterns once at module import:

| Target | Pattern | Replacement |
|---|---|---|
| OpenAI-style key | `sk-[A-Za-z0-9]{16,}` | `<KEY>` |
| Project key | `atr_[A-Za-z0-9_-]{16,}` | `<KEY>` |
| GitHub token | `gh[pousr]_[A-Za-z0-9]{20,}` | `<TOKEN>` |
| Bearer header | `Bearer\s+[A-Za-z0-9._-]{10,}` | `Bearer <TOKEN>` |
| `apiKey` assignment | `(?i)api[-_]?key["\']?\s*[:=]\s*["\']?[^"\'\s,}]+` | `apiKey=<KEY>` |
| Email | `[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}` | `<EMAIL>` |
| Windows home | `[A-Za-z]:\\Users\\[^\\\s]+` | `<HOME>` |
| POSIX home | `/home/[^/\s]+` | `<HOME>` |

Apply them in that order, home paths last so a path containing a token is redacted as a path.

`redact_model` uses `model.model_copy(deep=True)`, walks the copied model's fields, replaces every string field with its redacted form, and returns the copy. It must not mutate the original.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_redact.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add src/blockprobe/redact.py tests/test_redact.py
git commit -m "feat: add evidence and environment redaction"
```

---

### Task 4: Terminal primitives

**Files:**
- Create: `src/blockprobe/terminal.py`
- Create: `tests/test_terminal.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `GLYPHS_ASCII = {"probe": ">", "arrow": "->", "dot": "-", "rule": "-"}` and `GLYPHS_UNICODE = {"probe": "▸", "arrow": "→", "dot": "·", "rule": "─"}`.
  - `class Glyphs` with a constructor `Glyphs(ascii_mode: bool = False)` and attributes `probe`, `arrow`, `dot`, `rule`; the default instance is `GLYPHS = Glyphs()`.
  - `is_tty(stream) -> bool` — `stream.isatty()` guarded by `getattr`.
  - `colour_enabled(stream, force_off: bool = False, env: Mapping | None = None) -> bool` — false when `force_off`, false when `NO_COLOR` is set in `env` (defaulting to `os.environ`), false when the stream is not a TTY, true otherwise.
  - `terminal_width(default: int = 80) -> int` — `shutil.get_terminal_size(fallback=(default, 24)).columns`, clamped to at least 40.
  - `style(text: str, *codes: str) -> str` — wraps `text` in `"\x1b[<codes>m" ... "\x1b[0m"` joined by `;`. Returns `text` unchanged when `codes` is empty.
  - `dim(text) -> str`, `bold(text) -> str`, `green(text) -> str`, `yellow(text) -> str`, `red(text) -> str` — each a `style` call with the matching code.
  - `status_colour(status: str) -> str` — returns the ANSI code for `PASS` (32), `FLAKY` (33), `FAIL` (31), `SKIP` (90), `ERROR` (90); unknown statuses get 31.
  - `severity_colour(severity: str) -> str` — `high` 31, `medium` 33, `low` 90, anything else 31.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_terminal.py
import io
import os
import shutil

from blockprobe.terminal import (
    Glyphs, colour_enabled, status_colour, style, terminal_width,
)


class _TtyStream:
    """A stream that reports itself as a TTY, for the gating tests."""

    def __init__(self, tty: bool = True):
        self._tty = tty

    def isatty(self) -> bool:
        return self._tty


def test_colour_disabled_for_non_tty():
    assert colour_enabled(io.StringIO()) is False


def test_colour_enabled_for_tty_without_no_color():
    assert colour_enabled(_TtyStream(), env={}) is True


def test_colour_disabled_by_no_color_env():
    assert colour_enabled(_TtyStream(), env={"NO_COLOR": "1"}) is False


def test_colour_disabled_by_force_off():
    assert colour_enabled(_TtyStream(), force_off=True, env={}) is False


def test_style_wraps_with_ansi():
    assert style("PASS", "32") == "\x1b[32mPASS\x1b[0m"


def test_style_with_no_codes_is_unchanged():
    assert style("PASS") == "PASS"


def test_status_colour_mapping():
    assert status_colour("PASS") == "32"
    assert status_colour("FLAKY") == "33"
    assert status_colour("FAIL") == "31"
    assert status_colour("SKIP") == "90"
    assert status_colour("ERROR") == "90"


def test_unknown_status_is_treated_as_failure_colour():
    assert status_colour("WEIRD") == "31"


def test_ascii_glyphs_fallback():
    ascii_glyphs = Glyphs(ascii_mode=True)
    assert ascii_glyphs.rule == "-"
    assert ascii_glyphs.arrow == "->"


def test_terminal_width_has_a_floor(monkeypatch):
    monkeypatch.setattr(
        shutil, "get_terminal_size", lambda fallback=None: os.terminal_size((20, 24))
    )
    assert terminal_width() == 40
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_terminal.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'blockprobe.terminal'`

- [ ] **Step 3: Implement `terminal.py`**

No third-party dependency. The colour decision order in `colour_enabled` is: `force_off` wins, then `NO_COLOR`, then TTY. `style` accepts several codes and joins them with `;`. The `terminal_width` docstring must say the fallback applies when neither `COLUMNS` nor the OS reports a size — not whenever output is redirected.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_terminal.py -v`
Expected: PASS (10 passed)

- [ ] **Step 5: Commit**

```bash
git add src/blockprobe/terminal.py tests/test_terminal.py
git commit -m "feat: add terminal colour, width and glyph primitives"
```

---

### Task 5: Run output renderer

**Files:**
- Create: `src/blockprobe/report/__init__.py`
- Create: `src/blockprobe/report/render.py`
- Create: `tests/fixtures/results_sample.json`
- Create: `tests/test_render.py`

**Interfaces:**
- Consumes: `RunSummary`, `ProbeResult`, `ProbeStatus` from `blockprobe.models`; `style`, `status_colour`, `terminal_width`, `Glyphs` from `blockprobe.terminal`; `redact_text` from `blockprobe.redact`.
- Produces (all in `blockprobe.report.render`):
  - `STATUS_ORDER: list[str]` — `["PASS", "FLAKY", "FAIL", "SKIP", "ERROR"]`.
  - `summarise(summary: RunSummary) -> dict` — machine-readable counts: keys `pass`, `flaky`, `fail`, `skip`, `error`, `total`, `duration_s`, `total_calls`. A status string that is not one of the five known values counts as `error`. Every other function in this module is implemented in terms of this one, so the counts exist in exactly one place.
  - `render_probe_line(probe: ProbeResult, colour: bool = True) -> str` — one line, no trailing newline: `"  ▸ P01 contract        PASS    0.4s"`. Layout: two leading spaces, glyph, space, probe id, space, label padded to 16 characters, status padded to 7, then p50 latency right-aligned in 6 characters ending in `s`; when `passed` differs from `repeats` the pass-rate `n/N` follows, separated by three spaces. For `FLAKY`, `FAIL` and `ERROR` statuses a redacted, truncated `message` follows, separated by two spaces and capped at 40 characters; `PASS` and `SKIP` show no message. Design goal 2 requires the cause of a failure to be visible in the terminal, and this line is the only place it appears.
  - `render_probe_list(probe: ProbeResult, colour: bool = True) -> str` — the narrow-terminal variant: `"  ▸ P01 contract  PASS  0.4s  2/3"`, one space between fields, no padding.
  - `render_counts(summary: RunSummary) -> str` — `"4 pass · 1 flaky · 1 fail"`, built from `summarise`, omitting zero counts, in `STATUS_ORDER`.
  - `render_footer(summary: RunSummary) -> list[str]` — two lines: `"  run:  runs/<run_id>"` and `"  next: blockprobe diff runs/<a> runs/<b>"`.
  - `render_table(summary: RunSummary, colour: bool = True) -> list[str]` — the five-column table: header `Building block`, `Probe`, `Result`, `Pass`, `p50`; one row per probe; returns an empty list when there are no probes.
  - `render_run(summary: RunSummary, colour: bool = True, width: int | None = None) -> list[str]` — the full screen: one line per probe, a rule, the counts line with total duration and call count, a blank line, the table, a blank line, and the footer.

- [ ] **Step 1: Write the failing test**

```python
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
```

Create `tests/fixtures/results_sample.json` with six probes matching the design doc: `P01 contract` PASS, `P02 agent_run` PASS, `P03 tool_call` FLAKY 2/3, `P04 sessions` PASS, `P06 errors` FAIL 0/3, `P10 diagnostics` PASS. `P03` has `latency_p50_s` 3.4, `P06` 0.9, the others 0.4 / 1.8 / 2.1 / 1.2. `run_id` is `2026-10-20-1432`, `total_calls` 22, `duration_s` 9.8.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_render.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'blockprobe.report'`

- [ ] **Step 3: Implement `render.py`**

All functions take a `colour: bool = True` flag and apply colour only when it is true, so tests can assert on plain text. `render_run` picks `render_table` when the width is at least 60 and `render_probe_list` lines otherwise; the width comes from the `width` argument, and `None` means `terminal_width()`. Probe lines use `GLYPHS`, the Unicode set; the ASCII set is available only by constructing `Glyphs(ascii_mode=True)`, and no render function takes an ASCII flag in this plan.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_render.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add src/blockprobe/report/__init__.py src/blockprobe/report/render.py tests/fixtures/results_sample.json tests/test_render.py
git commit -m "feat: add run output renderer with live probe lines and results table"
```

---

### Task 6: Markdown report

**Files:**
- Create: `src/blockprobe/report/templates/building-blocks-tested.md`
- Create: `src/blockprobe/report/markdown.py`
- Create: `tests/test_markdown.py`
- Modify: `pyproject.toml` (ship the template in built distributions)

**Interfaces:**
- Consumes: `RunSummary` from `blockprobe.models`; `redact_model` from `blockprobe.redact`.
- Produces (in `blockprobe.report.markdown`):
  - `render_building_blocks_md(summary: RunSummary) -> str` — the six-column PRD §12 table, Markdown, ending with a newline.
  - `write_building_blocks_md(summary: RunSummary, out_dir: Path, force: bool = False) -> Path` — writes `building-blocks-tested.md` into `out_dir`; if the file exists and `force` is false it returns the existing path without writing; returns the path it wrote.
  - `REPORT_FILENAME = "building-blocks-tested.md"`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_markdown.py
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
    # PRD §12 puts Building block in column one, so probe rows start with the
    # block name, not the probe id; count every data row instead.
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_markdown.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'blockprobe.report.markdown'`

- [ ] **Step 3: Implement `markdown.py` and the template**

`src/blockprobe/report/templates/building-blocks-tested.md` is a plain-text template using `str.format` placeholders. Its first line is exactly `# Building Blocks Tested`, followed by a blank line, then a metadata block (openminion version, python version, os, provider, model, run id, started at), then the six-column table header row and its separator. `render_building_blocks_md` fills it and returns the complete string ending with a newline.

`write_building_blocks_md` redacts the summary with `redact_model` before rendering, checks `out_dir / REPORT_FILENAME`, and only writes when the file is absent or `force` is true.

`pyproject.toml` gains a `[tool.setuptools.package-data]` table with `"blockprobe.report" = ["templates/*.md"]`. Without it the template survives an editable install but is missing from a built wheel, so an installed BlockProbe would fail to render the report.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_markdown.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add src/blockprobe/report/templates/building-blocks-tested.md src/blockprobe/report/markdown.py tests/test_markdown.py
git commit -m "feat: add building blocks tested markdown report"
```

---

### Task 7: Doctor

**Files:**
- Create: `src/blockprobe/doctor.py`
- Create: `tests/test_doctor.py`

**Interfaces:**
- Consumes: `redact_text` from `blockprobe.redact`; `style`, `dim`, `green`, `red`, `terminal_width` from `blockprobe.terminal`.
- Produces (in `blockprobe.doctor`):
  - `class CheckResult(BaseModel)` with fields `name: str`, `value: str`, `ok: bool`, `detail: str = ""`, `next_step: str = ""`. The `next_step` is the command or action that fixes a failed check, following the convention `openminion status readiness` uses (`next: openminion setup`).
  - `class EnvironmentInfo(BaseModel)` with fields `os_name: str`, `python_version: str`, `openminion_version: str`, `install_source: str`, `provider: str`, `model: str`, `budget_calls: int | None`, `check_turn: str`, `timestamp: str`, `checks: list[CheckResult] = []`.
  - `capture_environment(probe_turn: Callable[[], str] | None = None) -> EnvironmentInfo` — gathers OS, python version, the installed `openminion` version and install source, the provider and model names from BlockProbe's own environment variables (`BLOCKPROBE_PROVIDER`, `BLOCKPROBE_MODEL`), the budget from `BLOCKPROBE_BUDGET` if set, and the `openminion doctor --check-turn --json` output summarised through `probe_turn` when that callable is supplied. Never includes a secret, and never reads `agents.json`, which carries provider credentials.

    The `BLOCKPROBE_*` names are deliberate. `openminion` 0.1.8 has no `OPENMINION_PROVIDER`, `OPENMINION_MODEL` or `OPENMINION_BUDGET` — the only `OPENMINION_PROVIDER*` names are `OPENMINION_PROVIDER_INTERFACE_STRICT` and `OPENMINION_PROVIDER_THINKING_PASSTHROUGH`. Reading them would always yield `unknown`. Provider credentials are per provider (`providers.<name>.api_key`, or the provider's `api_key_env` such as `CORTENSOR_API_KEY`), so naming the provider is BlockProbe's concern, not `openminion`'s.
  - `render_doctor(info: EnvironmentInfo, colour: bool = True) -> list[str]` — one `name  value` row per check, a blank line, and a closing verdict line `"6 checks passed · provider reachable · budget set"`.
  - `doctor_exit_code(info: EnvironmentInfo) -> int` — 0 when every check is ok, 4 when the provider or environment is unavailable.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_doctor.py
from blockprobe.doctor import (
    CheckResult, EnvironmentInfo, doctor_exit_code, render_doctor,
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


def test_exit_code_is_zero_when_all_checks_pass():
    assert doctor_exit_code(info()) == 0


def test_exit_code_is_four_when_provider_unavailable():
    assert doctor_exit_code(info(checks=[CheckResult(name="check-turn", value="unreachable", ok=False)])) == 4


def test_no_secret_appears_in_the_output():
    text = "\n".join(render_doctor(info(provider="portal/gemma-4"), colour=False))
    assert "sk-" not in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_doctor.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'blockprobe.doctor'`

- [ ] **Step 3: Implement `doctor.py`**

`capture_environment` reads the `openminion` version by importing the package and reading `__version__`, falling back to `"unknown"`. It records the install source as `pip`, `uv`, `editable` or `unknown`. Every captured value passes through `redact_text` before it is stored, so a provider string that accidentally contains a token is scrubbed.

`render_doctor` prints one row per check as `name` padded to 20 characters, then the value, with the value coloured green when the check is ok and red when it is not. When a check is not ok and `next_step` is set, the following line is `    next: <next_step>`, the same fix-hint convention `openminion status readiness` uses. The verdict line counts the passed checks and names the provider and budget state; when `budget_calls` is `None` the verdict says `budget not set` rather than `budget set`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_doctor.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/blockprobe/doctor.py tests/test_doctor.py
git commit -m "feat: add doctor command and environment capture"
```

---

### Task 8: CLI

**Files:**
- Create: `src/blockprobe/cli.py`
- Modify: `src/blockprobe/__main__.py`
- Modify: `pyproject.toml`
- Create: `tests/test_cli.py`

**Interfaces:**
- Consumes: `render_run`, `render_table`, `render_footer`, `summarise` from `blockprobe.report.render`; `render_building_blocks_md`, `write_building_blocks_md` from `blockprobe.report.markdown`; `capture_environment`, `render_doctor`, `doctor_exit_code` from `blockprobe.doctor`; `RunSummary` from `blockprobe.models`; `colour_enabled`, `terminal_width` from `blockprobe.terminal`.
- Produces:
  - `main(argv: list[str] | None = None) -> int` — the console-script entry point; returns the process exit code.
  - `USAGE_GROUPS: list[tuple[str, list[tuple[str, str]]]]` — the help grouping, each entry a group name and its `(command, description)` pairs.
  - `EXIT_OK = 0`, `EXIT_FAILURE = 1`, `EXIT_USAGE = 2`, `EXIT_BUDGET = 3`, `EXIT_ENVIRONMENT = 4`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli.py
import json
from pathlib import Path

import pytest

from blockprobe.cli import EXIT_USAGE, main

FIXTURE = Path(__file__).parent / "fixtures" / "results_sample.json"


def test_version_exits_zero(capsys):
    assert main(["--version"]) == 0
    assert "0.1.0" in capsys.readouterr().out


def test_help_groups_commands_by_task(capsys):
    assert main(["--help"]) == 0
    out = capsys.readouterr().out
    assert "probe" in out
    assert "report" in out
    assert "doctor" in out


def test_report_renders_a_results_file(capsys, tmp_path):
    result = tmp_path / "results.json"
    result.write_text(FIXTURE.read_text())
    assert main(["report", "--results", str(result)]) == 0
    out = capsys.readouterr().out
    assert "Building block" in out
    assert "P01 contract" in out


def test_report_json_emits_only_json_on_stdout(capsys, tmp_path):
    result = tmp_path / "results.json"
    result.write_text(FIXTURE.read_text())
    assert main(["report", "--results", str(result), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["run_id"] == "2026-10-20-1432"


def test_report_writes_the_markdown_file(capsys, tmp_path):
    result = tmp_path / "results.json"
    result.write_text(FIXTURE.read_text())
    assert main(["report", "--results", str(result), "--out", str(tmp_path)]) == 0
    assert (tmp_path / "building-blocks-tested.md").exists()


def test_report_md_prints_raw_markdown(capsys, tmp_path):
    result = tmp_path / "results.json"
    result.write_text(FIXTURE.read_text())
    assert main(["report", "--results", str(result), "--md"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("# Building Blocks Tested")
    assert "\x1b[" not in out


def test_missing_results_file_is_a_usage_error(capsys, tmp_path):
    assert main(["report", "--results", str(tmp_path / "nope.json")]) == EXIT_USAGE
    assert "error" in capsys.readouterr().err


def test_malformed_results_file_is_a_usage_error_not_a_traceback(capsys, tmp_path):
    result = tmp_path / "results.json"
    result.write_text("{not json")
    assert main(["report", "--results", str(result)]) == EXIT_USAGE
    err = capsys.readouterr().err
    assert "Traceback" not in err
    assert "error" in err


def test_unknown_command_is_a_usage_error(capsys):
    assert main(["nope"]) == EXIT_USAGE
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'blockprobe.cli'`

- [ ] **Step 3: Implement `cli.py`**

`argparse` with `prog="blockprobe"` and `add_subparsers(dest="command")`. Subcommands in this plan: `doctor` and `report`. `report` takes `--results <path>` (required), `--out <dir>` (optional), `--md` (print raw Markdown to stdout), `--json` (emit the run payload as JSON to stdout), `--no-color`. `doctor` takes `--json` and `--no-color`, and exits with `doctor_exit_code`.

Stream routing, per design decision D3: the rendered report, the `--json` payload and the `--md` body all go to **stdout**; error messages go to **stderr**. `--help` goes to stdout. A file that cannot be read or parsed prints `error: <what went wrong>` to stderr and returns `EXIT_USAGE` — never a traceback.

Replace `src/blockprobe/__main__.py` with the real entry point:

```python
from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
```

Add the console-script entry point to `pyproject.toml`:

```toml
[project.scripts]
blockprobe = "blockprobe.cli:main"
```

The help text is built from `USAGE_GROUPS`, listing only commands that exist in this plan: the `probe` group holds `doctor`, the `report` group holds `report`. The grouping in the design doc lists all seven PRD §11 commands; the remaining five are added by the plans that implement them.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli.py -v`
Expected: PASS (9 passed)

- [ ] **Step 5: Commit**

```bash
git add src/blockprobe/cli.py tests/test_cli.py
git commit -m "feat: add blockprobe CLI with report and doctor commands"
```

---

### Task 9: Review Focus cases and Phase 0 checks

**Files:**
- Create: `tests/test_edge_cases.py`
- Create: `FINDINGS.md`

**Interfaces:**
- Consumes: `render_run`, `render_table` from `blockprobe.report.render`; `RunSummary` from `blockprobe.models`; `main` from `blockprobe.cli`.
- Produces: no new production API. This task pins the five Review Focus behaviours and records the three Phase 0 checks in `FINDINGS.md`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_edge_cases.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_edge_cases.py -v`
Expected: FAIL — at least the empty-run and unknown-status assertions fail against the current renderer

- [ ] **Step 3: Make the renderer satisfy the cases**

In `summarise`, treat a status string that is not one of the five known values as `ERROR`. In `render_run`, when the probe list is empty print the counts line as `0 probes` and skip the table. In `render_run`, use `render_probe_list` for the per-probe lines when `width < 60`. In `render_probe_line`, pass the probe message through `redact_text` and truncate it to 40 characters before showing it, and only show it for `FLAKY`, `FAIL` and `ERROR`. In `render_probe_line`, omit the latency field entirely when `latency_p50_s` is `None`.

- [ ] **Step 4: Run the full test suite**

Run: `pytest -v`
Expected: PASS (all tests, including the nine tasks above)

- [ ] **Step 5: Write FINDINGS.md**

Create `FINDINGS.md` with a dated entry recording the three Phase 0 checks from design decision D18:

1. **Terminal glyphs** — whether `▸` `→` `·` `─` render and align in Windows PowerShell. Record the result and, if any glyph misaligns, the ASCII fallback that will be used instead.
2. **Finding-level progress** — whether the OpenMinion SDK can report findings as they are produced, or whether the analyze phase must fall back to an elapsed-time line (design decision D14).
3. **TTY detection** — whether stdout is detected as a TTY on Windows and on Linux, and that colour is dropped when piped.

Each entry states the command run, what was observed, and the conclusion. PRD §7 requires at least five entries in `FINDINGS.md` by M0; add the environment capture (OS, python version, openminion version) as two further entries so the file meets that bar.

- [ ] **Step 6: Commit**

```bash
git add tests/test_edge_cases.py FINDINGS.md
git commit -m "test: pin edge cases and record phase 0 checks in findings"
```

---

## After this plan

- **Next plan — runner and probes.** The probe runner, environment isolation (`OPENMINION_HOME` per run), the six MVP probes (P01, P02, P03, P04, P06, P10), `contracts/0.1.x.json`, and the `run` command. It produces the `RunSummary` that this plan's `report` command consumes. The `run`, `analyze`, `matrix`, `diff` and `publish` subcommands join the CLI when their plans land, completing the help grouping in design decision D9.
- **Later plans — analyst and issues.** The analyst agent, the `what-we-learned.md` note (D4, D5), the diff renderer (D6), the publish gate (D7, D8), the version matrix (D16) and the demo script (D17, D19).
