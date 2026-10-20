# FINDINGS

Dated log of everything BlockProbe learns about OpenMinion, its own harness,
and the machines it runs on. Each entry records the command run, what was
observed, and the conclusion it forces. Entries F-001…F-013 are the Phase 0
research, condensed from the full evidence notes; everything else is a
harness check.

## 2026-10-20 — Environment capture (development machine)

- OS: Windows 11 (10.0.26300); Python 3.12.10; Git 2.55.0 and GNU Make
  4.4.1 installed via winget for this project.
- `openminion` is not installed in the development environment (it lives in
  the `probe` extra and in the research venv, which runs 0.1.8). BlockProbe's
  doctor correctly reports it as `unknown` with
  `next: pip install openminion>=0.1.4,<0.2` here.

## 2026-10-20 — Terminal glyphs (D18 check 1)

- Command: `python -m blockprobe report --results tests/fixtures/results_sample.json --no-color`
- Git Bash (mintty, UTF-8): `▸ → · ─` render and align correctly; the
  padded columns line up.
- Windows PowerShell 5.1 on the classic console (codepage cp1252): exit 0,
  no crash, but `▸` arrives as mojibake (`Ôû©`) because PowerShell decodes
  the child's UTF-8 bytes with the console codepage. Alignment is unaffected
  (padding is by character count).
- Conclusion: the Unicode glyph set is safe on UTF-8 terminals; classic
  PowerShell needs a decision before the demo — set the console output
  codepage to 65001 from `main`, add an `--ascii` switch, or document a
  UTF-8 console requirement. Tracked in the plan ledger.

## 2026-10-20 — TTY detection and colour gating (D18 check 3)

- Command: `python -m blockprobe report --results tests/fixtures/results_sample.json | grep -c $'\033'` → `0`.
- Observed: piped stdout reports `isatty() == False`, no ANSI escapes are
  emitted, and `NO_COLOR` is honoured (unit-pinned, decision order
  `force_off` → `NO_COLOR` → TTY).
- Linux: not yet run locally (no Linux environment); the CI matrix
  (ubuntu-latest × py3.11/3.12) covers it from Task 8's CI onward.
- Conclusion: the D3 routing (data on stdout, colour only on a TTY) holds on
  Windows.

## 2026-10-20 — Finding-level progress (D18 check 2)

- Verified against the installed SDK (see F-007): `Agent.run_stream()` and
  `APIRuntime.submit_turn()` yield `TurnChunk` progress events in 0.1.8.
- Conclusion: the analyze phase can stream analyst progress as findings are
  drafted, instead of falling back to a bare elapsed-time line (D14). The
  structured `Findings` validation still happens at turn end, because Pydantic
  output validation is a final-step contract.

## 2026-10-20 — Phase 0 research (F-001…F-013)

### F-001 — The latest release is 0.1.8, not 0.1.4

PyPI lists 0.1.8 down to 0.1.0 plus a long 0.0.x tail; four releases shipped
since the PRD was written. The pin `openminion>=0.1.4,<0.2` still holds.

### F-002 — The P06 bug was real, and upstream says it is fixed

`API_COMPATIBILITY.md`: after the retry budget is exhausted, `Agent.run()`
raises public `ProviderError` for recognized provider failures, "corrects
0.1.4 behavior that could return an error message as a completed answer."
A 0.1.4 vs 0.1.8 diff should show P06 FAIL → PASS — the strongest material
for the bug-fix bonus. Check the upstream issue tracker before filing
anything.

### F-003 — `openminion` uses a lazy `__getattr__`, so `dir()` lies

`dir(openminion)` on 0.1.8 shows none of the twelve documented root exports,
but every documented name resolves through `getattr`. A public-contract
probe built on `dir()` would report a false failure — P01 must use
`getattr`, never `dir()`.

### F-004 — `doctor --check-turn --json` fails without a config file

On a clean machine: `config file not found: .../.openminion/agents.json`.
Until `openminion setup` runs, the check-turn row must be reported as a
blocked check with `next: openminion setup`, not an error.

### F-005 — `openminion status readiness` is the model for BlockProbe's doctor

Works with no config and no credential. Rows carry a small state vocabulary
(`available` / `blocked` / `not_configured`), a blocked row states the cause
and the next command, and an available row can still carry a caveat.

### F-006 — No issue template in the upstream repository

`github.com/openminion/openminion` has no `ISSUE_TEMPLATE`. The hackathon
bug template in PRD §12 stands on its own.

### F-007 — Confirmed SDK signatures for the probes

Resolved from the installed package: `Agent(*, instructions=None,
output_type=None, ..., forced_tools=None, handoffs=None, session_id=None,
...)`; `Handoff(target, name=None, description=None)` takes a live `Agent`;
forcing a tool call is `Agent(forced_tools=[...])`; `RuntimeTurnHandle` and
`TurnChunk` live in `openminion.api`, not the root namespace.

### F-008 — Documented behaviour confirms three probe assertions

`TurnTimeoutError` has `__since__` 0.1.5 (on 0.1.4 probes must treat it as
absent, not failing); `resolve_approval()` accepts only `allow_once` and
`deny`; prose-wrapped JSON remains accepted during 0.1.x, so P11 records it
rather than judging it.

### F-009 — Isolation mechanism and the `examples/sdk/` files

`openminion --help` exposes `--home-root`, `--data-root`, `--generated-root`
as global options — the per-run isolation mechanism FR-02 needs.
`examples/sdk/` contains the reference implementations for probes P02–P11.

### F-010 — The `openminion` CLI surface is much larger than the PRD assumes

46 subcommand groups, 21 documented console scripts plus `openminion mcp`.
P01's "documented console scripts exist" should check the 21 scripts named in
`API_COMPATIBILITY.md`, and a stretch probe over `openminion mcp` is more
valuable than the PRD's "P14 rooms" guess.

### F-011 — The isolation variables are exactly as PRD FR-02 names them

`OPENMINION_HOME`, `OPENMINION_DATA_ROOT`, `OPENMINION_GENERATED_ROOT` are
read by the runtime, also exposed as CLI options. Also surfaced:
`OPENMINION_CONFIG_PATH`, `OPENMINION_WORKSPACE`, `OPENMINION_POLICY_PATH`,
`OPENMINION_TURN_TIMEOUT_SECONDS`, and trace/debug variables that are
candidate evidence sources.

### F-012 — The echo provider is set up with `openminion config init --provider echo`

The echo provider is first-class, selectable at config-init time. Harness
tests should run `config init --provider echo` inside each isolated home and
exercise the real SDK — a materially stronger claim than mocking.

### F-013 — The Cortensor provider is first-class, default model `gpt-oss-20b`

Seven provider configs ship in 0.1.8; Cortensor has a dedicated 26-field
config: `api_key_env = CORTENSOR_API_KEY`, default endpoint a local router at
`http://127.0.0.1:8080/api/v2/completions`, `timeout_seconds = 420`, default
model `gpt-oss-20b` — not Gemma 4. Consequences: the demo needs a local
Cortensor router running; a dead router is `ERROR`, not `FAIL`; long timeouts
must be driven down via `OPENMINION_TURN_TIMEOUT_SECONDS`; the PRD's
"Portal / Gemma4" assumption needs confirming with the organisers.
