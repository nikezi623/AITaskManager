"""Tests for tools/atm_state.py's merge -- the Python mirror of docs/js/merge.js.

    python tests/test_merge.py

Runs the SAME fixtures as the JS runner (tests/merge_cases.json). If the two
implementations ever disagree, this goes red instead of the two devices
silently diverging.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))

from atm_state import (  # noqa: E402
    SCHEMA, apply_checkin, checked_dates, empty_state, is_checked,
    live_records, merge_cell, merge_states, next_stamp, normalize_state,
    pick_record, prune_tombstones, stable_stringify, touch_record,
)

passed = 0
failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    global passed
    if condition:
        passed += 1
    else:
        failures.append(f"{name}\n    {detail}" if detail else name)


def eq(name: str, actual, expected) -> None:
    a, b = stable_stringify(actual), stable_stringify(expected)
    check(name, a == b, f"expected {b}\n    actual   {a}")


# ── 1. Fixture cases (shared with the JS runner) ──────────────────────────

cases = json.loads((HERE / "merge_cases.json").read_text(encoding="utf-8"))["cases"]
for case in cases:
    eq(f"fixture: {case['name']}",
       merge_states(case["base"], case["incoming"]),
       normalize_state(case["expected"]))

# ── 2. Structural guarantees ─────────────────────────────────────────────

OUT_KEYS = sorted(["schema", "habits", "groups", "checkins", "meta"])
out = merge_states({"habits": {"a": {"id": "a", "updatedAt": 1, "writer": "x"}}}, {})
eq("shape: merge output always has exactly the five top-level keys",
   sorted(out.keys()), OUT_KEYS)
check("shape: schema version is set on merge output", out["schema"] == SCHEMA)
eq("shape: garbage normalizes to an empty state",
   normalize_state({"habits": "nope", "checkins": [1, 2], "meta": "x"}), empty_state())

# ── 3. Randomized property tests ─────────────────────────────────────────

STAMPS = [500, 1000, 2000, 3000, -500, -1000, -2000, -3000]
WRITERS = ["pc", "phone", "migrate"]
DATES = ["2026-09-14", "2026-09-15", "2026-09-16", "2026-09-17"]
IDS = ["h1", "h2", "h3", "g1", "g2"]


def random_state(rnd: random.Random) -> dict:
    state = empty_state()
    for ident in IDS:
        if rnd.random() < 0.6:
            table = "groups" if ident.startswith("g") else "habits"
            state[table][ident] = {
                "id": ident,
                "name": f"{table}-{ident}-{rnd.randrange(3)}",
                "order": rnd.randrange(3) * 10,
                "updatedAt": 1000 + rnd.randrange(3) * 1000,
                "writer": rnd.choice(WRITERS),
                "deleted": rnd.random() < 0.2,
            }
    for ident in ["h1", "h2", "h3"]:
        if rnd.random() < 0.75:
            state["checkins"][ident] = {
                d: rnd.choice(STAMPS) for d in DATES if rnd.random() < 0.5
            }
    if rnd.random() < 0.5:
        state["meta"] = {
            "bot_enabled": rnd.random() < 0.5,
            "updatedAt": 1000 + rnd.randrange(3) * 1000,
            "writer": rnd.choice(WRITERS),
        }
    return state


ROUNDS = 4000
bad_idem = bad_comm = bad_assoc = 0
for i in range(ROUNDS):
    rnd = random.Random(i)
    a, b, c = random_state(rnd), random_state(rnd), random_state(rnd)

    if stable_stringify(merge_states(a, a)) != stable_stringify(normalize_state(a)):
        bad_idem += 1
    if stable_stringify(merge_states(a, b)) != stable_stringify(merge_states(b, a)):
        bad_comm += 1
    if stable_stringify(merge_states(merge_states(a, b), c)) != \
       stable_stringify(merge_states(a, merge_states(b, c))):
        bad_assoc += 1

check(f"property: {ROUNDS} rounds of idempotence", bad_idem == 0, f"{bad_idem} violations")
check(f"property: {ROUNDS} rounds of commutativity", bad_comm == 0, f"{bad_comm} violations")
check(f"property: {ROUNDS} rounds of associativity", bad_assoc == 0, f"{bad_assoc} violations")

# ── 4. Cross-language parity of stable_stringify ─────────────────────────
# pick_record's last-resort tie-break compares these strings, so the two
# implementations must produce byte-identical output for shared value types.

eq("parity: stable_stringify sorts keys", stable_stringify({"b": 1, "a": 2}), '{"a":2,"b":1}')
eq("parity: stable_stringify nests", stable_stringify({"z": [{"b": 1, "a": 2}], "a": None}),
   '{"a":null,"z":[{"a":2,"b":1}]}')
eq("parity: stable_stringify keeps CJK raw",
   stable_stringify({"a": "单词复习"}), '{"a":"单词复习"}')
eq("parity: stable_stringify booleans and ints",
   stable_stringify({"a": True, "b": 1000}), '{"a":true,"b":1000}')

# ── 5. Mutation helpers own invariant I1 ─────────────────────────────────

state = empty_state()
apply_checkin(state, "h1", "2026-09-14", True, 1000)
first = state["checkins"]["h1"]["2026-09-14"]
apply_checkin(state, "h1", "2026-09-14", False, 1000)
second = state["checkins"]["h1"]["2026-09-14"]
apply_checkin(state, "h1", "2026-09-14", True, 1000)
third = state["checkins"]["h1"]["2026-09-14"]

check("I1: stamps strictly increase under same-second rewrites",
      first < abs(second) < third, f"got {first}, {second}, {third}")
check("I1: sign encodes the requested state", first > 0 > second and third > 0)
check("I1: a later stamp beats an earlier one", merge_cell(second, third) == third)
check("I1: next_stamp never goes backwards with a clock in the past",
      next_stamp(5000, 100) == 5001, f"got {next_stamp(5000, 100)}")

rec = {"id": "h1", "updatedAt": 9000, "writer": "pc"}
touch_record(rec, 100, "phone")
check("I1: touch_record bumps past an existing future stamp",
      rec["updatedAt"] == 9001 and rec["writer"] == "phone", str(rec))

# ── 6. Read helpers ──────────────────────────────────────────────────────

state = empty_state()
apply_checkin(state, "h1", "2026-09-14", True, 1000)
apply_checkin(state, "h1", "2026-09-15", False, 2000)
apply_checkin(state, "h1", "2026-09-16", True, 3000)

check("is_checked: a tombstone reads as unchecked", not is_checked(state, "h1", "2026-09-15"))
check("is_checked: a positive cell reads as checked", is_checked(state, "h1", "2026-09-16"))
check("is_checked: a missing cell reads as unchecked", not is_checked(state, "h1", "2026-09-17"))
eq("checked_dates: excludes tombstones",
   sorted(checked_dates(state, "h1")), ["2026-09-14", "2026-09-16"])
eq("live_records: drops tombstones",
   [h["id"] for h in live_records({"a": {"id": "a"}, "b": {"id": "b", "deleted": True}})],
   ["a"])
eq("live_records: tolerates None", live_records(None), [])

# ── 7. Tombstone pruning ─────────────────────────────────────────────────

now, day = 1_760_000_000, 86400
state = empty_state()
apply_checkin(state, "h1", "old-tombstone", False, now - 200 * day)
apply_checkin(state, "h1", "recent-tombstone", False, now - 10 * day)
apply_checkin(state, "h1", "ancient-checkin", True, now - 400 * day)
prune_tombstones(state, now, 180)

check("prune: aged tombstone is dropped", "old-tombstone" not in state["checkins"]["h1"])
check("prune: recent tombstone is kept", "recent-tombstone" in state["checkins"]["h1"])
check("prune: a real check-in is never dropped, however old",
      "ancient-checkin" in state["checkins"]["h1"])

# ── Report ───────────────────────────────────────────────────────────────

total = passed + len(failures)
if failures:
    print(f"\n{len(failures)} of {total} checks FAILED:\n", file=sys.stderr)
    for item in failures:
        print(f"  x {item}", file=sys.stderr)
    sys.exit(1)
print(f"OK all {total} checks passed ({len(cases)} fixtures, {ROUNDS * 3} property rounds)")
