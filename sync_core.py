"""ATM data format and sync engine -- shared by the app and the CLI tools.

This file sits next to app.py ON PURPOSE. PyInstaller bundles whatever app.py
imports, so keeping the engine here means the packaged .exe picks it up with no
build-config changes and no sys._MEIPASS path juggling. The tools in tools/
import it from here, so there is exactly one implementation.

Mirrors docs/js/merge.js exactly; both are verified against the same fixtures
in tests/merge_cases.json.

    python tools/atm_state.py --import            # dry run, prints a report
    python tools/atm_state.py --import --write    # writes .atm/atm-state.json
    python tools/atm_state.py --import --write --push

── Data model ──────────────────────────────────────────────────────────────
Check-ins merge per cell (habit x date) with a sign-encoded last-write-wins
register:

    v > 0   checked at epoch-second v
    v < 0   explicitly unchecked at epoch-second -v   ("tombstone")

The tombstone is a value, not a consumed event, so it keeps winning on every
device forever -- that is what makes un-checking propagate to a device that
still believes the day was checked.

Two invariants the caller MUST uphold (see next_stamp/touch_record):
  I1. Timestamps are strictly monotonic per cell/record.
  I2. Records are always written whole, never partially.
I1 is what lets pick_record ignore content entirely.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCHEMA = 3
TOMBSTONE_TTL_DAYS = 180

# Beijing has had no DST since 1991, so a fixed offset is exact year-round.
BJ = timezone(timedelta(hours=8))

UNASSIGNED_ID = "g_unassigned"
UNASSIGNED_ZH = "未分组"
UNASSIGNED_EN = "Ungrouped"
UNASSIGNED_COLOR = "#605e5c"

HERE = Path(__file__).resolve().parent
REPO = HERE

DATA_REPO = "nikezi623/ATM-data"
DATA_PATH = "atm-state.json"
DATA_BRANCH = "main"


class SyncError(RuntimeError):
    """Anything a caller should surface rather than crash on."""


class SyncPaths:
    """Where sync reads and writes.

    The state directory follows the DATA, not the executable. The desktop app
    runs from dist/ while the command-line tools run from the repo root, and
    both must find the same last-state snapshot: without it the diff cannot
    tell a deletion from something it has never seen, and every sync would
    re-add the entire task list.
    """

    def __init__(self, pool_dir, state_dir=None):
        self.pool = Path(pool_dir)
        self.state = Path(state_dir) if state_dir else self.pool.parent / ".atm"

    @property
    def last_state(self) -> Path:
        return self.state / "last-state.json"

    @property
    def migrated(self) -> Path:
        return self.state / "atm-state.json"

    @property
    def device(self) -> Path:
        return self.state / "device"

    @property
    def backups(self) -> Path:
        return self.state / "backups"


# ══════════════════════════════════════════════════════════════════════════
#  Merge -- mirror of docs/js/merge.js
# ══════════════════════════════════════════════════════════════════════════

def empty_state() -> dict:
    return {"schema": SCHEMA, "habits": {}, "groups": {}, "checkins": {}, "meta": None}


def normalize_state(raw) -> dict:
    def obj(v):
        return v if isinstance(v, dict) else {}

    if not isinstance(raw, dict):
        raw = {}
    meta = raw.get("meta")
    return {
        "schema": SCHEMA,
        "habits": obj(raw.get("habits")),
        "groups": obj(raw.get("groups")),
        "checkins": obj(raw.get("checkins")),
        "meta": meta if isinstance(meta, dict) else None,
    }


def merge_cell(a, b):
    """Compare MAGNITUDES first, then apply the sign.

    A plain max(a, b) would let an old check-in (+1000) beat a newer un-check
    (-5000) and silently resurrect a day the user deliberately cleared.
    """
    if a is None:
        return b
    if b is None:
        return a
    if abs(a) != abs(b):
        return a if abs(a) > abs(b) else b
    return max(a, b)  # exact tie: checked beats unchecked


def pick_record(a, b):
    """Total order over arbitrary record pairs, not just I1-respecting ones."""
    if not a:
        return b
    if not b:
        return a
    if a.get("updatedAt") != b.get("updatedAt"):
        return a if a.get("updatedAt", 0) > b.get("updatedAt", 0) else b
    if a.get("writer") != b.get("writer"):
        return a if str(a.get("writer", "")) < str(b.get("writer", "")) else b
    # (updatedAt, writer) tied means I1 was violated somewhere. Fall back to
    # content so the result stays deterministic instead of device-dependent.
    return a if stable_stringify(a) <= stable_stringify(b) else b


def merge_states(base, incoming) -> dict:
    """Commutative, associative, idempotent -- so retries are free."""
    a = normalize_state(base)
    b = normalize_state(incoming)
    out = empty_state()

    for table in ("habits", "groups"):
        for key in set(a[table]) | set(b[table]):
            out[table][key] = pick_record(a[table].get(key), b[table].get(key))

    for habit_id in set(a["checkins"]) | set(b["checkins"]):
        left = a["checkins"].get(habit_id) or {}
        right = b["checkins"].get(habit_id) or {}
        cells = {}
        for date_str in set(left) | set(right):
            cells[date_str] = merge_cell(left.get(date_str), right.get(date_str))
        out["checkins"][habit_id] = cells

    out["meta"] = pick_record(a["meta"], b["meta"]) or None
    return out


def next_stamp(prev, now_sec: int) -> int:
    """Next stamp for a value: never decreases, never repeats (invariant I1)."""
    return max(int(now_sec), abs(prev or 0) + 1)


def apply_checkin(state: dict, habit_id: str, date_str: str, checked: bool, now_sec: int) -> dict:
    cells = state["checkins"].setdefault(habit_id, {})
    mag = next_stamp(cells.get(date_str), now_sec)
    cells[date_str] = mag if checked else -mag
    return state


def touch_record(rec: dict, now_sec: int, writer: str) -> dict:
    rec["updatedAt"] = next_stamp(rec.get("updatedAt"), now_sec)
    rec["writer"] = writer
    return rec


def prune_tombstones(state: dict, now_sec: int, ttl_days: int = TOMBSTONE_TTL_DAYS) -> dict:
    cutoff = now_sec - ttl_days * 86400
    for cells in state["checkins"].values():
        for date_str in [d for d, v in cells.items() if v < 0 and -v < cutoff]:
            del cells[date_str]
    return state


def is_checked(state: dict, habit_id: str, date_str: str) -> bool:
    v = (state.get("checkins") or {}).get(habit_id, {}).get(date_str)
    return isinstance(v, int) and v > 0


def checked_dates(state: dict, habit_id: str) -> list[str]:
    cells = (state.get("checkins") or {}).get(habit_id) or {}
    return [d for d, v in cells.items() if v > 0]


def live_records(table: dict) -> list[dict]:
    return [r for r in (table or {}).values() if r and not r.get("deleted")]


def stable_stringify(value) -> str:
    """Key-sorted JSON, matching docs/js/merge.js stableStringify for the
    value types used here (str/int/bool/None/dict/list).

    Not for merge decisions except the unreachable tie-break in pick_record --
    it exists so two devices agree on a canonical form.
    """
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


# ══════════════════════════════════════════════════════════════════════════
#  Legacy <-> state
# ══════════════════════════════════════════════════════════════════════════

def normalize_text(text: str) -> str:
    return "".join(str(text).lower().split())


def group_id_for(name_zh: str) -> str:
    """Deterministic, so re-running an import is idempotent."""
    digest = hashlib.sha1(str(name_zh).strip().encode("utf-8")).hexdigest()
    return "g_" + digest[:10]


def date_to_cell(date_str: str) -> int:
    """Midnight of the date itself, in Beijing time.

    Using the date's own midnight rather than the import time makes the import
    idempotent AND guarantees it can never outrank a real action taken later.
    """
    parsed = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=BJ)
    return int(parsed.timestamp())


def find_task_pool(base_dir: Path) -> Path:
    """Port of app.py:_find_task_pool -- searches six candidate locations and
    picks the one with the most habits in habits.json.

    The user has been bitten twice by multiple task_pool copies (commits
    4745534, 1f1ab48), so never hardcode a path.
    """
    candidates = [
        base_dir / "task_pool",
        base_dir / "dist" / "task_pool",
        base_dir.parent / "task_pool",
        base_dir.parent / "dist" / "task_pool",
        base_dir.parent.parent / "task_pool",
        base_dir.parent.parent / "dist" / "task_pool",
    ]
    best = base_dir / "task_pool"
    best_count = 0
    for pool in candidates:
        habits_file = pool / "habits.json"
        if habits_file.exists():
            try:
                count = len(json.loads(habits_file.read_text(encoding="utf-8")))
            except Exception:
                continue
            if count >= best_count:  # ties go to the later candidate, as in app.py
                best, best_count = pool, count
    return best


def load_legacy_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def load_legacy(pool_dir: Path):
    return (
        load_legacy_json(pool_dir / "habits.json", []),
        load_legacy_json(pool_dir / "groups.json", []),
        load_legacy_json(pool_dir / "settings.json", {}),
    )


def legacy_to_state(habits: list, groups: list, settings: dict, now_sec: int,
                    writer: str = "migrate"):
    """Convert the desktop app's three JSON files into one state document.

    Returns (state, report). The report is not decoration: habits whose group
    string matches no group are silently invisible in the desktop UI and
    unreachable from its menus, so the migration must surface them rather than
    quietly dropping or vanishing them.
    """
    state = empty_state()
    report = {"orphans": [], "bad_dates": [], "duplicate_ids": [], "group_count": 0,
              "habit_count": 0, "cell_count": 0}

    # Resolve group references through name_zh, name_en and a normalized form.
    # The desktop app stores whichever name was displayed when the habit was
    # last edited, so all three spellings occur in real data.
    resolved = []          # (group_dict, gid)
    lookup = {}
    seen_group_ids = set()
    for group in groups:
        name_zh = str(group.get("name_zh") or "").strip()
        if not name_zh:
            continue
        gid = group_id_for(name_zh)
        if gid in seen_group_ids:
            report["duplicate_ids"].append(f"group '{name_zh}'")
            continue
        seen_group_ids.add(gid)
        name_en = str(group.get("name_en") or "").strip() or name_zh
        resolved.append((group, gid))
        for spelling in (name_zh, name_en):
            lookup[spelling] = gid
            lookup[normalize_text(spelling)] = gid

    # Preserve the desktop app's display order: it sorts groups by `order`,
    # which has gaps in real data (0,2,3,4,5). Rank them, then space out.
    resolved.sort(key=lambda pair: pair[0].get("order", 0))
    for rank, (group, gid) in enumerate(resolved):
        name_zh = str(group["name_zh"]).strip()
        state["groups"][gid] = {
            "id": gid,
            "name_zh": name_zh,
            "name_en": str(group.get("name_en") or "").strip() or name_zh,
            "color": str(group.get("color") or "#0078d4"),
            "order": rank * 10,
            "updatedAt": now_sec,
            "writer": writer,
            "deleted": False,
        }

    orphaned = []
    seen_habit_ids = set()
    for index, habit in enumerate(habits):
        if not isinstance(habit, dict):
            continue
        name = str(habit.get("name") or "").strip()
        habit_id = str(habit.get("id") or "") or f"h_{index}"
        if habit_id in seen_habit_ids:
            report["duplicate_ids"].append(f"habit '{name}' ({habit_id})")
            continue
        seen_habit_ids.add(habit_id)

        raw_group = str(habit.get("group") or "").strip()
        gid = lookup.get(raw_group) or lookup.get(normalize_text(raw_group))
        if not gid:
            gid = UNASSIGNED_ID
            orphaned.append((name, raw_group))

        state["habits"][habit_id] = {
            "id": habit_id,
            "name": name,
            "groupId": gid,
            # Display order in the desktop app is the global array position
            # (rows are filtered per group from one flat list), so the index
            # is the ground truth -- per-group indices would reorder the list.
            "order": index * 10,
            "updatedAt": now_sec,
            "writer": writer,
            "deleted": False,
        }

        cells = {}
        for date_str in habit.get("checkins") or []:
            if not isinstance(date_str, str):
                continue
            try:
                datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                report["bad_dates"].append(f"{name}: {date_str!r}")
                continue
            cells[date_str] = date_to_cell(date_str)
        if cells:
            state["checkins"][habit_id] = cells

    # meta carries the only shared setting: whether the WeCom report fires.
    # The webhook URL is deliberately NOT here -- it stays on the desktop and
    # in the repository secret, never in data the phone can read.
    state["meta"] = {
        "bot_enabled": bool(settings.get("bot_enabled", False)),
        "updatedAt": now_sec,
        "writer": writer,
    }

    if orphaned:
        existing = state["groups"].get(UNASSIGNED_ID)
        if not existing:
            state["groups"][UNASSIGNED_ID] = {
                "id": UNASSIGNED_ID,
                "name_zh": UNASSIGNED_ZH,
                "name_en": UNASSIGNED_EN,
                "color": UNASSIGNED_COLOR,
                "order": len(resolved) * 10 + 10,
                "updatedAt": now_sec,
                "writer": writer,
                "deleted": False,
            }
        report["orphans"] = orphaned

    report["group_count"] = len(state["groups"])
    report["habit_count"] = len(state["habits"])
    report["cell_count"] = sum(len(c) for c in state["checkins"].values())
    return state, report


def state_to_legacy(state: dict):
    """Project a state back into the desktop app's three-file format.

    `collapsed` is device-local UI state and is not stored in the state, so it
    always comes back False; the round-trip check accounts for that.
    """
    state = normalize_state(state)
    # Break ties on id, not insertion order: two records sharing an `order`
    # would otherwise sort differently on different devices, which presents as
    # two rows swapping at random.
    groups = sorted(live_records(state["groups"]), key=lambda g: (g.get("order", 0), g["id"]))

    legacy_groups = []
    name_by_gid = {}
    for rank, group in enumerate(groups):
        name_zh = group.get("name_zh") or group.get("name_en") or ""
        name_by_gid[group["id"]] = name_zh
        legacy_groups.append({
            "name_zh": name_zh,
            "name_en": group.get("name_en") or name_zh,
            "color": group.get("color") or "#0078d4",
            "collapsed": False,
            "order": rank,
        })

    legacy_habits = []
    for habit in sorted(live_records(state["habits"]), key=lambda h: (h.get("order", 0), h["id"])):
        legacy_habits.append({
            "id": habit["id"],
            "name": habit.get("name", ""),
            "group": name_by_gid.get(habit.get("groupId"), UNASSIGNED_ZH),
            "checkins": sorted(checked_dates(state, habit["id"])),
        })
    return legacy_habits, legacy_groups


def legacy_projection(habits: list, groups: list) -> dict:
    """The parts of the legacy view that survive a round trip.

    `collapsed` is device-local UI state deliberately not carried in the state
    document, so it is excluded rather than compared.
    """
    order_of = {str(g.get("name_zh") or ""): i for i, g in enumerate(groups)}
    return {
        "groups": [
            {
                "name_zh": str(g.get("name_zh") or ""),
                "name_en": str(g.get("name_en") or "").strip() or str(g.get("name_zh") or ""),
                "color": str(g.get("color") or "#0078d4"),
            }
            for g in sorted(groups, key=lambda g: order_of[str(g.get("name_zh") or "")])
        ],
        "habits": [
            {
                "id": str(h.get("id") or ""),
                "name": str(h.get("name") or "").strip(),
                "group": str(h.get("group") or "").strip(),
                "checkins": sorted(str(d) for d in (h.get("checkins") or [])),
            }
            for h in habits
        ],
    }


def assert_round_trip(state: dict, habits: list, groups: list) -> list[str]:
    """Re-derive the legacy view and diff it against the input.

    A one-time, irreversible migration earns a 20-line guard: if this returns
    anything, the caller must abort and write nothing.
    """
    back_habits, back_groups = state_to_legacy(state)
    before = legacy_projection(habits, groups)
    after = legacy_projection(back_habits, back_groups)

    problems = []
    if len(before["habits"]) != len(after["habits"]):
        problems.append(f"habit count {len(before['habits'])} -> {len(after['habits'])}")
    if len(before["groups"]) != len(after["groups"]):
        problems.append(f"group count {len(before['groups'])} -> {len(after['groups'])}")

    for b, a in zip(before["habits"], after["habits"]):
        if b != a:
            problems.append(f"habit differs: {b} -> {a}")
    for b, a in zip(before["groups"], after["groups"]):
        if b != a:
            problems.append(f"group differs: {b} -> {a}")

    before_cells = sum(len(h["checkins"]) for h in before["habits"])
    after_cells = sum(len(h["checkins"]) for h in after["habits"])
    if before_cells != after_cells:
        problems.append(f"check-in cell count {before_cells} -> {after_cells}")

    # Every date must survive individually, not just the total.
    for h in before["habits"]:
        match = next((x for x in after["habits"] if x["id"] == h["id"]), None)
        if match and set(h["checkins"]) != set(match["checkins"]):
            missing = set(h["checkins"]) - set(match["checkins"])
            problems.append(f"{h['name']}: lost check-ins {sorted(missing)[:5]}")
    return problems


# ══════════════════════════════════════════════════════════════════════════
#  GitHub Contents API
# ══════════════════════════════════════════════════════════════════════════

class GitHubError(RuntimeError):
    def __init__(self, status: int, message: str):
        super().__init__(f"HTTP {status}: {message}")
        self.status = status
        self.message = message


def _api_request(url: str, token: str, method: str = "GET", body: dict | None = None,
                 timeout: int = 30):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("X-GitHub-Api-Version", "2022-11-28")
    if data:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(detail).get("message", detail)
        except json.JSONDecodeError:
            pass
        raise GitHubError(exc.code, detail) from None
    except urllib.error.URLError as exc:
        raise GitHubError(0, f"network error: {exc.reason}") from None


def get_remote_state(token: str, repo: str = DATA_REPO, path: str = DATA_PATH,
                     branch: str = DATA_BRANCH, timeout: int = 30):
    """Returns (state, sha). sha is None when the file does not exist yet."""
    url = f"https://api.github.com/repos/{repo}/contents/{path}?ref={branch}"
    try:
        payload = _api_request(url, token, timeout=timeout)
    except GitHubError as exc:
        if exc.status == 404:
            return None, None
        raise
    import base64
    content = base64.b64decode(payload["content"]).decode("utf-8")
    return normalize_state(json.loads(content)), payload["sha"]


def put_remote_state(state: dict, sha: str | None, token: str, message: str,
                     repo: str = DATA_REPO, path: str = DATA_PATH,
                     branch: str = DATA_BRANCH, timeout: int = 30) -> str:
    """Commit the state. Raises GitHubError(409) when sha is stale."""
    import base64
    body = {
        "message": message,
        "content": base64.b64encode(stable_stringify(state).encode("utf-8")).decode("ascii"),
        "branch": branch,
    }
    if sha:
        body["sha"] = sha
    payload = _api_request(f"https://api.github.com/repos/{repo}/contents/{path}", token,
                           method="PUT", body=body, timeout=timeout)
    return payload["content"]["sha"]


def now_stamp() -> str:
    """'2026-09-16 20:44 +0800' for commit messages.

    Date and time from the same timezone: an audit log that mixes a local date
    with a UTC clock is ambiguous exactly when you are reading it to debug.
    """
    return datetime.now(BJ).strftime("%Y-%m-%d %H:%M %z")


def resolve_token(explicit: str | None = None, state_dir: Path | None = None) -> str:
    """Token from --token, $GITHUB_TOKEN, a saved .atm/token, or the gh CLI.

    Returns "" when nothing is configured rather than exiting: the desktop app
    treats that as "just work offline", and a windowed .exe has no console to
    print an error to anyway. CLI callers check for "" and report it.
    """
    if explicit:
        return explicit.strip()
    env = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if env:
        return env.strip()
    if state_dir:
        saved = Path(state_dir) / "token"
        if saved.exists():
            try:
                value = saved.read_text(encoding="utf-8").strip()
            except OSError:
                value = ""
            if value:
                return value
    import subprocess
    try:
        # CREATE_NO_WINDOW: without it a packaged GUI app flashes a console
        # window every time it shells out.
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        # stdin=DEVNULL as well: a --windowed .exe has no valid stdin handle,
        # and an inherited one makes the child fail in ways that are invisible
        # without a console.
        out = subprocess.run(["gh", "auth", "token"], capture_output=True,
                             text=True, timeout=15, creationflags=flags,
                             stdin=subprocess.DEVNULL)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return ""


# ══════════════════════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════════════════════

def _use_utf8_stdout():
    """Windows consoles default to cp936 and would mangle the Chinese names."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def cmd_import(args) -> int:
    pool = Path(args.pool).resolve() if args.pool else find_task_pool(REPO)
    paths = SyncPaths(pool, args.state_dir)
    print(f"Task pool: {pool}")
    if not (pool / "habits.json").exists():
        print("  (no habits.json here)")
        return 1

    habits, groups, settings = load_legacy(pool)
    print(f"  {len(habits)} habits, {len(groups)} groups")

    now_sec = int(datetime.now(BJ).timestamp())
    state, report = legacy_to_state(habits, groups, settings, now_sec)

    print(f"\nConverted to schema {SCHEMA}:")
    print(f"  habits        {report['habit_count']}")
    print(f"  groups        {report['group_count']}")
    print(f"  check-in cells {report['cell_count']}")
    print(f"  bot_enabled   {bool(settings.get('bot_enabled', False))}")

    if report["bad_dates"]:
        print(f"\n  Unparseable dates skipped ({len(report['bad_dates'])}):")
        for item in report["bad_dates"][:10]:
            print(f"    - {item}")

    if report["duplicate_ids"]:
        print(f"\n  Duplicate ids skipped ({len(report['duplicate_ids'])}):")
        for item in report["duplicate_ids"][:10]:
            print(f"    - {item}")

    if report["orphans"]:
        print(f"\n  ORPHANS -- habits whose group matched nothing ({len(report['orphans'])}).")
        print("  These are invisible in the desktop UI; they were placed in 未分组:")
        for name, raw in report["orphans"][:20]:
            print(f"    - {name!r} had group={raw!r}")
    else:
        print("\n  0 orphans (every habit's group resolved)")

    problems = assert_round_trip(state, habits, groups)
    if problems:
        print(f"\nROUND TRIP FAILED ({len(problems)} problems) -- nothing written:")
        for item in problems[:10]:
            print(f"    - {item}")
        return 1
    print("  round trip OK (legacy -> state -> legacy matches)")

    if not args.write and not args.push:
        print("\nDry run. Pass --write to save, --write --push to upload.")
        return 0

    paths.state.mkdir(parents=True, exist_ok=True)
    paths.migrated.write_text(stable_stringify(state), encoding="utf-8")
    print(f"\nWrote {paths.migrated}")

    if args.push:
        token = resolve_token(args.token)
        remote, sha = get_remote_state(token)
        if remote is not None:
            merged = merge_states(remote, state)
            print("  merged with existing remote state (import never overwrites)")
        else:
            merged, sha = state, None
        new_sha = put_remote_state(
            merged, sha, token,
            f"import from desktop ({report['habit_count']} habits, {report['cell_count']} cells)",
        )
        print(f"  pushed to {DATA_REPO}/{DATA_PATH} @ {new_sha[:10]}")
    return 0


def main() -> int:
    _use_utf8_stdout()
    parser = argparse.ArgumentParser(description="ATM data format tools")
    parser.add_argument("--import", dest="do_import", action="store_true",
                        help="convert the desktop task_pool into atm-state.json")
    parser.add_argument("--write", action="store_true", help="save .atm/atm-state.json")
    parser.add_argument("--push", action="store_true", help="upload to the data repo")
    parser.add_argument("--pool", help="task_pool directory (default: auto-detect)")
    parser.add_argument("--state-dir", help="where .atm lives (default: beside the pool)")
    parser.add_argument("--token", help="GitHub token (default: $GITHUB_TOKEN or gh auth token)")
    args = parser.parse_args()

    if args.do_import:
        return cmd_import(args)
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
