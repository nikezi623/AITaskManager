"""Two-way sync between the desktop task_pool and the cloud state.

    python tools/atm_sync.py            # sync
    python tools/atm_sync.py --dry-run  # show what would change

The implementation lives in ../sync_engine.py, which sits next to app.py so
PyInstaller bundles it into the .exe. This wrapper keeps the same CLI, and
means the app and the command line run identical logic.

CLOSE THE DESKTOP APP FIRST unless you are running a build that syncs on
startup -- the app keeps the task list in memory and rewrites the whole file
on every change, so a check-in made in a running window would overwrite
whatever this just pulled down.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sync_core as core  # noqa: E402
import sync_engine  # noqa: E402
from sync_core import SyncError, SyncPaths  # noqa: E402
from sync_engine import (  # noqa: F401,E402  (re-exported for tests)
    build_legacy_state, diff_against_snapshot, plan_group_ids, sync_once,
)


def main() -> int:
    core._use_utf8_stdout()
    parser = argparse.ArgumentParser(description="Sync the desktop task_pool with the cloud")
    parser.add_argument("--dry-run", action="store_true", help="report only, write nothing")
    parser.add_argument("--pool", help="task_pool directory (default: auto-detect)")
    parser.add_argument("--state-dir", help="where .atm lives (default: beside the pool)")
    parser.add_argument("--token", help="GitHub token (default: $GITHUB_TOKEN or gh auth token)")
    args = parser.parse_args()

    pool = Path(args.pool).resolve() if args.pool else core.find_task_pool(core.REPO)
    paths = SyncPaths(pool, args.state_dir)
    print(f"Task pool: {paths.pool}")
    print(f"State dir: {paths.state}")
    if not (paths.pool / "habits.json").exists():
        print("  no habits.json there -- nothing to sync")
        return 1

    token = core.resolve_token(args.token, state_dir=paths.state)
    if not token:
        print("\nNo GitHub token. Run `gh auth login`, set GITHUB_TOKEN, "
              "or save one in .atm/token.")
        return 1

    try:
        summary = sync_engine.sync_once(
            paths, token=token, dry_run=args.dry_run, log=lambda msg: print(f"  {msg}"))
    except SyncError as exc:
        print(f"\n[FAILED] {exc}")
        return 1

    changes = {k: v for k, v in summary.items() if isinstance(v, int) and v and k != "pushed"}
    print(f"\nLocal changes ({sum(changes.values())}):")
    for key, value in changes.items():
        print(f"  {key:<18} {value}")
    if not changes:
        print("  (none)")

    if args.dry_run:
        print("\nDry run -- nothing written.")
        return 0
    print("\nDone. Reopen the desktop app to see the merged data.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
