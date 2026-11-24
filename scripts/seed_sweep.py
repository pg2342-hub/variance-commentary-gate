"""Run the 25 cases on seeds they were not written with, so the cases are not tuned to their data.

python scripts/seed_sweep.py        # exits 1 below 95%
"""

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval"))

from agent import gated_drafter  # noqa: E402
from checks import checks  # noqa: E402
from golive_gate.cases import Case  # noqa: E402

SEEDS = [1, 2, 3, 5, 8, 21, 34]


def main() -> int:
    cases = yaml.safe_load((ROOT / "eval" / "cases.yml").read_text())["cases"]
    passed = total = 0
    misses = []
    for seed in SEEDS:
        for c in cases:
            scen = dict(c["input"], seed=seed)
            case = Case(id=c["id"], group=c["group"], title=c["title"], input=scen, expected=c.get("expected") or {})
            out = gated_drafter(scen)
            ok = all(ch.run(case, out).result != "fail" for ch in checks)
            passed += ok
            total += 1
            if not ok:
                misses.append(f"{c['id']}@{seed}")
    print(f"{passed} of {total} cases pass on seeds {SEEDS}")
    if misses:
        print("misses:", ", ".join(misses))
    return 0 if passed / total >= 0.95 else 1


if __name__ == "__main__":
    raise SystemExit(main())
