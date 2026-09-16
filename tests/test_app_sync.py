"""Integration tests for the desktop app's cloud sync.

    python tests/test_app_sync.py

Runs Qt offscreen so the window can be constructed without a display. No
network: sync_once is replaced with a stub, which also lets the test prove the
ordering that makes the whole feature work -- the startup sync must run BEFORE
DataStore reads the files, or the window opens on stale data and the pull was
pointless.

Everything writes to a temp directory, never the real task_pool.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

try:
    from PySide6.QtWidgets import QApplication
except ImportError as exc:
    print(f"SKIP: PySide6 not installed ({exc})")
    sys.exit(0)

import app as atm_app  # noqa: E402
import sync_core  # noqa: E402
import sync_engine  # noqa: E402

passed = 0
failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    global passed
    if condition:
        passed += 1
    else:
        failures.append(f"{name}\n    {detail}" if detail else name)


# ── A sandbox that looks like a real task_pool ───────────────────────────

tmp = Path(tempfile.mkdtemp(prefix="atm-app-test-"))
pool = tmp / "task_pool"
pool.mkdir(parents=True)

(pool / "habits.json").write_text(json.dumps(
    [{"id": "h1", "name": "本地习惯", "group": "雅思", "checkins": ["2026-09-14"]}],
    ensure_ascii=False, indent=2), encoding="utf-8")
(pool / "groups.json").write_text(json.dumps(
    [{"name_zh": "雅思", "name_en": "IELTS", "color": "#881798",
      "collapsed": False, "order": 0}], ensure_ascii=False, indent=2), encoding="utf-8")
(pool / "settings.json").write_text(json.dumps(
    {"bot_enabled": True, "lang": "zh", "font_size": 12},
    ensure_ascii=False, indent=2), encoding="utf-8")

# Point the app's module globals at the sandbox.
atm_app.POOL_DIR = pool
atm_app.HABITS_PATH = pool / "habits.json"
atm_app.GROUPS_PATH = pool / "groups.json"
atm_app.SETTINGS_PATH = pool / "settings.json"
atm_app.SYNC_PATHS = sync_core.SyncPaths(pool, tmp / ".atm")

qt = QApplication.instance() or QApplication([])


def build_window():
    return atm_app.HabitApp()


# ── 1. The startup sync must land before the data is read ────────────────

calls: list[str] = []


def fake_sync_once(paths, **kwargs):
    """Stand in for the cloud: adds a habit the local files don't have."""
    calls.append("sync")
    habits = json.loads((paths.pool / "habits.json").read_text(encoding="utf-8"))
    if not any(h["id"] == "from-cloud" for h in habits):
        habits.append({"id": "from-cloud", "name": "云端新增",
                       "group": "雅思", "checkins": []})
        (paths.pool / "habits.json").write_text(
            json.dumps(habits, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"pushed": True}


real_sync_once = sync_engine.sync_once
sync_engine.sync_once = fake_sync_once
atm_app.sync_engine.sync_once = fake_sync_once

window = build_window()

check("startup: sync runs", calls == ["sync"], str(calls))
check("startup: the window is built on the merged data, not the stale files",
      any(h["id"] == "from-cloud" for h in window.data.habits),
      str([h["id"] for h in window.data.habits]))

# ── 2. The UI reflects the sync state ───────────────────────────────────

check("ui: a sync button exists", window._sync_btn is not None)
check("ui: the button is enabled once the sync is done", window._sync_btn.isEnabled())
check("ui: a sync status label exists", window._sync_label is not None)
check("ui: the label shows the last outcome",
      "已同步" in window._sync_label.text(), window._sync_label.text())

# ── 3. Every state renders, in both languages ───────────────────────────

for key in ("sync_never", "syncing", "sync_ok", "sync_failed", "sync_offline"):
    window._sync_state = (key, {"time": "20:44"} if key == "sync_ok" else {})
    window.data.lang = "zh"
    chinese = window._sync_text()
    window.data.lang = "en"
    english = window._sync_text()
    check(f"i18n: {key} renders in Chinese", bool(chinese) and chinese != key, chinese)
    check(f"i18n: {key} renders in English", bool(english) and english != key, english)
    check(f"i18n: {key} differs between languages", chinese != english,
          f"{chinese!r} == {english!r}")
window.data.lang = "zh"

# ── 4. No token must degrade to local-only, not crash ───────────────────

restore_token = sync_core.resolve_token
sync_core.resolve_token = lambda *a, **k: ""
atm_app.sync_core.resolve_token = sync_core.resolve_token
sync_engine.sync_once = real_sync_once
atm_app.sync_engine.sync_once = real_sync_once

window2 = build_window()
check("no token: the app still constructs", window2.data is not None)
check("no token: it reports local-only mode",
      window2._sync_state[0] == "sync_offline", str(window2._sync_state))
check("no token: the reason is available as a tooltip",
      "token" in window2._sync_detail.lower(), window2._sync_detail)
window2.close()

# ── 5. A failing sync must not take the app down ────────────────────────

def exploding_sync_once(paths, **kwargs):
    raise sync_engine.SyncError("simulated network failure")


sync_core.resolve_token = lambda *a, **k: "fake-token"
atm_app.sync_core.resolve_token = sync_core.resolve_token
sync_engine.sync_once = exploding_sync_once
atm_app.sync_engine.sync_once = exploding_sync_once

window3 = build_window()
check("failure: the app still constructs", window3.data is not None)
check("failure: it reports the failure",
      window3._sync_state[0] == "sync_failed", str(window3._sync_state))
check("failure: it still loaded the local data",
      any(h["id"] == "h1" for h in window3.data.habits))
check("failure: the error text is kept for the tooltip",
      "simulated network failure" in window3._sync_detail, window3._sync_detail)
window3.close()


def unexpected_sync_once(paths, **kwargs):
    raise RuntimeError("a bug in the sync code")


sync_engine.sync_once = unexpected_sync_once
atm_app.sync_engine.sync_once = unexpected_sync_once
window4 = build_window()
check("unexpected error: still constructs", window4.data is not None)
check("unexpected error: reported as failed",
      window4._sync_state[0] == "sync_failed", str(window4._sync_state))
window4.close()

sync_core.resolve_token = restore_token
atm_app.sync_core.resolve_token = restore_token

# ── 6. reload() picks up what a sync wrote ──────────────────────────────

data = window4.data
before = len(data.habits)
habits = json.loads((pool / "habits.json").read_text(encoding="utf-8"))
habits.append({"id": "reloaded", "name": "重新读取", "group": "雅思", "checkins": []})
(pool / "habits.json").write_text(json.dumps(habits, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
check("reload: the in-memory list is stale before the call", len(data.habits) == before)
data.reload()
check("reload: picks up the new file contents",
      any(h["id"] == "reloaded" for h in data.habits),
      str([h["id"] for h in data.habits]))

# ── 7. Sync stays optional ──────────────────────────────────────────────

check("packaging: sync modules import from beside app.py", atm_app.SYNC_AVAILABLE)
check("packaging: the state dir follows the data, not the executable",
      atm_app.SYNC_PATHS.state.parent == pool.parent,
      f"{atm_app.SYNC_PATHS.state} should be a sibling of {pool}")

# ── Report ───────────────────────────────────────────────────────────────

import shutil  # noqa: E402
shutil.rmtree(tmp, ignore_errors=True)

total = passed + len(failures)
if failures:
    print(f"\n{len(failures)} of {total} checks FAILED:\n", file=sys.stderr)
    for item in failures:
        print(f"  x {item}", file=sys.stderr)
    sys.exit(1)
print(f"OK all {total} app-sync checks passed")
