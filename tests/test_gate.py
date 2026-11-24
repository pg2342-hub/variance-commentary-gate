"""The eval itself: the gated drafter must pass the gate and the payee pivot must not."""

from pathlib import Path

from golive_gate.cli import main

CONFIG = str(Path(__file__).resolve().parents[1] / "eval" / "golive.yml")


def test_gated_drafter_is_go(tmp_path):
    assert main(["run", CONFIG, "--out", str(tmp_path)]) == 0


def test_pivot_is_no_go(tmp_path):
    assert main(["run", CONFIG, "--agent", "agent:pivot_drafter", "--out", str(tmp_path)]) != 0
