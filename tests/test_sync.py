"""Tests for tools/atm_sync.py's diff logic.

    python tests/test_sync.py

This is the desktop data path. A bug here silently loses check-ins made on the
computer -- the legacy files cannot express "unchecked", so the whole diff
depends on a snapshot being interpreted exactly right.

The strongest check is the round trip at the end: applying the computed delta
to the snapshot must reproduce the files we started from, byte for byte.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))

import atm_state as atm          # noqa: E402
import atm_sync as sync          # noqa: E402

passed = 0
failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    global passed
    if condition:
        passed += 1
    else:
        failures.append(f"{name}\n    {detail}" if detail else name)


def eq(name: str, actual, expected) -> None:
    a, b = atm.stable_stringify(actual), atm.stable_stringify(expected)
    check(name, a == b, f"expected {b}\n    actual   {a}")


NOW = 1_760_000_000
WRITER = "pc-test"


def sample_files():
    habits = [
        {"id": "h1", "name": "单词复习", "group": "雅思", "checkins": ["2026-09-14", "2026-09-15"]},
        {"id": "h2", "name": "百词斩新词打卡", "group": "雅思", "checkins": []},
        {"id": "h3", "name": "阅读 30 分钟", "group": "学习", "checkins": ["2026-09-15"]},
    ]
    groups = [
        {"name_zh": "雅思", "name_en": "IELTS", "color": "#881798", "collapsed": False, "order": 0},
        {"name_zh": "学习", "name_en": "Study", "color": "#0078d4", "collapsed": False, "order": 1},
    ]
    return habits, groups


def snapshot(habits, groups):
    state, _ = sync.build_legacy_state(copy.deepcopy(habits), copy.deepcopy(groups),
                                       atm.empty_state(), NOW, WRITER)
    return state


def delta_for(habits, groups, base):
    state, _ = sync.build_legacy_state(copy.deepcopy(habits), copy.deepcopy(groups),
                                       base, NOW, WRITER)
    return sync.diff_against_snapshot(state, base, NOW + 100, WRITER)


# ── An unchanged file produces no operations ─────────────────────────────

habits, groups = sample_files()
base = snapshot(habits, groups)
delta, summary = delta_for(habits, groups, base)
check("no change: nothing is emitted", sum(summary.values()) == 0, str(summary))
eq("no change: the delta is empty", delta, atm.empty_state())

# ── A new check-in ───────────────────────────────────────────────────────

habits, groups = sample_files()
base = snapshot(habits, groups)
habits[1]["checkins"] = ["2026-09-16"]
delta, summary = delta_for(habits, groups, base)
check("new check-in: counted", summary["checked"] == 1, str(summary))
check("new check-in: written as a positive cell",
      delta["checkins"]["h2"]["2026-09-16"] > 0, str(delta["checkins"]))
check("new check-in: nothing else changes",
      sum(summary.values()) == 1, str(summary))

# ── A cleared check-in becomes a tombstone ───────────────────────────────
# This is the case the legacy format cannot express on its own: the date is
# simply absent, and only the snapshot reveals that it used to be there.

habits, groups = sample_files()
base = snapshot(habits, groups)
habits[0]["checkins"] = ["2026-09-15"]  # 09-14 removed
delta, summary = delta_for(habits, groups, base)
check("un-check: counted", summary["unchecked"] == 1, str(summary))
check("un-check: written as a negative cell",
      delta["checkins"]["h1"]["2026-09-14"] < 0, str(delta["checkins"]))
check("un-check: the surviving date is untouched",
      "2026-09-15" not in delta["checkins"]["h1"], str(delta["checkins"]))

# ── A cleared check-in must still propagate through a merge ──────────────

merged = atm.merge_states(base, delta)
check("un-check: survives the merge into the base",
      not atm.is_checked(merged, "h1", "2026-09-14"))
check("un-check: the other date is still checked",
      atm.is_checked(merged, "h1", "2026-09-15"))

# A stale device that still believes 09-14 was checked must not resurrect it.
stale, _ = sync.build_legacy_state(copy.deepcopy(habits), copy.deepcopy(groups),
                                   atm.empty_state(), NOW - 5000, "phone")
stale["checkins"]["h1"]["2026-09-14"] = NOW - 5000
revived = atm.merge_states(merged, stale)
check("un-check: a stale device cannot resurrect the day",
      not atm.is_checked(revived, "h1", "2026-09-14"))

# ── Renaming a habit ─────────────────────────────────────────────────────

habits, groups = sample_files()
base = snapshot(habits, groups)
habits[2]["name"] = "阅读 45 分钟"
delta, summary = delta_for(habits, groups, base)
check("rename habit: counted as an edit", summary["habits_edited"] == 1, str(summary))
eq("rename habit: the new name is carried",
   delta["habits"]["h3"]["name"], "阅读 45 分钟")
check("rename habit: the timestamp moves forward",
      delta["habits"]["h3"]["updatedAt"] > base["habits"]["h3"]["updatedAt"])

# ── A new habit ──────────────────────────────────────────────────────────

habits, groups = sample_files()
base = snapshot(habits, groups)
habits.append({"id": "h4", "name": "跑步 2km", "group": "学习", "checkins": []})
delta, summary = delta_for(habits, groups, base)
check("new habit: counted", summary["habits_added"] == 1, str(summary))
check("new habit: appears in the delta", "h4" in delta["habits"])
eq("new habit: lands in the right group",
   delta["habits"]["h4"]["groupId"], base["habits"]["h3"]["groupId"])

# ── A deleted habit ──────────────────────────────────────────────────────

habits, groups = sample_files()
base = snapshot(habits, groups)
habits = [h for h in habits if h["id"] != "h2"]
delta, summary = delta_for(habits, groups, base)
check("delete habit: counted", summary["habits_deleted"] == 1, str(summary))
check("delete habit: written as a tombstone",
      delta["habits"]["h2"]["deleted"] is True)
merged = atm.merge_states(base, delta)
check("delete habit: a merge keeps it deleted",
      not [h for h in atm.live_records(merged["habits"]) if h["id"] == "h2"])

# ── Renaming a group reuses its id ───────────────────────────────────────
# Group ids derive from the name, so a naive rebuild would tombstone the old
# group and create a new one. Position matching keeps the id stable, which
# keeps the phone from briefly showing two groups.

habits, groups = sample_files()
base = snapshot(habits, groups)
groups[0]["name_zh"] = "雅思考试"
# The desktop app rewrites every habit's group field when a group is renamed
# (GroupDialog._save), so a realistic rename touches both.
for habit in habits:
    if habit["group"] == "雅思":
        habit["group"] = "雅思考试"
delta, summary = delta_for(habits, groups, base)
check("rename group: no group is created", summary["groups_added"] == 0, str(summary))
check("rename group: no group is deleted", summary["groups_deleted"] == 0, str(summary))
check("rename group: counted as one edit", summary["groups_edited"] == 1, str(summary))
eq("rename group: the id is unchanged",
   list(delta["groups"].keys()), [base["habits"]["h1"]["groupId"]])
check("rename group: habits are NOT treated as moved",
      "h1" not in delta["habits"] and "h2" not in delta["habits"],
      str(list(delta["habits"].keys())))

# ── A new group ──────────────────────────────────────────────────────────

habits, groups = sample_files()
base = snapshot(habits, groups)
groups.append({"name_zh": "科研", "name_en": "Research", "color": "#ff5500",
               "collapsed": False, "order": 2})
delta, summary = delta_for(habits, groups, base)
check("new group: counted", summary["groups_added"] == 1, str(summary))
check("new group: appears in the delta", len(delta["groups"]) == 1)

# ── A deleted group ──────────────────────────────────────────────────────
# The desktop app deletes a group's habits along with it, so the files show
# both the group and its habits gone.

habits, groups = sample_files()
base = snapshot(habits, groups)
groups = [g for g in groups if g["name_zh"] != "学习"]
habits = [h for h in habits if h["group"] != "学习"]
delta, summary = delta_for(habits, groups, base)
check("delete group: the group is tombstoned", summary["groups_deleted"] == 1, str(summary))
check("delete group: its habit is tombstoned too",
      summary["habits_deleted"] == 1, str(summary))
check("delete group: the group record is marked deleted",
      any(r.get("deleted") for r in delta["groups"].values()))

# ── Multiple changes at once ─────────────────────────────────────────────

habits, groups = sample_files()
base = snapshot(habits, groups)
habits[0]["checkins"] = ["2026-09-16"]           # 09-14, 09-15 cleared; 09-16 added
habits[1]["checkins"] = ["2026-09-16"]           # added
habits[2]["name"] = "阅读 60 分钟"                # renamed
delta, summary = delta_for(habits, groups, base)
check("combined: two un-checks", summary["unchecked"] == 2, str(summary))
check("combined: two check-ins", summary["checked"] == 2, str(summary))
check("combined: one habit edit", summary["habits_edited"] == 1, str(summary))

# ── Ordering ─────────────────────────────────────────────────────────────
# Regression: the order used to be taken from the file index, which is only
# valid for the very first import. Survivors of a deletion keep the orders
# they were given when there were more habits, so a new habit's index collided
# with a survivor's order -- and since sorting then fell back to dict insertion
# order, two rows appeared to swap at random.

habits, groups = sample_files()
base = snapshot(habits, groups)
habits = [habits[0], habits[2],
          {"id": "h5", "name": "新习惯", "group": "学习", "checkins": []}]
delta, summary = delta_for(habits, groups, base)
merged = atm.merge_states(base, delta)

live = atm.live_records(merged["habits"])
orders = [h["order"] for h in live]
check("gaps: orders stay unique after a delete plus an add",
      len(orders) == len(set(orders)), str(orders))
eq("gaps: no reorder is flagged when nothing was reordered",
   summary.get("habits_reordered", 0), 0)

got_habits, got_groups = atm.state_to_legacy(merged)
eq("gaps: the new habit lands last",
   [h["name"] for h in got_habits], ["单词复习", "阅读 30 分钟", "新习惯"])
eq("gaps: round trip matches",
   atm.legacy_projection(got_habits, got_groups),
   atm.legacy_projection(habits, groups))

# A real reorder on the desktop must be honoured, not silently reverted.
habits, groups = sample_files()
base = snapshot(habits, groups)
habits.reverse()
delta, summary = delta_for(habits, groups, base)
check("reorder: detected", summary.get("habits_reordered", 0) > 0, str(summary))
merged = atm.merge_states(base, delta)
got_habits, _ = atm.state_to_legacy(merged)
eq("reorder: the reversed order survives",
   [h["id"] for h in got_habits], [h["id"] for h in habits])

# Re-syncing an already-synced state must be a no-op, or every sync would bump
# timestamps and let the desktop clobber edits made on the phone.
settled = atm.merge_states(base, delta)
settled_base = atm.normalize_state(settled)
settled_habits, settled_groups = atm.state_to_legacy(settled)
delta2, summary2 = delta_for(settled_habits, settled_groups, settled_base)
check("idempotent: a second sync produces no operations",
      sum(summary2.values()) == 0, str(summary2))

# ── The round trip ───────────────────────────────────────────────────────
# Merging the delta into the snapshot must reproduce exactly the files we
# started from. If this holds, the diff lost nothing.

for label, mutate in [
    ("checkin", lambda h, g: h[1].update(checkins=["2026-09-16"])),
    ("uncheck", lambda h, g: h[0].update(checkins=["2026-09-14"])),
    ("rename", lambda h, g: h[2].update(name="新名字")),
    ("reorder", lambda h, g: h.reverse()),
    ("regroup", lambda h, g: h[2].update(group="雅思")),
    ("mixed", lambda h, g: (h[0].update(checkins=["2026-09-16"]),
                            h[1].update(name="改名"),
                            h.append({"id": "h9", "name": "新习惯", "group": "学习", "checkins": []}))),
]:
    habits, groups = sample_files()
    base = snapshot(habits, groups)
    mutate(habits, groups)
    delta, _ = delta_for(habits, groups, base)
    merged = atm.merge_states(base, delta)
    got_habits, got_groups = atm.state_to_legacy(merged)
    eq(f"round trip ({label}): habits match",
       atm.legacy_projection(got_habits, got_groups),
       atm.legacy_projection(habits, groups))

# ── The webhook must never be uploaded ───────────────────────────────────

secret = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=SUPERSECRET"
habits, groups = sample_files()
base = snapshot(habits, groups)
delta, _ = delta_for(habits, groups, base)
merged = atm.merge_states(base, delta)
check("privacy: the webhook URL never reaches the synced state",
      "SUPERSECRET" not in atm.stable_stringify(merged))
check("privacy: no settings value is carried in the state at all",
      "webhook" not in atm.stable_stringify(merged).lower())

# ── Report ───────────────────────────────────────────────────────────────

total = passed + len(failures)
if failures:
    print(f"\n{len(failures)} of {total} checks FAILED:\n", file=sys.stderr)
    for item in failures:
        print(f"  x {item}", file=sys.stderr)
    sys.exit(1)
print(f"OK all {total} sync checks passed")
