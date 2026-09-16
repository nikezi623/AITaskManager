"""Send the habit check-in report to a WeCom (企业微信) group bot.

Runs inside the ATM-data repository, via .github/workflows/wecom-report.yml.
Reads atm-state.json from the working tree; the webhook comes from the
WECOM_WEBHOOK secret and is never written to the repository.

    python3 tools/send_report.py            # send
    DRY_RUN=1 python3 tools/send_report.py  # print the message instead

The message format matches the desktop app's --send-report byte for byte, so
nothing changes for the reader when the schedule moves from Windows Task
Scheduler to GitHub Actions.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

STATE_PATH = Path("atm-state.json")

# Beijing has had no DST since 1991, so a fixed offset is exact year-round.
#
# THIS IS THE LOAD-BEARING LINE. Runners are UTC, and the 06:05 Beijing run
# fires at 22:05 UTC on the PREVIOUS day -- date.today() would report a date
# one day behind and send the wrong day's data. Always derive the date from
# Beijing wall-clock time.
BEIJING = timezone(timedelta(hours=8))

# Hardcoded rather than strftime("%A"): the desktop app relied on the C locale
# to get English names, which is fragile. This is deterministic everywhere.
WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday",
                 "Friday", "Saturday", "Sunday"]


def load_state() -> dict:
    if not STATE_PATH.exists():
        sys.exit(f"{STATE_PATH} not found -- is this running in the ATM-data repo root?")
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        sys.exit(f"{STATE_PATH} is not valid JSON: {exc}")


def build_message(state: dict, now: datetime) -> str:
    """Reproduce the desktop app's report exactly."""
    habits = sorted(
        (h for h in state.get("habits", {}).values() if not h.get("deleted")),
        key=lambda h: h.get("order", 0),
    )
    checkins = state.get("checkins", {})

    today_str = now.strftime("%Y-%m-%d")
    today_display = f"{today_str} {WEEKDAY_NAMES[now.weekday()]}"

    done_today: list[str] = []
    pending_today: list[str] = []
    for habit in habits:
        cells = checkins.get(habit["id"], {})
        # A positive cell means checked; a negative one is an explicit
        # un-check and must not count.
        if cells.get(today_str, 0) > 0:
            done_today.append(habit["name"])
        else:
            pending_today.append(habit["name"])

    total = len(habits)
    done_count = len(done_today)
    rate = round(done_count / total * 100) if total > 0 else 0

    lines = [
        "## 🤖 ATM 今日习惯打卡",
        "",
        f"**日期**: {today_display}",
        f"**进度**: {done_count}/{total} ({rate}%)",
        "",
    ]
    if pending_today:
        lines.append(f"### ⏳ 待完成 ({len(pending_today)})")
        for name in pending_today:
            lines.append(f"- {name}")

    if done_today:
        lines.extend(["", f"### ✅ 已完成 ({done_count})"])
        for name in done_today:
            lines.append(f"- ✓ {name}")

    if total == 0:
        lines.append("- 暂无习惯")

    return "\n".join(lines)


def send(webhook: str, message: str) -> None:
    payload = json.dumps(
        {"msgtype": "markdown", "markdown": {"content": message}}
    ).encode("utf-8")
    request = urllib.request.Request(
        webhook, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.loads(response.read().decode("utf-8"))
    if result.get("errcode") != 0:
        # A non-zero exit turns a silent failure into a red Actions run, which
        # is the only alerting we get.
        sys.exit(f"WeCom rejected the message: {result.get('errmsg')}")


def main() -> int:
    state = load_state()

    # `or {}` not a default argument: the key exists with value None when a
    # state was merged from two sources that never set it.
    if not (state.get("meta") or {}).get("bot_enabled", False):
        # meta.bot_enabled is toggled from the app; there is no UI for the
        # webhook itself, which lives only in repository secrets.
        print("Bot not enabled (meta.bot_enabled is false).")
        return 0

    now = datetime.now(BEIJING)
    message = build_message(state, now)

    if os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes"):
        print(f"--- dry run, message for {now:%Y-%m-%d %H:%M} Beijing ---")
        print(message)
        return 0

    webhook = os.environ.get("WECOM_WEBHOOK", "").strip()
    if not webhook:
        sys.exit("WECOM_WEBHOOK secret is not set.")

    send(webhook, message)
    print(f"[{datetime.now(BEIJING):%Y-%m-%d %H:%M:%S}] Report sent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
