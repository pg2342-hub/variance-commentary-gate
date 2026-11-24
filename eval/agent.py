"""The two drafters the gate compares, called with each case's scenario."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vcg.baseline import pivot_draft  # noqa: E402
from vcg.core import draft  # noqa: E402
from vcg.data import build  # noqa: E402


def _truth(close):
    t = dict(close.truth)
    return t


def gated_drafter(scenario: dict) -> dict:
    """Data checks, tie-out, driver per variance, and holds for FP&A."""
    close = build(scenario)
    return draft(close) | {"truth": _truth(close)}


def pivot_drafter(scenario: dict) -> dict:
    """A spreadsheet pivot by payee that sends everything it drafts."""
    close = build(scenario)
    return pivot_draft(close) | {"truth": _truth(close)}
