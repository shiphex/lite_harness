from tools.powershell import run_powershell
from pathlib import Path


def test_run_powershell():
    result = run_powershell("$PWD.Path")
    assert result != ""
    assert Path(result.strip()).resolve() == Path.cwd().resolve()
