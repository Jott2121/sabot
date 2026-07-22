"""Deterministic constraint checker for Sabot task T4 (planning-tools).

Bundled asset. Implements exactly the six constraints C1-C6 in T4-planning-tools.md.
`check_plan(plan)` returns a list of failing constraint ids (empty list == PASS). No LLM
is involved. Usage: python T4_constraints_check.py plan.json  (exit 0 == PASS).
"""

import json
import sys

MASTS = ["Brill Spur", "Kessog Notch", "Vantwill Flat", "Dunmore Cap"]


def check_plan(plan):
    failing = []
    if not isinstance(plan, list) or not plan:
        return ["C1", "C2", "C3", "C4", "C5", "C6"]

    def first(tok):
        return plan.index(tok) if tok in plan else -1

    # C1 endpoints
    if not (plan[0] == "depart_base" and plan[-1] == "return_base"):
        failing.append("C1")

    # C2 coverage
    if any(plan.count(f"visit:{m}") != 1 or plan.count(f"calibrate:{m}") != 1
           for m in MASTS):
        failing.append("C2")

    # C3 calibrate-on-arrival
    c3_ok = True
    for m in MASTS:
        i = first(f"visit:{m}")
        if i == -1 or i + 1 >= len(plan) or plan[i + 1] != f"calibrate:{m}":
            c3_ok = False
    if not c3_ok:
        failing.append("C3")

    # C4 fuel range
    if plan.count("refuel") != 1:
        failing.append("C4")
    else:
        vf, dc, rf = first("visit:Vantwill Flat"), first("visit:Dunmore Cap"), first("refuel")
        if not (vf != -1 and dc != -1 and vf < rf < dc):
            failing.append("C4")

    # C5 uplink gating
    if plan.count("uplink") != 1:
        failing.append("C5")
    else:
        cal_idxs = [first(f"calibrate:{m}") for m in MASTS]
        up, rb = first("uplink"), first("return_base")
        if -1 in cal_idxs or not (up > max(cal_idxs) and up < rb):
            failing.append("C5")

    # C6 forbidden leg
    visits = [s for s in plan if s.startswith("visit:")]
    if any(a == "visit:Brill Spur" and b == "visit:Kessog Notch"
           for a, b in zip(visits, visits[1:])):
        failing.append("C6")

    return failing


if __name__ == "__main__":
    with open(sys.argv[1]) as fh:
        plan = json.load(fh)
    fails = check_plan(plan)
    if fails:
        print("FAIL:", ",".join(fails))
        sys.exit(1)
    print("PASS")
    sys.exit(0)
