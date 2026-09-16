"""Two-way sync between the desktop app's task_pool and the cloud state.

    python tools/atm_sync.py            # sync
    python tools/atm_sync.py --dry-run  # show what would change

CLOSE THE DESKTOP APP FIRST. It keeps the task list in memory and rewrites the
whole file on every change, so a check-in made in a running window would
overwrite everything this script just pulled down. sync.bat prompts for this.

How the diff works
------------------
The legacy files cannot express "unchecked" -- a date is either in the
`checkins` array or it is not, and an absent date is ambiguous between "never
checked" and "deliberately cleared". So we keep a snapshot of the last state we
wrote (`.atm/last-state.json`) and diff the current files against it:

    in legacy, not in snapshot   -> a new check-in
    in snapshot, not in legacy   -> an un-check (writes a tombstone)
    habit missing from legacy    -> a deletion (writes a tombstone)
    record fields differ         -> an edit

That turns observable file state into the explicit operations the merge needs.
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import atm_state as atm  # noqa: E402

LEGACY_HABITS = "habits.json"
LEGACY_GROUPS = "groups.json"
LEGACY_SETTINGS = "settings.json"
LAST_STATE_PATH = atm.LOCAL_STATE_DIR / "last-state.json"
DEVICE_PATH = atm.LOCAL_STATE_DIR / "device"
BACKUP_DIR = atm.LOCAL_STATE_DIR / "backups"


def local_now() -> int:
    return int(datetime.now(atm.BJ).timestamp())


def device_id() -> str:
    """A stable id for this machine, so merge tie-breaks are deterministic."""
    atm.LOCAL_STATE_DIR.mkdir(parents=True, exist_ok=True)
    if DEVICE_PATH.exists():
        value = DEVICE_PATH.read_text(encoding="utf-8").strip()
        if value:
            return value
    value = f"pc-{random.randrange(16 ** 6):06x}"
    DEVICE_PATH.write_text(value, encoding="utf-8")
    return value


def read_last_state() -> dict:
    """The state we last wrote to disk.

    Falls back to the migration output when there is no snapshot yet, so the
    first sync after `atm_state.py --import --write` produces an empty diff
    instead of re-adding everything.
    """
    for path in (LAST_STATE_PATH, atm.LOCAL_STATE_PATH):
        if path.exists():
            try:
                return atm.normalize_state(json.loads(path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                continue
    return atm.empty_state()


def save_last_state(state: dict) -> None:
    atm.LOCAL_STATE_DIR.mkdir(parents=True, exist_ok=True)
    LAST_STATE_PATH.write_text(atm.stable_stringify(state), encoding="utf-8")


def backup_legacy(pool: Path) -> Path | None:
    stamp = datetime.now(atm.BJ).strftime("%Y%m%d-%H%M%S")
    target = BACKUP_DIR / stamp
    try:
        target.mkdir(parents=True, exist_ok=True)
        for name in (LEGACY_HABITS, LEGACY_GROUPS, LEGACY_SETTINGS):
            source = pool / name
            if source.exists():
                shutil.copy2(source, target / name)
    except OSError as exc:
        print(f"  warning: could not back up {pool}: {exc}")
        return None
    return target


def plan_group_ids(legacy_groups: list, base: dict) -> dict[str, str]:
    """Map each legacy group to a stable id.

    Group ids are derived from the Chinese name, so a rename on the desktop
    would otherwise read as "delete the old group, create a new one" -- correct
    data, but churn that looks alarming in the history and briefly shows as two
    groups on the phone. So: reuse an existing id when the name still matches,
    fall back to matching by display position (which is what a rename looks
    like), and only mint a fresh id for a genuinely new group.

    Returns {legacy name_zh: gid}.
    """
    legacy_sorted = sorted(legacy_groups, key=lambda g: g.get("order", 0))
    legacy_sorted = [g for g in legacy_sorted if str(g.get("name_zh") or "").strip()]
    base_groups = sorted(atm.live_records(base["groups"]), key=lambda g: g.get("order", 0))

    mapping: dict[str, str] = {}
    used: set[str] = set()

    # Pass 1: same name (either language).
    for group in legacy_sorted:
        keys = {atm.normalize_text(group.get("name_zh") or ""),
                atm.normalize_text(group.get("name_en") or "")} - {""}
        for candidate in base_groups:
            if candidate["id"] in used:
                continue
            names = {atm.normalize_text(candidate.get("name_zh") or ""),
                     atm.normalize_text(candidate.get("name_en") or "")} - {""}
            if keys & names:
                mapping[str(group.get("name_zh")).strip()] = candidate["id"]
                used.add(candidate["id"])
                break

    # Pass 2: same position among the leftovers -- this is what a rename is.
    leftover_legacy = [g for g in legacy_sorted
                       if str(g.get("name_zh")).strip() not in mapping]
    leftover_base = [g for g in base_groups if g["id"] not in used]
    for group, candidate in zip(leftover_legacy, leftover_base):
        mapping[str(group.get("name_zh")).strip()] = candidate["id"]
        used.add(candidate["id"])

    # Pass 3: genuinely new groups.
    for group in legacy_sorted:
        name = str(group.get("name_zh")).strip()
        if name not in mapping:
            mapping[name] = atm.group_id_for(name)
    return mapping


def build_legacy_state(legacy_habits: list, legacy_groups: list,
                       base: dict, now: int, writer: str) -> tuple[dict, dict]:
    """Convert the files into a state, with group ids pinned to existing ones."""
    state, _ = atm.legacy_to_state(legacy_habits, legacy_groups, {}, now, writer)

    id_map = plan_group_ids(legacy_groups, base)
    sha_to_name = {atm.group_id_for(name): name for name in id_map}

    remapped = atm.empty_state()
    old_to_new: dict[str, str] = {}
    for gid, record in state["groups"].items():
        if gid == atm.UNASSIGNED_ID:
            remapped["groups"][gid] = record
            old_to_new[gid] = gid
            continue
        name = sha_to_name.get(gid)
        new_gid = id_map.get(name) or gid
        record["id"] = new_gid
        remapped["groups"][new_gid] = record
        old_to_new[gid] = new_gid

    for hid, record in state["habits"].items():
        # A habit's groupId still points at the pre-remap key, so translate it
        # through the old->new map. Looking it up in the remapped table directly
        # always misses, which makes every habit look like it moved.
        record["groupId"] = old_to_new.get(record["groupId"], record["groupId"])
        remapped["habits"][hid] = record

    remapped["checkins"] = state["checkins"]
    return remapped, id_map


def stamp_for(base_cells: dict, date_str: str, now: int) -> int:
    """A timestamp that outranks whatever the snapshot already holds.

    The delta is built on an empty state, so apply_checkin cannot see the
    value it must beat -- it would use `now` alone. That is wrong for
    future-dated cells: checking a day later this week stores that day's
    midnight, which is LARGER than `now`, so a tombstone stamped `now` would
    lose and the cancelled day would come back. Explicitly seed the magnitude
    from the snapshot.
    """
    previous = abs(base_cells.get(date_str) or 0)
    return max(now, previous + 1)


def diff_against_snapshot(legacy_state: dict, base: dict, now: int, writer: str):
    """Turn (current files, last snapshot) into a state of pending changes."""
    delta = atm.empty_state()
    summary = {"habits_added": 0, "habits_edited": 0, "habits_deleted": 0,
               "groups_added": 0, "groups_edited": 0, "groups_deleted": 0,
               "checked": 0, "unchecked": 0}

    for gid, record in legacy_state["groups"].items():
        previous = base["groups"].get(gid)
        if previous is None:
            delta["groups"][gid] = record
            summary["groups_added"] += 1
        elif (previous.get("name_zh") != record["name_zh"]
              or previous.get("name_en") != record["name_en"]
              or previous.get("color") != record["color"]
              or previous.get("deleted")):
            record["updatedAt"] = max(now, (previous.get("updatedAt") or 0) + 1)
            delta["groups"][gid] = record
            summary["groups_edited"] += 1
    for gid, previous in base["groups"].items():
        if not previous.get("deleted") and gid not in legacy_state["groups"]:
            delta["groups"][gid] = {
                **previous, "deleted": True,
                "updatedAt": max(now, (previous.get("updatedAt") or 0) + 1),
                "writer": writer,
            }
            summary["groups_deleted"] += 1

    for hid, record in legacy_state["habits"].items():
        previous = base["habits"].get(hid)
        if previous is None:
            delta["habits"][hid] = record
            summary["habits_added"] += 1
        elif (previous.get("name") != record["name"]
              or previous.get("groupId") != record["groupId"]
              or previous.get("deleted")):
            record["updatedAt"] = max(now, (previous.get("updatedAt") or 0) + 1)
            delta["habits"][hid] = record
            summary["habits_edited"] += 1
    for hid, previous in base["habits"].items():
        if not previous.get("deleted") and hid not in legacy_state["habits"]:
            delta["habits"][hid] = {
                **previous, "deleted": True,
                "updatedAt": max(now, (previous.get("updatedAt") or 0) + 1),
                "writer": writer,
            }
            summary["habits_deleted"] += 1

    for hid in legacy_state["habits"]:
        if delta["habits"].get(hid, {}).get("deleted"):
            continue
        base_cells = base["checkins"].get(hid) or {}
        was = {d for d, v in base_cells.items() if v > 0}
        now_checked = {d for d, v in (legacy_state["checkins"].get(hid) or {}).items() if v > 0}
        for date_str in sorted(now_checked - was):
            atm.apply_checkin(delta, hid, date_str, True, stamp_for(base_cells, date_str, now))
            summary["checked"] += 1
        for date_str in sorted(was - now_checked):
            atm.apply_checkin(delta, hid, date_str, False, stamp_for(base_cells, date_str, now))
            summary["unchecked"] += 1

    # ── Ordering ──
    # The legacy array order IS the display order, and `state_to_legacy` writes
    # the array back out sorted by `order`. So a reorder made on the desktop
    # would be silently reverted on the next sync unless it is detected here.
    # Only pure reorders are handled; adds and deletes have their own paths.
    live_base = sorted((h for h in base["habits"].values() if not h.get("deleted")),
                       key=lambda h: h.get("order", 0))
    legacy_order = sorted(legacy_state["habits"].values(), key=lambda h: h["order"])
    if [h["id"] for h in live_base] != [h["id"] for h in legacy_order] \
            and {h["id"] for h in live_base} == {h["id"] for h in legacy_order}:
        for record in legacy_order:
            previous = base["habits"].get(record["id"]) or {}
            if previous.get("order") == record["order"]:
                continue
            updated = dict(record)
            updated["updatedAt"] = max(now, (previous.get("updatedAt") or 0) + 1)
            updated["writer"] = writer
            delta["habits"][record["id"]] = updated
            summary["habits_reordered"] = summary.get("habits_reordered", 0) + 1

    return delta, summary


def write_legacy(pool: Path, state: dict, existing_settings: dict) -> None:
    habits, groups = atm.state_to_legacy(state)
    (pool / LEGACY_HABITS).write_text(
        json.dumps(habits, ensure_ascii=False, indent=2), encoding="utf-8")
    (pool / LEGACY_GROUPS).write_text(
        json.dumps(groups, ensure_ascii=False, indent=2), encoding="utf-8")

    # settings.json also holds device-local values (webhook_url, lang,
    # font_size). Only bot_enabled is shared, and the webhook must never leave
    # this machine -- it is the one credential that stays here.
    settings = dict(existing_settings)
    meta = state.get("meta") or {}
    if "bot_enabled" in meta:
        settings["bot_enabled"] = bool(meta["bot_enabled"])
    (pool / LEGACY_SETTINGS).write_text(
        json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    atm._use_utf8_stdout()
    parser = argparse.ArgumentParser(description="Sync the desktop task_pool with the cloud")
    parser.add_argument("--dry-run", action="store_true", help="report only, write nothing")
    parser.add_argument("--pool", help="task_pool directory (default: auto-detect)")
    parser.add_argument("--token", help="GitHub token (default: $GITHUB_TOKEN or gh auth token)")
    args = parser.parse_args()

    pool = Path(args.pool).resolve() if args.pool else atm.find_task_pool(atm.REPO)
    print(f"Task pool: {pool}")
    if not (pool / LEGACY_HABITS).exists():
        print("  no habits.json there -- nothing to sync")
        return 1

    writer = device_id()
    now = local_now()

    legacy_habits, legacy_groups, settings = atm.load_legacy(pool)
    base = read_last_state()
    print(f"  local:  {len(legacy_habits)} habits, {len(legacy_groups)} groups")
    print(f"  device: {writer}")

    legacy_state, _ = build_legacy_state(legacy_habits, legacy_groups, base, now, writer)
    delta, summary = diff_against_snapshot(legacy_state, base, now, writer)

    changes = sum(summary.values())
    print(f"\nLocal changes since the last sync ({changes}):")
    for key, value in summary.items():
        if value:
            print(f"  {key:<16} {value}")
    if not changes:
        print("  (none)")

    token = atm.resolve_token(args.token)
    remote, sha = atm.get_remote_state(token)
    if remote is None:
        print("\nRemote state is empty; this will be the first push.")
        remote = atm.empty_state()

    merged = atm.merge_states(remote, delta)
    atm.prune_tombstones(merged, now)

    back_habits, back_groups = atm.state_to_legacy(merged)
    cells = sum(len(c) for c in merged["checkins"].values())
    print(f"\nAfter merge: {len(back_habits)} habits, {len(back_groups)} groups, {cells} check-in cells")

    if args.dry_run:
        print("\nDry run -- nothing written.")
        return 0

    backup = backup_legacy(pool)
    if backup:
        print(f"  backed up legacy files to {backup.relative_to(atm.REPO)}")

    write_legacy(pool, merged, settings)
    save_last_state(merged)
    print("  wrote task_pool/*.json and .atm/last-state.json")

    new_sha = atm.put_remote_state(merged, sha, token, f"sync {writer}")
    print(f"  pushed to {atm.DATA_REPO} @ {new_sha[:10]}")
    print("\nDone. Reopen the desktop app to see the merged data.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
