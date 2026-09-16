"""Pull / merge / push orchestration for the desktop side.

Lives beside app.py and sync_core.py so PyInstaller bundles all three with no
build-config changes. tools/atm_sync.py is a thin CLI wrapper over sync_once.

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

import json
import random
import shutil
import sys
from datetime import datetime
from pathlib import Path

import sync_core as core

# Re-exported rather than redefined: resolve_token raises it too, and callers
# must be able to catch one type. The desktop app catches this and keeps
# working from local files -- a sync failure must never take the habit list
# down with it.
from sync_core import SyncError  # noqa: F401


# ── Time and identity ────────────────────────────────────────────────────

def local_now() -> int:
    return int(datetime.now(core.BJ).timestamp())


def ensure_device(paths: core.SyncPaths) -> str:
    """A stable id for this machine, so merge tie-breaks are deterministic."""
    paths.state.mkdir(parents=True, exist_ok=True)
    if paths.device.exists():
        value = paths.device.read_text(encoding="utf-8").strip()
        if value:
            return value
    value = f"pc-{random.randrange(16 ** 6):06x}"
    paths.device.write_text(value, encoding="utf-8")
    return value


def read_last_state(paths: core.SyncPaths) -> dict:
    """The state we last wrote to disk.

    Falls back to the migration output when there is no snapshot yet, so the
    first sync after an import produces an empty diff instead of re-adding
    everything.
    """
    for path in (paths.last_state, paths.migrated):
        if path.exists():
            try:
                return core.normalize_state(json.loads(path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                continue
    return core.empty_state()


def save_last_state(paths: core.SyncPaths, state: dict) -> None:
    paths.state.mkdir(parents=True, exist_ok=True)
    paths.last_state.write_text(core.stable_stringify(state), encoding="utf-8")


BACKUP_KEEP = 10


def backup_legacy(paths: core.SyncPaths) -> Path | None:
    stamp = datetime.now(core.BJ).strftime("%Y%m%d-%H%M%S")
    target = paths.backups / stamp
    try:
        target.mkdir(parents=True, exist_ok=True)
        for name in ("habits.json", "groups.json", "settings.json"):
            source = paths.pool / name
            if source.exists():
                shutil.copy2(source, target / name)
        # The app syncs on every launch and exit, so without a cap this grows
        # without bound.
        for old in sorted(p for p in paths.backups.iterdir() if p.is_dir())[:-BACKUP_KEEP]:
            shutil.rmtree(old, ignore_errors=True)
    except OSError:
        return None
    return target


# ── Group identity ───────────────────────────────────────────────────────

def plan_group_ids(legacy_groups: list, base: dict) -> dict:
    """Map each legacy group name to a stable id.

    Group ids derive from the Chinese name, so a rename on the desktop would
    otherwise read as "delete the old group, create a new one" -- correct data,
    but churn that looks alarming in the history and briefly shows two groups
    on the phone. So: reuse an existing id when the name still matches, fall
    back to matching by display position (which is what a rename looks like),
    and only mint a fresh id for a genuinely new group.
    """
    legacy_sorted = sorted(legacy_groups, key=lambda g: g.get("order", 0))
    legacy_sorted = [g for g in legacy_sorted if str(g.get("name_zh") or "").strip()]
    base_groups = sorted(core.live_records(base["groups"]), key=lambda g: g.get("order", 0))

    mapping: dict[str, str] = {}
    used: set[str] = set()

    def names_of(record):
        return {core.normalize_text(record.get("name_zh") or ""),
                core.normalize_text(record.get("name_en") or "")} - {""}

    for group in legacy_sorted:
        keys = names_of(group)
        for candidate in base_groups:
            if candidate["id"] in used:
                continue
            if keys & names_of(candidate):
                mapping[str(group.get("name_zh")).strip()] = candidate["id"]
                used.add(candidate["id"])
                break

    leftover_legacy = [g for g in legacy_sorted
                       if str(g.get("name_zh")).strip() not in mapping]
    leftover_base = [g for g in base_groups if g["id"] not in used]
    for group, candidate in zip(leftover_legacy, leftover_base):
        mapping[str(group.get("name_zh")).strip()] = candidate["id"]
        used.add(candidate["id"])

    for group in legacy_sorted:
        name = str(group.get("name_zh")).strip()
        if name not in mapping:
            mapping[name] = core.group_id_for(name)
    return mapping


def build_legacy_state(legacy_habits: list, legacy_groups: list,
                       base: dict, now: int, writer: str) -> dict:
    """Convert the files into a state, with group ids pinned to existing ones."""
    state, _ = core.legacy_to_state(legacy_habits, legacy_groups, {}, now, writer)

    id_map = plan_group_ids(legacy_groups, base)
    sha_to_name = {core.group_id_for(name): name for name in id_map}

    remapped = core.empty_state()
    old_to_new: dict[str, str] = {}
    for gid, record in state["groups"].items():
        if gid == core.UNASSIGNED_ID:
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
    return remapped


# ── The diff ─────────────────────────────────────────────────────────────

def stamp_for(base_cells: dict, date_str: str, now: int) -> int:
    """A timestamp that outranks whatever the snapshot already holds.

    The delta is built on an empty state, so apply_checkin cannot see the value
    it must beat -- it would use `now` alone. That is wrong for future-dated
    cells: checking a day later this week stores that day's midnight, which is
    LARGER than `now`, so a tombstone stamped `now` would lose and the
    cancelled day would come back. Explicitly seed the magnitude from the
    snapshot.
    """
    return max(now, abs(base_cells.get(date_str) or 0) + 1)


def diff_against_snapshot(legacy_state: dict, base: dict, now: int, writer: str):
    """Turn (current files, last snapshot) into a state of pending changes."""
    delta = core.empty_state()
    summary = {"habits_added": 0, "habits_edited": 0, "habits_deleted": 0,
               "groups_added": 0, "groups_edited": 0, "groups_deleted": 0,
               "checked": 0, "unchecked": 0, "habits_reordered": 0}

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
            core.apply_checkin(delta, hid, date_str, True, stamp_for(base_cells, date_str, now))
            summary["checked"] += 1
        for date_str in sorted(was - now_checked):
            core.apply_checkin(delta, hid, date_str, False, stamp_for(base_cells, date_str, now))
            summary["unchecked"] += 1

    # ── Ordering ──
    # The legacy array order IS the display order, and `state_to_legacy` writes
    # the array back out sorted by `order`. Two things can go wrong, silently:
    #
    #   * Reusing the file index as the order. Valid only for the very first
    #     import. Existing habits keep the orders they were given when there
    #     were more of them, so the gaps left by deletions collide with fresh
    #     indices -- and two habits sharing an order sort by dict insertion
    #     order, which shows up as two rows swapping at random.
    #   * Renumbering on every sync, which bumps updatedAt on unchanged records
    #     and lets a stale desktop view clobber a concurrent phone edit.
    #
    # So: keep existing orders, append new habits after the last one, and
    # renumber only when the file order genuinely disagrees with that model --
    # which is what a drag or a move-up on the desktop looks like.
    live_base = sorted((h for h in base["habits"].values() if not h.get("deleted")),
                       key=lambda h: (h.get("order", 0), h["id"]))
    legacy_seq = [h["id"] for h in
                  sorted(legacy_state["habits"].values(), key=lambda h: h["order"])]
    legacy_ids = set(legacy_seq)
    base_ids = {h["id"] for h in live_base}

    expected = [h["id"] for h in live_base if h["id"] in legacy_ids] \
        + [hid for hid in legacy_seq if hid not in base_ids]

    if legacy_seq != expected:
        for index, hid in enumerate(legacy_seq):
            previous = base["habits"].get(hid) or {}
            record = dict(delta["habits"].get(hid) or legacy_state["habits"][hid])
            record["order"] = index * 10
            if previous.get("order") == record["order"] and hid not in delta["habits"]:
                continue
            record["updatedAt"] = max(now, (previous.get("updatedAt") or 0) + 1)
            record["writer"] = writer
            delta["habits"][hid] = record
            summary["habits_reordered"] += 1
    else:
        next_order = max((h.get("order", 0) for h in live_base), default=-10) + 10
        for hid in legacy_seq:
            if hid in base_ids:
                continue
            record = dict(delta["habits"].get(hid) or legacy_state["habits"][hid])
            record["order"] = next_order
            next_order += 10
            record["updatedAt"] = now
            record["writer"] = writer
            delta["habits"][hid] = record

    return delta, summary


def write_legacy(paths: core.SyncPaths, state: dict, existing_settings: dict) -> None:
    habits, groups = core.state_to_legacy(state)
    (paths.pool / "habits.json").write_text(
        json.dumps(habits, ensure_ascii=False, indent=2), encoding="utf-8")
    (paths.pool / "groups.json").write_text(
        json.dumps(groups, ensure_ascii=False, indent=2), encoding="utf-8")

    # settings.json also holds device-local values (webhook_url, lang,
    # font_size). Only bot_enabled is shared, and the webhook must never leave
    # this machine -- it is the one credential that stays here.
    settings = dict(existing_settings)
    meta = state.get("meta") or {}
    if "bot_enabled" in meta:
        settings["bot_enabled"] = bool(meta["bot_enabled"])
    (paths.pool / "settings.json").write_text(
        json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Entry point ──────────────────────────────────────────────────────────

def sync_once(paths: core.SyncPaths, token: str | None = None, dry_run: bool = False,
              timeout: int = 30, log=None):
    """Pull, merge, write the local files, push.

    Returns a summary dict. Raises SyncError with a human-readable message for
    anything the caller should surface -- a missing token, a rejected token, no
    network. The caller is responsible for not letting that break the app.
    """
    say = log if log is not None else (lambda _msg: None)

    if not (paths.pool / "habits.json").exists():
        raise SyncError(f"no habits.json in {paths.pool}")

    writer = ensure_device(paths)
    now = local_now()

    legacy_habits, legacy_groups, settings = core.load_legacy(paths.pool)
    base = read_last_state(paths)
    say(f"local: {len(legacy_habits)} habits, {len(legacy_groups)} groups")

    legacy_state = build_legacy_state(legacy_habits, legacy_groups, base, now, writer)
    delta, summary = diff_against_snapshot(legacy_state, base, now, writer)

    if token is None:
        token = core.resolve_token(state_dir=paths.state)
    if not token:
        raise SyncError("no GitHub token configured")

    try:
        remote, sha = core.get_remote_state(token, timeout=timeout)
    except core.GitHubError as exc:
        raise SyncError(f"could not read the cloud state: {exc.message}") from None

    if remote is None:
        remote = core.empty_state()
    merged = core.merge_states(remote, delta)
    core.prune_tombstones(merged, now)

    back_habits, back_groups = core.state_to_legacy(merged)
    cells = sum(len(c) for c in merged["checkins"].values())
    say(f"after merge: {len(back_habits)} habits, {len(back_groups)} groups, {cells} cells")

    summary["pushed"] = False
    summary["writer"] = writer
    if dry_run:
        return summary

    # Commit only when the cloud would actually change. The app syncs on every
    # launch and exit; an unconditional PUT would bury the real history under
    # empty commits, and that history is the manual recovery path.
    changed = core.stable_stringify(merged) != core.stable_stringify(remote)

    if changed:
        backup = backup_legacy(paths)
        if backup:
            say(f"backed up to {backup}")
    write_legacy(paths, merged, settings)
    save_last_state(paths, merged)

    if changed:
        try:
            new_sha = core.put_remote_state(
                merged, sha, token, f"sync {writer} {core.now_stamp()}", timeout=timeout)
        except core.GitHubError as exc:
            # Local files are already written and the snapshot saved, so the
            # next run simply tries again. Nothing is lost.
            raise SyncError(f"could not push: {exc.message}") from None
        summary["pushed"] = True
        summary["sha"] = new_sha
    return summary
