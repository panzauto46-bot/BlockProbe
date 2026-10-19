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
