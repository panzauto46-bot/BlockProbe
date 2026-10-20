# BlockProbe — Roadmap

**Window:** Mon 19 Oct → Sat 19 Dec 2026 (all dates WIB)
**Hard deadline:** Sat 19 Dec, 14:59 WIB (= 18 Dec, Pacific Time)
**Internal target:** submit on Wed 16 Dec
**Assumption:** one builder, roughly 10–15 hours a week. Tick the boxes weekly. If a phase slips, apply the scope-cut order below instead of moving the deadline.

## At a glance

| Phase | Dates | Goal | Exit milestone |
|---|---|---|---|
| 0 · Kickoff and setup | Mon 19 – Sun 25 Oct | Registered, installed, first real-model run, repo skeleton | **M0** Sun 25 Oct |
| 1 · MVP harness | Mon 26 Oct – Sun 8 Nov | `blockprobe run --profile quick` with 6 probes and a report | **M1** Sun 8 Nov |
| 2 · Analyst and full probes | Mon 9 – Sun 22 Nov | 11 probes, analyst agent, version diff | **M2** Sun 22 Nov |
| 3 · Issues, gate, providers | Mon 23 Nov – Sun 6 Dec | Bug drafts, approval gate, provider comparison, feature freeze | **M3** Sun 6 Dec |
| 4 · Polish and demo | Mon 7 – Sun 13 Dec | README, notes, clean-machine test, video, docs freeze | **M4** Sun 13 Dec |
| 5 · Submit and buffer | Mon 14 – Sat 19 Dec | PR and DoraHacks submission, buffer | **M5** Wed 16 Dec |

## Progress log

- **2026-10-20 —** Repository is public with a README, MIT licence and three diagrams; the CLI UX spec and a 9-task plan for the CLI surface and report layer are approved. `models.py`, `redact.py`, `terminal.py` and `report/render.py` are on `feat/cli-surface` with tests.
- **2026-10-20 —** Phase 0 research recorded: OpenMinion 0.1.8 is the latest release, the provider-error defect was fixed upstream after 0.1.4, and Cortensor is a first-class provider.
- **2026-10-20 —** Task 6 shipped on `feat/cli-surface`: the `building-blocks-tested.md` renderer with redaction and no-clobber `--force` semantics, template included in built wheels; 39 tests green. Remaining on this branch: doctor, CLI wiring, edge cases and `FINDINGS.md`.
- **2026-10-20 —** Task 7 shipped: `doctor.py` with the six-check environment capture (`BLOCKPROBE_*` names, redaction at capture, blocked rows carry `next:` fix hints), renderer and exit-code policy; 46 tests green. Remaining on this branch: CLI wiring, edge cases and `FINDINGS.md`.
- **2026-10-20 —** Task 8 shipped: the `blockprobe` CLI — `doctor` and `report` subcommands wired to the real modules, console script, UTF-8 stdio so legacy Windows consoles survive the Unicode glyphs; 12 CLI tests, 58 green. Remaining on this branch: edge cases and `FINDINGS.md`.
- **2026-10-20 —** Task 9 shipped: the five review-focus edge cases are pinned (only the empty run needed a renderer change — the counts line now says `0 probes`), `.env.example` carries the verified `BLOCKPROBE_*`/`CORTENSOR_API_KEY` names, and `FINDINGS.md` opens with the three D18 checks plus the condensed F-001…F-013 research; 63 tests green. **The CLI surface and report layer plan is complete** (tasks 1–9).
- **2026-10-20 —** CI committed: GitHub Actions runs the 63-test suite with `-W error` on Ubuntu and Windows across Python 3.11 and 3.12, on pushes to `main` / `feat/cli-surface` and on pull requests. Echo-provider harness lanes land with the runner plan.
- **Blocked —** The real-model run waits on a provider credential.

---

## Phase 0 — Kickoff and setup (Mon 19 – Sun 25 Oct)

- [ ] Register on DoraHacks and join the Cortensor Discord.
- [ ] Ask in Discord: the Hackathon #5 repository URL, whether "Submit Build" on DoraHacks is also required, and how to get Portal / Gemma4 access.
- [ ] Fork and star `openminion/openminion`; follow OpenMinion and Cortensor on GitHub and X.
- [ ] Install `openminion` in a clean virtual environment (Python 3.11+); pick a real provider and model; set a spend cap.
- [ ] Run `openminion doctor --check-turn --json`, the starter quickstart, and `examples/sdk/submitted_stream.py` on the real provider.
- [x] Start `FINDINGS.md` with the first command and log every rough edge: docs gaps, confusing errors, Windows issues.
- [ ] Read `API_COMPATIBILITY.md`, `docs/runtime-surfaces.md` and `examples/sdk/`; answer the open questions in PRD section 17.
- [x] Create the `blockprobe` repo with the skeleton from PRD section 11 (pyproject, Makefile, CI on the echo provider).

**M0 (Sun 25 Oct):** one real-model run recorded, at least 5 entries in `FINDINGS.md`, repo skeleton pushed.

## Phase 1 — MVP harness (Mon 26 Oct – Sun 8 Nov)

- [ ] Result models, runner (repeats, timeout, call budget, per-probe isolation).
- [ ] Environment capture and isolated `OPENMINION_*` directories per run.
- [ ] Probes P01 contract, P02 agent run, P03 tool calling, P04 sessions, P06 errors, P10 diagnostics.
- [ ] `contracts/0.1.x.json` built from `API_COMPATIBILITY.md`.
- [x] Redaction module with tests.
- [ ] Report renderer: `results.json` and `building-blocks-tested.md`.
- [ ] Harness tests on the echo provider (no credentials).
- [ ] README v0: setup and run.

