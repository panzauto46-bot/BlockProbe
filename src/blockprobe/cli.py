"""The blockprobe command surface.

Owns argument parsing, stream routing and exit codes. Data commands write
to stdout, errors and diagnostics to stderr, and a failed invocation never
ends in a traceback. The help text is built from :data:`USAGE_GROUPS` so
the grouping lands in exactly one place.
"""

import argparse
import sys
from pathlib import Path
from typing import cast

from blockprobe import __version__
from blockprobe.doctor import capture_environment, doctor_exit_code, render_doctor
from blockprobe.models import RunSummary
from blockprobe.redact import redact_model
from blockprobe.report.markdown import (
    render_building_blocks_md, write_building_blocks_md,
)
from blockprobe.report.render import render_run
from blockprobe.terminal import colour_enabled

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_USAGE = 2
EXIT_BUDGET = 3
EXIT_ENVIRONMENT = 4

USAGE_GROUPS = [
    ("probe", [("doctor", "check environment, provider and budget before a run")]),
    ("report", [("report", "re-render a saved run to the terminal or Markdown")]),
]


def main(argv: list[str] | None = None) -> int:
    """Run the blockprobe CLI and return the process exit code."""
    # Windows consoles default to a legacy codepage that cannot encode the
    # Unicode glyph set; UTF-8 stdio keeps the renderer from crashing on '▸'.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")

    if argv is None:
        argv = sys.argv[1:]
    if "--version" in argv:
        print(f"blockprobe {__version__}")
        return EXIT_OK

    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        # argparse exits 0 for --help and 2 for usage errors; both are
        # return values here, the console script re-raises via SystemExit.
        return int(exc.code or 0)

    if args.command is None:
        parser.print_help()
        return EXIT_OK
    if args.command == "doctor":
        return _cmd_doctor(args)
    return _cmd_report(args)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="blockprobe",
        description="Probe OpenMinion's building blocks and report the results.",
        epilog=_usage_text(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command")

    doctor = subparsers.add_parser("doctor", help="check the environment before a run")
    doctor.add_argument("--json", action="store_true", help="emit the environment as JSON")
    doctor.add_argument("--no-color", action="store_true", help="disable ANSI colour")

    report = subparsers.add_parser("report", help="re-render a saved run")
    report.add_argument("--results", required=True, type=Path, help="path to results.json")
    report.add_argument("--out", type=Path, help="also write building-blocks-tested.md here")
    report.add_argument("--md", action="store_true", help="print raw Markdown to stdout")
    report.add_argument("--json", action="store_true", help="emit the run payload as JSON")
    report.add_argument("--force", action="store_true", help="overwrite an edited note")
    report.add_argument("--no-color", action="store_true", help="disable ANSI colour")
    return parser


def _usage_text() -> str:
    lines = ["commands:"]
    for group, commands in USAGE_GROUPS:
        lines.append(f"  {group}")
        for name, description in commands:
            lines.append(f"    {name:<12} {description}")
    return "\n".join(lines)


def _cmd_report(args: argparse.Namespace) -> int:
    try:
        text = args.results.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"error: cannot read {args.results}: {exc.strerror or exc}", file=sys.stderr)
        return EXIT_USAGE
    try:
        summary = RunSummary.model_validate_json(text)
    except ValueError as exc:
        print(f"error: {args.results} is not a valid results file: {exc}", file=sys.stderr)
        return EXIT_USAGE

    if args.json:
        print(summary.model_dump_json(indent=2))
        return EXIT_OK
    if args.md:
        redacted = cast(RunSummary, redact_model(summary))
        sys.stdout.write(render_building_blocks_md(redacted))
        return EXIT_OK

    colour = colour_enabled(sys.stdout, force_off=args.no_color)
    for line in render_run(summary, colour=colour):
        print(line)
    if args.out is not None:
        write_building_blocks_md(summary, args.out, force=args.force)
    return EXIT_OK


def _cmd_doctor(args: argparse.Namespace) -> int:
    info = capture_environment()
    if args.json:
        print(info.model_dump_json(indent=2))
    else:
        colour = colour_enabled(sys.stdout, force_off=args.no_color)
        for line in render_doctor(info, colour=colour):
            print(line)
    return doctor_exit_code(info)


if __name__ == "__main__":
    raise SystemExit(main())
