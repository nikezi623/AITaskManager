"""Verify the cloud report matches the desktop app byte for byte.

    python tests/test_report.py

The report is the one piece of output the user actually reads, and it moved
from Windows Task Scheduler to GitHub Actions, so any drift is immediately
visible. Rather than eyeballing two format strings, this imports the real
desktop function, stubs out its network call, and diffs what it would have
sent against what the cloud script produces.

Requires PySide6 (to import app.py) and the migrated .atm/atm-state.json.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "tools" / "atm-data-repo" / "tools"))

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

passed = 0
failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    global passed
    if condition:
        passed += 1
    else:
        failures.append(f"{name}\n    {detail}" if detail else name)


def report(message: str) -> None:
    total = passed + len(failures)
    if failures:
        print(f"\n{len(failures)} of {total} checks FAILED:\n", file=sys.stderr)
        for item in failures:
            print(f"  x {item}", file=sys.stderr)
        sys.exit(1)
    print(f"OK all {total} report checks passed")


def skip(reason: str) -> None:
    print(f"SKIP: {reason}")
    sys.exit(0)


# ── Preconditions ────────────────────────────────────────────────────────

try:
    import app as desktop
except ImportError as exc:
    skip(f"cannot import the desktop app ({exc})")

import atm_state  # noqa: E402
import send_report  # noqa: E402

# Build the state from the live task_pool, NOT from a saved .atm snapshot:
# the snapshot goes stale the moment the user edits anything in the desktop
# app, and the test would then be comparing two different datasets.
pool = atm_state.find_task_pool(REPO)
if not (pool / "habits.json").exists():
    skip(f"no habits.json in {pool}")
legacy_habits, legacy_groups, settings = atm_state.load_legacy(pool)
state, _ = atm_state.legacy_to_state(
    legacy_habits, legacy_groups, settings,
    int(datetime.now(ZoneInfo("Asia/Shanghai")).timestamp()))


# ── Capture what the desktop app would send ──────────────────────────────

captured: dict[str, bytes] = {}


class _FakeResponse:
    def __init__(self, body: bytes):
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


def _fake_urlopen(request, timeout=None):  # noqa: ARG001
    captured["payload"] = request.data
    return _FakeResponse(json.dumps({"errcode": 0}).encode("utf-8"))


desktop.urllib.request.urlopen = _fake_urlopen

try:
    desktop._send_report_and_exit()
except SystemExit:
    pass

if "payload" not in captured:
    skip("the desktop app did not attempt a send (bot_enabled false?)")

desktop_payload = json.loads(captured["payload"].decode("utf-8"))
desktop_message = desktop_payload["markdown"]["content"]
check("desktop: sends a markdown message", desktop_payload["msgtype"] == "markdown")

# ── What the cloud script produces for the same data ─────────────────────

now = datetime.now(ZoneInfo("Asia/Shanghai"))
cloud_message = send_report.build_message(state, now)

if desktop_message != cloud_message:
    # Show the first differing line rather than dumping both blobs.
    left = desktop_message.splitlines()
    right = cloud_message.splitlines()
    detail = []
    for index in range(max(len(left), len(right))):
        a = left[index] if index < len(left) else "<missing>"
        b = right[index] if index < len(right) else "<missing>"
        if a != b:
            detail.append(f"line {index + 1}:\n      desktop: {a!r}\n      cloud:   {b!r}")
            if len(detail) >= 4:
                break
    check("parity: cloud message matches the desktop byte for byte", False,
          "\n    ".join(detail) or "(differs only in trailing whitespace)")
else:
    check("parity: cloud message matches the desktop byte for byte", True)

# ── Format invariants from the original implementation ───────────────────

lines = cloud_message.splitlines()
check("format: the header line is exactly as before",
      lines[0] == "## 🤖 ATM 今日习惯打卡", repr(lines[0]))
check("format: the date line has no zero-padding surprises",
      lines[2].startswith("**日期**: ") and len(lines[2]) == len("**日期**: 2026-09-16 Wednesday"),
      repr(lines[2]))
check("format: the progress line uses the N/N (N%) shape",
      lines[3].startswith("**进度**: ") and lines[3].endswith("%)"), repr(lines[3]))
check("format: no trailing newline", not cloud_message.endswith("\n"))
check("format: completed items use '- ✓ ' with a space after the tick",
      all(not line.startswith("- ✓") or line.startswith("- ✓ ")
          for line in lines), "found a '- ✓' without a space")

# ── The timezone trap ────────────────────────────────────────────────────
# The 06:05 Beijing run fires at 22:05 UTC the previous day. A naive
# date.today() on a UTC runner would report the wrong date entirely.

beijing_0605 = datetime(2026, 9, 17, 6, 5, tzinfo=ZoneInfo("Asia/Shanghai"))
utc_equivalent = beijing_0605.astimezone(ZoneInfo("UTC"))
check("timezone: 06:05 Beijing is the previous day in UTC",
      utc_equivalent.strftime("%Y-%m-%d") == "2026-09-16", utc_equivalent.isoformat())

message_at_0605 = send_report.build_message(state, beijing_0605)
check("timezone: the 06:05 report is dated in Beijing, not UTC",
      "2026-09-17" in message_at_0605.splitlines()[2],
      message_at_0605.splitlines()[2])
check("timezone: the weekday name is English",
      any(day in message_at_0605.splitlines()[2] for day in send_report.WEEKDAY_NAMES),
      message_at_0605.splitlines()[2])

# ── Edge cases ───────────────────────────────────────────────────────────

empty = {"schema": 3, "habits": {}, "groups": {}, "checkins": {}, "meta": {"bot_enabled": True}}
empty_message = send_report.build_message(empty, now)
check("edge: an empty state still renders", "0/0 (0%)" in empty_message, empty_message)
check("edge: an empty state falls back to 暂无习惯", "暂无习惯" in empty_message, empty_message)

# A tombstoned cell must not count as done.
tombstoned = {
    "habits": {"h1": {"id": "h1", "name": "测试习惯", "order": 0, "deleted": False}},
    "checkins": {"h1": {now.strftime("%Y-%m-%d"): -1758000000}},
    "meta": {"bot_enabled": True},
}
tomb_message = send_report.build_message(tombstoned, now)
check("edge: an explicit un-check does not count as done",
      "0/1 (0%)" in tomb_message, tomb_message)
check("edge: the un-checked habit is listed as pending",
      "待完成 (1)" in tomb_message, tomb_message)

# A deleted habit must not appear at all.
deleted = {
    "habits": {"h1": {"id": "h1", "name": "已删除", "order": 0, "deleted": True}},
    "checkins": {},
    "meta": {"bot_enabled": True},
}
deleted_message = send_report.build_message(deleted, now)
check("edge: a deleted habit is excluded", "已删除" not in deleted_message, deleted_message)

report(cloud_message)