**M1 (Sun 8 Nov):** `blockprobe run --profile quick` on a clean virtual environment produces the report with 6 probes on a real model in 10 minutes or less.

## Phase 2 — Analyst and full probes (Mon 9 – Sun 22 Nov)

- [ ] Probes P05 streaming and cancel, P07 memory, P08 permissions and approvals, P09 delegation, P11 structured output.
- [ ] Analyst agent: tools, structured findings, evidence-ref validator, `approval_callback` write policy.
- [ ] `blockprobe diff` for two runs; baselines per version.
- [ ] `blockprobe matrix` with per-version virtual environments.
- [ ] Check existing OpenMinion issues; **by Fri 20 Nov** file the first genuine, reproducible bug (if any) so the team has time to acknowledge it for the bug-fix bonus.

**M2 (Sun 22 Nov):** 11 probes, the analyst writes What We Learned with valid evidence refs, and at least 2 OpenMinion versions are compared.

## Phase 3 — Issues, gate, providers (Mon 23 Nov – Sun 6 Dec)

- [ ] Issue drafter and `--delegate` mode with fallback to inline drafting.
- [ ] Approval gate: `publish` needs typed confirmation; private-note routing for suspected security issues.
- [ ] Provider profiles. If Portal / Gemma4 access is granted, run P02–P05 there and record latency and pass-rate against the default provider.
- [ ] Reliability stats: raise repeats to 5 for FLAKY probes.
- [ ] Bug-bonus track: for an acknowledged bug, make a substantive fix PR attempt.
- [ ] **Feature freeze Sun 6 Dec.**

**M3 (Sun 6 Dec):** at least 1 reproducible finding documented in the bug template, and a reliability table for at least 1 provider.

## Phase 4 — Polish and demo (Mon 7 – Sun 13 Dec)

- [ ] README final: setup, run, "How BlockProbe uses the SDK" table, architecture diagram.
- [ ] Commit `examples/sample-run/` from a real run.
- [ ] Clean-machine reproduction test (fresh virtual environment on Windows PowerShell, plus Linux or WSL if possible); time it.
- [ ] Final Building Blocks Tested and What We Learned notes: edit the generated drafts by hand and add what the tool cannot see.
- [ ] Write `docs/demo-script.md` from PRD Appendix A, then record the 1–5 minute demo (re-record if needed).
- [ ] **Docs freeze Sun 13 Dec.**

**M4 (Sun 13 Dec):** README, both notes and the video are final.

## Phase 5 — Submit and buffer (Mon 14 – Sat 19 Dec)

- [ ] Mon 14 – Tue 15 Dec: last pass; re-run on the latest OpenMinion release and pin the exact version in the README.
- [ ] **Wed 16 Dec: open the PR to the Hackathon #5 repository**, submit on DoraHacks if required, and verify every link opens while logged out.
- [ ] Thu 17 – Fri 18 Dec: buffer for requested fixes.
- [ ] Sat 19 Dec, 14:59 WIB: hard stop.

**M5 (Wed 16 Dec):** submitted.

---

## Scope-cut order (if behind)

Cut in this order, and never touch the last line.

1. HTML report and GitHub Action (FR-17)
2. Memory mode (FR-16)
3. Delegation mode (FR-15)
4. Provider comparison (FR-14), unless Portal / Gemma4 access is already working
5. Stretch probes P12–P15
6. **Never cut:** probes P01–P04, P06, P10; the analyst agent; report and diff; README; demo; both notes.

## Weekly rhythm

- **Monday:** re-run the canary on the newest OpenMinion release; log what changed in `FINDINGS.md`.
- **Friday:** 15-minute review against the milestone; tick this file; decide whether to apply a scope cut.

## External dependencies and watch list

| Item | Status | When to check |
|---|---|---|
| Hackathon #5 repository URL | Not in the details received; announced "before kickoff" | Week 1, then weekly |
| DoraHacks "Submit Build" also required? | Unknown | Week 1 |
| Portal / Gemma4 access | TBD, coordinated through Discord | Ask in week 1; design must not depend on it |
| Team acknowledgement of a bug (for the bonus) | Needed before a fix PR | File the issue by Fri 20 Nov |
| OpenMinion release cadence | Five releases in 8 days (0.1.0 to 0.1.4) | Every Monday |
| Provider spend | Set a cap in week 0 | Weekly |

## Stretch backlog (only if ahead of plan)

- HTML report with panels for the demo
- GitHub Action: nightly canary on new OpenMinion releases
- P12 local HTTP API and daemon, P13 skills, P14 rooms, MCP / A2A probes
- Capture OpenTelemetry traces as extra evidence
- Package the issue-drafting procedure as an OpenMinion skill

## Definition of done (submission)

- [ ] Public repo with README: setup, run, SDK workflow explanation
- [ ] One working example (`examples/sample-run/`) and a 1–5 minute demo video
- [ ] Building Blocks Tested note (what worked, what did not)
- [ ] What We Learned note (actionable product feedback)
- [ ] Any bug reported with steps, expected/actual behaviour and safe evidence; security-sensitive findings sent privately
- [ ] Bonus, if earned: linked bug report and substantive fix PR
- [ ] PR to the Hackathon #5 repository, and a submission on DoraHacks if required
