from __future__ import annotations

import pytest

from ahead_rev_sim._version import __version__
from ahead_rev_sim.cli import main as core_main
from ahead_rev_sim.debugger_cli import main as debugger_main
from ahead_rev_sim.history_cli import main as history_main
from ahead_rev_sim.memory_cli import main as memory_main


@pytest.mark.parametrize(
    ("command", "program"),
    (
        (debugger_main, "ahead-rev-debug"),
        (history_main, "ahead-rev-history"),
        (memory_main, "ahead-rev-memory"),
    ),
)
def test_legacy_demo_wrappers_honor_help_without_running_demo(
    command,
    program: str,
    capsys,
) -> None:
    with pytest.raises(SystemExit) as exc:
        command(["--help"])
    assert exc.value.code == 0
    output = capsys.readouterr().out
    assert f"usage: {program}" in output
    assert "CORRUPTION SOURCE" not in output
    assert "HISTORY BUFFER ANALYSIS" not in output
    assert "REXCH ROUND-TRIP" not in output


@pytest.mark.parametrize(
    ("command", "program"),
    (
        (core_main, "ahead-rev-sim"),
        (debugger_main, "ahead-rev-debug"),
        (history_main, "ahead-rev-history"),
        (memory_main, "ahead-rev-memory"),
    ),
)
def test_primary_and_demo_clis_report_the_release_version(
    command,
    program: str,
    capsys,
) -> None:
    with pytest.raises(SystemExit) as exc:
        command(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == f"{program} {__version__}"
