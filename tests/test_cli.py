import json
from pathlib import Path

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


def test_bare_invocation_prints_help(capsys):
    assert main([]) == 0
    out = capsys.readouterr().out
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


def test_report_out_respects_an_edited_note(capsys, tmp_path):
    result = tmp_path / "results.json"
    result.write_text(FIXTURE.read_text())
    note = tmp_path / "building-blocks-tested.md"
    note.write_text("hand edited")
    assert main(["report", "--results", str(result), "--out", str(tmp_path)]) == 0
    assert note.read_text() == "hand edited"
    assert main(["report", "--results", str(result), "--out", str(tmp_path), "--force"]) == 0
    assert "hand edited" not in note.read_text()


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


def test_doctor_json_emits_only_json_and_the_exit_code(capsys):
    assert main(["doctor", "--json"]) == 4
    payload = json.loads(capsys.readouterr().out)
    assert "checks" in payload
