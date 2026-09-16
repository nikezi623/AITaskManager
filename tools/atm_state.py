"""CLI wrapper -- the implementation lives in ../sync_core.py.

That file sits next to app.py so PyInstaller bundles it into the .exe
automatically. Keeping this wrapper means there is still exactly one
implementation, shared by the app and the command line.

    python tools/atm_state.py --import            # dry run, prints a report
    python tools/atm_state.py --import --write    # writes .atm/atm-state.json
    python tools/atm_state.py --import --write --push
"""

import sys
from pathlib import Path

# sync_core.py is one level up, next to app.py.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sync_core import *  # noqa: F401,F403  (re-exported for tests and callers)
from sync_core import SyncError, SyncPaths, main  # noqa: F401

if __name__ == "__main__":
    sys.exit(main())
