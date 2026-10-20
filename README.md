# BlockProbe

**A canary for OpenMinion upgrades.** BlockProbe probes OpenMinion's building
blocks against a real model, records what happened, and turns the results into
a report you can compare across versions and a bug report that is ready to
file.

`Python 3.11+` · `Pre-alpha` · `Windows and Linux`

---

## Why

OpenMinion ships almost weekly. A version bump can silently change how an agent,
a tool call, a session or a provider error behaves, and a builder has no quick
way to find out which of those changes matters to them. Re-testing by hand is
slow, inconsistent, and produces reports that are hard to compare.

BlockProbe makes the check repeatable: one command runs a documented probe
suite against a real model, classifies every non-pass, and writes both a
machine-readable result and a human-readable report.

## What it does

- **Probes documented behaviour.** Each probe asserts something OpenMinion's
  documentation promises — a callback fires, an exception is raised, an id is
  preserved — and records the document it verifies. A failure is a bug or a
  documentation gap, never a matter of taste.
- **Classifies every non-pass.** `FAIL` is a product failure, `FLAKY` is a pass
  rate between zero and one, `ERROR` is a problem in the harness itself, and
  `SKIP` means the feature does not exist in that version. Only product
  failures become bug drafts.
- **Redacts before it stores anything.** API keys, tokens, email addresses and
  user home paths are removed from evidence before it reaches a file or a
  model.
- **Compares runs.** The same suite on two OpenMinion versions, or two
  providers, produces a diff of regressions, fixes, pass rate and latency.

## How it works

```text
doctor  ->  run  ->  analyze  ->  report
```

| Step | What happens |
|---|---|
| `doctor` | Captures the OS, Python and OpenMinion versions, the provider and model, and whether a turn can actually be executed. |
| `run` | Executes each probe in an isolated OpenMinion home, with repeats, timeouts and a model-call budget. Writes `runs/<id>/results.json`. |
| `analyze` | An OpenMinion agent reads the results and writes structured findings, each tied to an evidence reference. It never changes a probe's status. |
| `report` | Renders `building-blocks-tested.md` from a results file. `diff` compares two runs. |

## Status

BlockProbe is in active development. This table records what exists today, not
what is planned.

| Area | State |
|---|---|
| Packaging, Makefile, test harness | Done |
| Result models (`ProbeResult`, `RunSummary`, `Finding`) | Done |
| Redaction of keys, tokens, emails and home paths | Done |
| Terminal rendering and the Markdown report | In progress |
| `doctor` and the CLI entry point | In progress |
| Probe runner, isolation and budget | Next |
| Probes P01–P11 | Next |
| Analyst agent, diff, matrix, publish gate | Later |

The probe runner is the next milestone. Until it lands, the `run`, `analyze`,
`matrix`, `diff` and `publish` commands do not exist yet, and `make quick`,
`make full`, `make matrix` and `make demo` will fail — they call those
commands.

## Quickstart

Requires Python 3.11 or newer and Git.

```bash
git clone https://github.com/panzauto46-bot/BlockProbe.git
cd BlockProbe
python -m venv .venv
```

Activate the virtual environment:

```powershell
# Windows PowerShell
.venv\Scripts\Activate.ps1
```

```bash
# Linux and macOS
source .venv/bin/activate
```

Install the package and run the test suite:

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python -m blockprobe --version
```

The test suite needs no provider credential and no network access. `make test`
runs the same suite with verbose output.

## Repository layout

```text
src/blockprobe/
├── __init__.py        package version
├── __main__.py        python -m blockprobe
├── models.py          ProbeStatus, ProbeResult, RunSummary, Finding
└── redact.py          evidence and environment redaction

tests/                 pytest suite; no network, no credentials
docs/superpowers/
├── specs/             approved design decisions
└── plans/             implementation plans
Makefile               setup | quick | full | matrix | test | demo
pyproject.toml         packaging, dependencies, pytest configuration
```

`runner.py`, `probes/`, `report/` and `agents/` arrive with the runner and
analyst plans.

## Documentation

- [`PRD.md`](PRD.md) — requirements, probe catalog and report formats.
- [`ROADMAP.md`](ROADMAP.md) — phases, milestones and the scope-cut order.
- [`docs/superpowers/specs/`](docs/superpowers/specs) — CLI UX design.
- [`docs/superpowers/plans/`](docs/superpowers/plans) — implementation plans.

## Design principles

1. **Evidence over opinion.** A probe asserts only what the documentation
   promises, and names the document it verifies.
2. **Harness errors are not product failures.** A broken harness reports
   `ERROR`, so a broken test never becomes a false bug report.
3. **Nothing leaves the machine by accident.** Redaction happens before storage
   and before model input; publishing is manual and requires typed
   confirmation.

## Contributing

Issues and pull requests are welcome. Before opening a pull request:

```bash
python -m pytest -q
```

Keep credentials out of the repository. A run redacts its own evidence, but
never paste a live key into an issue.
