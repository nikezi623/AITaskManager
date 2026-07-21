import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta, date
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QScrollArea, QFrame, QSizePolicy,
    QDialog, QVBoxLayout as QVBDialog, QLineEdit, QComboBox, QColorDialog,
    QMessageBox, QMenu, QCalendarWidget,
)
from PySide6.QtCore import Qt, QDate, Signal, QTimer, QSize, QRect
from PySide6.QtGui import QFont, QColor, QPalette, QPainter, QPen, QBrush, QFontDatabase, QAction, QIcon


# ── Paths ───────────────────────────────────────────────────────
def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _find_task_pool(base_dir: Path) -> Path:
    """Search for the task_pool with the most user data."""
    candidates = [
        base_dir / "task_pool",
        base_dir.parent / "task_pool",
        base_dir.parent.parent / "task_pool",
    ]
    best, best_count = base_dir / "task_pool", 0
    for tp in candidates:
        hf = tp / "habits.json"
        if hf.exists():
            try:
                cnt = len(json.loads(hf.read_text(encoding="utf-8")))
                if cnt >= best_count:
                    best, best_count = tp, cnt
            except Exception:
                pass
    return best


BASE_DIR = app_dir()
POOL_DIR = _find_task_pool(BASE_DIR)
POOL_DIR.mkdir(parents=True, exist_ok=True)
HABITS_PATH = POOL_DIR / "habits.json"
GROUPS_PATH = POOL_DIR / "groups.json"
SETTINGS_PATH = POOL_DIR / "settings.json"
ICON_PATH = BASE_DIR / "photo" / "app_icon.ico"

# ── Fluent Colors ───────────────────────────────────────────────
BG = "#f0f2f5"
CARD_BG = "#ffffff"
PRIMARY = "#0078d4"
PRIMARY_HOVER = "#106ebe"
TEXT = "#1f1f1f"
TEXT_SEC = "#605e5c"
SUCCESS = "#107c10"
BORDER = "#e0e0e0"
DOT_GRAY = "#d0d0d0"

# ── Default Data ────────────────────────────────────────────────
DEFAULT_GROUPS = [
    {"name_zh": "晨间", "name_en": "Morning", "color": "#ff8c00", "collapsed": False, "order": 0},
    {"name_zh": "日常", "name_en": "Daily", "color": "#0078d4", "collapsed": False, "order": 1},
    {"name_zh": "学习", "name_en": "Study", "color": "#881798", "collapsed": False, "order": 2},
]
DEFAULT_HABITS = [
    {"id": "h1", "name": "早起 (7:00前)", "group": "晨间", "checkins": []},
    {"id": "h2", "name": "冥想 5 分钟", "group": "晨间", "checkins": []},
    {"id": "h3", "name": "百词斩打卡", "group": "学习", "checkins": []},
    {"id": "h4", "name": "阅读 30 分钟", "group": "日常", "checkins": []},
    {"id": "h5", "name": "运动 20 分钟", "group": "日常", "checkins": []},
]
GROUP_COLORS = ["#0078d4", "#ff8c00", "#881798", "#107c10", "#d13438", "#00b7c3", "#498205", "#e81123"]
DEFAULT_WEBHOOK = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=708bb96a-fd4b-4754-b8fa-c3c02e60fcaf"

# ── i18n ────────────────────────────────────────────────────────
TS = {
    "zh": {
        "title": "ATM · 习惯打卡",
        "lang": "EN",
        "add_habit": "新增习惯",
        "add_group": "新增分组",
        "edit_habit": "编辑习惯",
        "delete_habit": "删除习惯",
        "edit_group": "编辑分组",
        "delete_group": "删除分组",
        "habit_name": "习惯名称",
        "group_name": "分组名称",
        "group_color": "分组颜色",
        "select_group": "选择分组",
        "cancel": "取消",
        "save": "保存",
        "delete": "删除",
        "total_days": "累计",
        "streak_days": "连续",
        "week_completion": "本周完成率",
        "all_done": "全部完成 🎉",
        "confirm_delete_habit": "确定要删除习惯「{name}」吗？",
        "confirm_delete_group": "确定要删除分组「{name}」及其所有习惯吗？",
        "stats_title": "打卡统计",
        "today": "今天",
        "bot_sent_title": "ATM 习惯打卡 · 昨日回顾",
        "bot_date_label": "日期",
        "bot_yesterday_summary": "昨日习惯完成情况",
        "bot_done": "已打卡",
        "bot_missed": "未打卡",
        "bot_no_habits": "暂无习惯",
    },
    "en": {
        "title": "ATM · Habit Tracker",
        "lang": "中文",
        "add_habit": "Add Habit",
        "add_group": "Add Group",
        "edit_habit": "Edit Habit",
        "delete_habit": "Delete Habit",
        "edit_group": "Edit Group",
        "delete_group": "Delete Group",
        "habit_name": "Habit Name",
        "group_name": "Group Name",
        "group_color": "Group Color",
        "select_group": "Select Group",
        "cancel": "Cancel",
        "save": "Save",
        "delete": "Delete",
        "total_days": "Total",
        "streak_days": "Streak",
        "week_completion": "Weekly Completion",
        "all_done": "All Done 🎉",
        "confirm_delete_habit": "Delete habit '{name}'?",
        "confirm_delete_group": "Delete group '{name}' and all its habits?",
        "stats_title": "Statistics",
        "today": "Today",
        "bot_sent_title": "ATM Habit Tracker · Yesterday Recap",
        "bot_date_label": "Date",
        "bot_yesterday_summary": "Yesterday's Habits",
        "bot_done": "Done",
        "bot_missed": "Missed",
        "bot_no_habits": "No habits",
    },
}


# ══════════════════════════════════════════════════════════════════
#  Data Helpers
# ══════════════════════════════════════════════════════════════════
class DataStore:
    """Central data management."""

    def __init__(self):
        self.habits = self._load(HABITS_PATH, DEFAULT_HABITS)
        self.groups = self._load(GROUPS_PATH, DEFAULT_GROUPS)
        self.settings = self._load(SETTINGS_PATH, {
            "webhook_url": DEFAULT_WEBHOOK, "bot_enabled": False,
            "lang": "zh", "font_size": 12,
        })
        self.lang = self.settings.get("lang", "zh")
        self.selected_date = date.today()

    def _load(self, path: Path, default):
        if not path.exists():
            self._save(path, default)
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    def _save(self, path: Path, data):
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def save_habits(self):
        self._save(HABITS_PATH, self.habits)

    def save_groups(self):
        self._save(GROUPS_PATH, self.groups)

    def save_settings(self):
        self._save(SETTINGS_PATH, self.settings)

    def t(self, key):
        return TS.get(self.lang, TS["zh"]).get(key, TS["zh"].get(key, key))

    def fmt(self, key, **kw):
        return self.t(key).format(**kw)

    # ── Habit ops ──
    def toggle_checkin(self, habit_id: str, date_str: str):
        for h in self.habits:
            if h["id"] == habit_id:
                if date_str in h["checkins"]:
                    h["checkins"].remove(date_str)
                else:
                    h["checkins"].append(date_str)
                self.save_habits()
                return

    def is_checked(self, habit_id: str, date_str: str) -> bool:
        for h in self.habits:
            if h["id"] == habit_id:
                return date_str in h["checkins"]
        return False

    def get_total(self, habit_id: str) -> int:
        for h in self.habits:
            if h["id"] == habit_id:
                return len(h["checkins"])
        return 0

    def get_streak(self, habit_id: str) -> int:
        """Consecutive days ending today."""
        for h in self.habits:
            if h["id"] == habit_id:
                checkins = set(h["checkins"])
                streak = 0
                d = date.today()
                while d.strftime("%Y-%m-%d") in checkins:
                    streak += 1
                    d -= timedelta(days=1)
                return streak
        return 0

    def get_habits_checked_today(self, date_str: str) -> set:
        """Return set of habit IDs checked on date_str."""
        checked = set()
        for h in self.habits:
            if date_str in h["checkins"]:
                checked.add(h["id"])
        return checked

    def get_habits_all_ids(self) -> set:
        return {h["id"] for h in self.habits}

    def get_habits_for_group(self, group_name: str):
        return [h for h in self.habits if h.get("group") == group_name]

    def get_group_names(self):
        key = "name_zh" if self.lang == "zh" else "name_en"
        return [g[key] for g in self.groups]

    def week_dates(self, ref_date: date = None):
        """Return list of 7 dates Mon-Sun containing ref_date."""
        if ref_date is None:
            ref_date = date.today()
        monday = ref_date - timedelta(days=ref_date.weekday())
        return [monday + timedelta(days=i) for i in range(7)]

    def week_completion_rate(self, ref_date: date = None):
        """% of all habits completed this week."""
        if ref_date is None:
            ref_date = date.today()
        days = self.week_dates(ref_date)
        total = 0
        done = 0
        for d in days:
            ds = d.strftime("%Y-%m-%d")
            if len(self.habits) > 0:
                total += len(self.habits)
                done += len(self.get_habits_checked_today(ds))
        if total == 0:
            return 0
        return round(done / total * 100)


# ══════════════════════════════════════════════════════════════════
#  Custom Widgets
# ══════════════════════════════════════════════════════════════════
class CheckInButton(QPushButton):
    toggled = Signal(str, str)  # habit_id, date_str

    def __init__(self, habit_id: str, date_str: str, checked: bool, parent=None):
        super().__init__(parent)
        self.habit_id = habit_id
        self.date_str = date_str
        self.setFixedSize(36, 36)
        self.setCursor(Qt.PointingHandCursor)
        self.setCheckable(True)
        self.setChecked(checked)
        self._update_style()

    def _update_style(self):
        if self.isChecked():
            self.setStyleSheet(
                "QPushButton { background: #107c10; border-radius: 18px; border: 2px solid #107c10; "
                "color: white; font-size: 16px; font-weight: bold; }"
                "QPushButton:hover { background: #0e6b0e; }"
            )
            self.setText("✓")
        else:
            self.setStyleSheet(
                "QPushButton { background: white; border-radius: 18px; border: 2px solid #d0d0d0; "
                "color: transparent; font-size: 16px; }"
                "QPushButton:hover { border-color: #107c10; background: #f0fff0; }"
            )
            self.setText("")

    def update_date(self, date_str: str, checked: bool):
        self.date_str = date_str
        self.setChecked(checked)
        self._update_style()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self._update_style()
        self.toggled.emit(self.habit_id, self.date_str)


class HabitRow(QFrame):
    checkin_toggled = Signal(str, str)
    context_menu_requested = Signal(object, object)
    dropped_on = Signal(str, str)  # dragged_habit_id, target_habit_id

    def __init__(self, data: DataStore, habit: dict, selected_date_str: str, parent=None):
        super().__init__(parent)
        self.data = data
        self.habit = habit
        self.date_str = selected_date_str
        self._show_streak = False
        self._drag_start = None
        self.setFixedHeight(52)
        self.setAcceptDrops(True)
        self.setStyleSheet(
            f"HabitRow {{ background: {CARD_BG}; border-radius: 8px; "
            f"border: 1px solid {BORDER}; margin: 2px 0; }}"
        )
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)
        self._build()

    def _on_context_menu(self, pos):
        self.context_menu_requested.emit(self.habit, self.mapToGlobal(pos))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_start is None:
            super().mouseMoveEvent(event)
            return
        if (event.position().toPoint() - self._drag_start).manhattanLength() < 15:
            super().mouseMoveEvent(event)
            return
        from PySide6.QtGui import QDrag, QPixmap
        from PySide6.QtCore import QMimeData
        drag = QDrag(self)
        mime = QMimeData()
        mime.setText(self.habit["id"])
        drag.setMimeData(mime)
        pixmap = self.grab()
        drag.setPixmap(pixmap.scaled(pixmap.width() // 2, pixmap.height() // 2, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        drag.setHotSpot(event.position().toPoint() / 2)
        self._drag_start = None
        drag.exec(Qt.MoveAction)

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            self.setStyleSheet(
                f"HabitRow {{ background: #e8f4fd; border-radius: 8px; "
                f"border: 2px dashed {PRIMARY}; margin: 2px 0; }}"
            )
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self.setStyleSheet(
            f"HabitRow {{ background: {CARD_BG}; border-radius: 8px; "
            f"border: 1px solid {BORDER}; margin: 2px 0; }}"
        )

    def dropEvent(self, event):
        dragged_id = event.mimeData().text()
        self.setStyleSheet(
            f"HabitRow {{ background: {CARD_BG}; border-radius: 8px; "
            f"border: 1px solid {BORDER}; margin: 2px 0; }}"
        )
        if dragged_id != self.habit["id"]:
            self.dropped_on.emit(dragged_id, self.habit["id"])
        event.acceptProposedAction()

    def _build(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 6, 10, 6)

        # Color indicator
        group = next((g for g in self.data.groups
                      if g.get("name_zh") == self.habit.get("group")
                      or g.get("name_en") == self.habit.get("group")), None)
        color = group["color"] if group else PRIMARY
        indicator = QLabel()
        indicator.setFixedSize(4, 28)
        indicator.setStyleSheet(f"background: {color}; border-radius: 2px;")
        layout.addWidget(indicator)

        # Name
        name = QLabel(self.habit.get("name", ""))
        name.setFont(QFont("Segoe UI", self.data.settings.get("font_size", 12)))
        name.setStyleSheet(f"color: {TEXT}; border: none; background: transparent;")
        layout.addWidget(name, 1)

        # Stats (clickable to toggle)
        self.stats_btn = QPushButton()
        self.stats_btn.setFont(QFont("Segoe UI", self.data.settings.get("font_size", 12) - 1))
        self.stats_btn.setCursor(Qt.PointingHandCursor)
        self.stats_btn.setFlat(True)
        self._update_stats_text()
        self.stats_btn.clicked.connect(self._toggle_stats)
        layout.addWidget(self.stats_btn)

        # Check-in button
        checked = self.data.is_checked(self.habit["id"], self.date_str)
        self.check_btn = CheckInButton(self.habit["id"], self.date_str, checked)
        self.check_btn.toggled.connect(self._on_checkin)
        layout.addWidget(self.check_btn)

    def _update_stats_text(self):
        total = self.data.get_total(self.habit["id"])
        streak = self.data.get_streak(self.habit["id"])
        if self._show_streak:
            self.stats_btn.setText(f"🔥 {streak}")
            self.stats_btn.setToolTip(self.data.t("streak_days"))
        else:
            self.stats_btn.setText(f"📊 {total}")
            self.stats_btn.setToolTip(self.data.t("total_days"))
        self.stats_btn.setStyleSheet(
            f"QPushButton {{ color: {TEXT_SEC}; border: none; background: transparent; "
            f"padding: 4px 8px; font-size: {self.data.settings.get('font_size', 12) - 1}px; }}"
        )

    def _toggle_stats(self):
        self._show_streak = not self._show_streak
        self._update_stats_text()

    def _on_checkin(self, habit_id, date_str):
        self.data.toggle_checkin(habit_id, date_str)
        self.checkin_toggled.emit(habit_id, date_str)

    def refresh(self, date_str: str):
        self.date_str = date_str
        checked = self.data.is_checked(self.habit["id"], date_str)
        self.check_btn.update_date(date_str, checked)
        self._update_stats_text()


class GroupHeader(QPushButton):
    context_menu_requested = Signal(object, object)
    dropped_on = Signal(str, str)  # dragged_group_name, target_group_name

    def __init__(self, data: DataStore, group: dict, parent=None):
        super().__init__(parent)
        self.data = data
        self.group = group
        self._drag_start = None
        self.setCursor(Qt.PointingHandCursor)
        self.setFlat(True)
        self.setAcceptDrops(True)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)
        self._build()

    def _on_context_menu(self, pos):
        self.context_menu_requested.emit(self.group, self.mapToGlobal(pos))

    def _build(self):
        name = self.group.get("name_zh" if self.data.lang == "zh" else "name_en", "")
        collapsed = self.group.get("collapsed", False)
        arrow = "▶" if collapsed else "▼"
        count = len(self.data.get_habits_for_group(
            self.group.get("name_zh", self.group.get("name_en", ""))))
        self.setText(f"  {arrow}  {name}  ({count})")
        self.setFont(QFont("Segoe UI", self.data.settings.get("font_size", 12), QFont.Bold))
        self.setStyleSheet(
            "QPushButton { color: #1f1f1f; border: none; background: transparent; "
            "text-align: left; padding: 8px 4px; }"
            "QPushButton:hover { color: #0078d4; }"
        )

    def refresh(self):
        self._build()

    # ── Drag & Drop ──
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_start is None:
            super().mouseMoveEvent(event)
            return
        if (event.position().toPoint() - self._drag_start).manhattanLength() < 15:
            super().mouseMoveEvent(event)
            return
        from PySide6.QtGui import QDrag, QPixmap
        from PySide6.QtCore import QMimeData
        drag = QDrag(self)
        mime = QMimeData()
        mime.setText("group:" + self.group.get("name_zh", ""))
        drag.setMimeData(mime)
        pixmap = self.grab()
        drag.setPixmap(pixmap.scaled(pixmap.width() // 2, pixmap.height() // 2,
                                     Qt.KeepAspectRatio, Qt.SmoothTransformation))
        drag.setHotSpot(event.position().toPoint() / 2)
        self._drag_start = None
        drag.exec(Qt.MoveAction)

    def dragEnterEvent(self, event):
        if event.mimeData().hasText() and event.mimeData().text().startswith("group:"):
            self.setStyleSheet(
                "QPushButton { color: #0078d4; border: 2px dashed #0078d4; border-radius: 6px; "
                "background: #e8f4fd; text-align: left; padding: 8px 4px; }"
            )
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self._build()

    def dropEvent(self, event):
        text = event.mimeData().text()
        self._build()
        if text.startswith("group:"):
            dragged_name = text[6:]
            target_name = self.group.get("name_zh", "")
            if dragged_name != target_name:
                self.dropped_on.emit(dragged_name, target_name)
        event.acceptProposedAction()


class WeekNavBar(QWidget):
    """7-day nav bar. Widgets are created once, then updated in-place — no destroy/recreate."""
    date_clicked = Signal(str)
    week_changed = Signal()

    def __init__(self, data: DataStore, parent=None):
        super().__init__(parent)
        self.data = data
        self.ref_date = date.today()
        self.setMinimumHeight(90)
        self.setStyleSheet(f"background: {CARD_BG}; border-radius: 10px;")
        self._first_build()

    def _first_build(self):
        """Create all widgets once. After this, _update() refreshes them in-place."""
        self._day_btns = []
        self._dot_labels = []
        self._dow_labels = []

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(6, 4, 6, 4)
        main_layout.setSpacing(2)

        # Row 0: arrows + year/month
        top_row = QHBoxLayout()
        top_row.setSpacing(4)
        left = QPushButton("◀")
        left.setFixedSize(20, 20)
        left.setFlat(True)
        left.setStyleSheet("QPushButton { color: #605e5c; border: none; font-size: 9px; }")
        left.clicked.connect(lambda: self._shift_week(-7))
        top_row.addWidget(left)

        self._ym_label = QLabel()
        self._ym_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self._ym_label.setStyleSheet("color: #1f1f1f; border: none; background: transparent;")
        top_row.addWidget(self._ym_label)
        top_row.addStretch()

        right = QPushButton("▶")
        right.setFixedSize(20, 20)
        right.setFlat(True)
        right.setStyleSheet("QPushButton { color: #605e5c; border: none; font-size: 9px; }")
        right.clicked.connect(lambda: self._shift_week(7))
        top_row.addWidget(right)
        main_layout.addLayout(top_row)

        # Row 1: 7 date buttons
        self._date_row = QHBoxLayout()
        self._date_row.setSpacing(2)
        for i in range(7):
            btn = QPushButton()
            btn.setFixedSize(32, 32)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _, idx=i: self._on_day_btn(idx))
            self._date_row.addWidget(btn, 1, Qt.AlignCenter)
            self._day_btns.append(btn)
        main_layout.addLayout(self._date_row)

        # Row 2: day-of-week + dots
        info_row = QHBoxLayout()
        info_row.setSpacing(2)
        for i in range(7):
            cell = QVBoxLayout()
            cell.setSpacing(1)
            cell.setContentsMargins(0, 0, 0, 0)

            dow = QLabel()
            dow.setAlignment(Qt.AlignCenter)
            dow.setFont(QFont("Segoe UI", 8))
            dow.setStyleSheet("color: #888888; border: none; background: transparent;")
            cell.addWidget(dow)
            self._dow_labels.append(dow)

            dot = QLabel()
            dot.setFixedSize(8, 8)
            dot.setAlignment(Qt.AlignCenter)
            cell.addWidget(dot, alignment=Qt.AlignCenter)
            self._dot_labels.append(dot)

            info_row.addLayout(cell, 1)
        main_layout.addLayout(info_row)

        self._update()

    def _on_day_btn(self, idx):
        days = self.data.week_dates(self.ref_date)
        if idx < len(days):
            d = days[idx]
            self.data.selected_date = d
            self._update()
            self.date_clicked.emit(d.strftime("%Y-%m-%d"))

    def _shift_week(self, delta_days):
        self.ref_date += timedelta(days=delta_days)
        self._update()
        self.week_changed.emit()

    def _update(self):
        """Refresh all widget text/styles from current data — no destroy."""
        days = self.data.week_dates(self.ref_date)
        today = date.today()
        wd_zh = ["一", "二", "三", "四", "五", "六", "日"]
        wd_en = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

        # Year/month
        ym_text = self.ref_date.strftime("%Y年%m月") if self.data.lang == "zh" else self.ref_date.strftime("%B %Y")
        self._ym_label.setText(ym_text)

        for i, d in enumerate(days):
            # Date button
            btn = self._day_btns[i]
            btn.setText(str(d.day))
            is_sel = d == self.data.selected_date
            is_today = d == today
            if is_sel:
                btn.setStyleSheet(
                    "QPushButton { background: #0078d4; color: #ffffff; border: none; "
                    "border-radius: 16px; font-size: 13px; font-weight: bold; }"
                    "QPushButton:hover { background: #106ebe; }"
                )
            elif is_today:
                btn.setStyleSheet(
                    "QPushButton { color: #0078d4; background: transparent; "
                    "border: 2px solid #0078d4; border-radius: 16px; font-size: 13px; font-weight: bold; }"
                    "QPushButton:hover { background: #e8f4fd; }"
                )
            else:
                btn.setStyleSheet(
                    "QPushButton { color: #1f1f1f; background: transparent; border: none; "
                    "border-radius: 16px; font-size: 13px; }"
                    "QPushButton:hover { background: #f0f0f0; }"
                )

            # Day of week
            wd = wd_en[i] if self.data.lang == "en" else wd_zh[i]
            self._dow_labels[i].setText(wd)

            # Dot
            ds = d.strftime("%Y-%m-%d")
            checked = self.data.get_habits_checked_today(ds)
            all_ids = self.data.get_habits_all_ids()
            all_done = len(all_ids) > 0 and checked == all_ids
            self._dot_labels[i].setStyleSheet(
                "background: #107c10; border-radius: 4px;" if all_done
                else "background: #d0d0d0; border-radius: 4px;"
            )

    def refresh(self):
        self._update()


class StatsDialog(QDialog):
    def __init__(self, data: DataStore, habit: dict = None, parent=None):
        super().__init__(parent)
        self.data = data
        self.habit = habit
        self.setWindowTitle(data.t("stats_title"))
        self.setMinimumSize(360, 400)
        self.setStyleSheet(
            "QDialog { background: #ffffff; }"
            "QLabel { color: #1f1f1f; background: transparent; border: none; }"
            "QFrame { background: #ffffff; }"
        )
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        title = QLabel(self.data.t("stats_title"))
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        layout.addWidget(title)

        habits = [self.habit] if self.habit else self.data.habits
        for h in habits:
            total = self.data.get_total(h["id"])
            streak = self.data.get_streak(h["id"])
            row = QFrame()
            row.setStyleSheet(f"QFrame {{ background: {CARD_BG}; border: 1px solid {BORDER}; border-radius: 8px; padding: 10px; }}")
            rl = QHBoxLayout(row)
            name = QLabel(h["name"])
            name.setFont(QFont("Segoe UI", 12))
            rl.addWidget(name, 1)
            stats = QLabel(f"📊 {total} 天  🔥 {streak} 天连续")
            stats.setFont(QFont("Segoe UI", 11))
            stats.setStyleSheet(f"color: {TEXT_SEC}; border: none;")
            rl.addWidget(stats)
            layout.addWidget(row)

        # Calendar for selected habit
        if self.habit:
            cal = QCalendarWidget()
            cal.setGridVisible(True)
            # Highlight checkin dates
            checkins = set(self.habit.get("checkins", []))
            fmt = cal.format()
            for checkin in checkins:
                try:
                    d = QDate.fromString(checkin, "yyyy-MM-dd")
                    cf = cal.dateTextFormat(d)
                    cf.setBackground(QColor("#107c10"))
                    cf.setForeground(QColor("white"))
                    cal.setDateTextFormat(d, cf)
                except Exception:
                    pass
            layout.addWidget(cal)


# ══════════════════════════════════════════════════════════════════
#  Dialogs
# ══════════════════════════════════════════════════════════════════
class HabitDialog(QDialog):
    def __init__(self, data: DataStore, habit=None, parent=None):
        super().__init__(parent)
        self.data = data
        self.habit = habit
        self.setWindowTitle(data.t("edit_habit") if habit else data.t("add_habit"))
        self.setMinimumWidth(350)
        self.setStyleSheet(
            f"QDialog {{ background: {CARD_BG}; }}"
            "QLineEdit { color: #1f1f1f; background: #ffffff; border: 1px solid #e0e0e0; border-radius: 6px; padding: 8px; font-size: 13px; }"
            "QComboBox { color: #1f1f1f; background: #ffffff; border: 1px solid #e0e0e0; border-radius: 6px; padding: 8px; }"
            "QComboBox::drop-down { border: none; }"
            "QComboBox QAbstractItemView { color: #1f1f1f; background: #ffffff; selection-background-color: #0078d4; }"
            "QLabel { color: #1f1f1f; background: transparent; border: none; }"
        )
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Name
        layout.addWidget(QLabel(self.data.t("habit_name")))
        self.name_input = QLineEdit(self.habit.get("name", "") if self.habit else "")
        self.name_input.setPlaceholderText(self.data.t("habit_name"))
        layout.addWidget(self.name_input)

        # Group
        layout.addWidget(QLabel(self.data.t("select_group")))
        self.group_combo = QComboBox()
        self.group_combo.addItems(self.data.get_group_names())
        if self.habit:
            gname = self.habit.get("group", "")
            if gname in [self.group_combo.itemText(i) for i in range(self.group_combo.count())]:
                self.group_combo.setCurrentText(gname)
        layout.addWidget(self.group_combo)

        # Buttons
        btns = QHBoxLayout()
        cancel = QPushButton(self.data.t("cancel"))
        cancel.clicked.connect(self.reject)
        cancel.setStyleSheet(f"QPushButton {{ color: {TEXT}; border: 1px solid {BORDER}; border-radius: 6px; padding: 8px 20px; }}")
        btns.addWidget(cancel)

        save = QPushButton(self.data.t("save"))
        save.clicked.connect(self._save)
        save.setStyleSheet(
            f"QPushButton {{ background: {PRIMARY}; color: white; border: none; border-radius: 6px; padding: 8px 20px; }}"
            f"QPushButton:hover {{ background: {PRIMARY_HOVER}; }}"
        )
        btns.addWidget(save)
        layout.addLayout(btns)

    def _save(self):
        name = self.name_input.text().strip()
        group = self.group_combo.currentText()
        if not name:
            return
        if self.habit:
            self.habit["name"] = name
            self.habit["group"] = group
        else:
            self.data.habits.append({
                "id": datetime.now().strftime("%Y%m%d%H%M%S%f"),
                "name": name,
                "group": group,
                "checkins": [],
            })
        self.data.save_habits()
        self.accept()


class GroupDialog(QDialog):
    def __init__(self, data: DataStore, group=None, parent=None):
        super().__init__(parent)
        self.data = data
        self.group = group
        self.setWindowTitle(data.t("edit_group") if group else data.t("add_group"))
        self.setMinimumWidth(350)
        self.setStyleSheet(
            "QDialog { background: #ffffff; }"
            "QLineEdit { color: #1f1f1f; background: #ffffff; border: 1px solid #e0e0e0; border-radius: 6px; padding: 8px; }"
            "QLabel { color: #1f1f1f; background: transparent; border: none; }"
            "QComboBox { color: #1f1f1f; background: #ffffff; border: 1px solid #e0e0e0; border-radius: 6px; padding: 8px; }"
        )
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Name (zh)
        layout.addWidget(QLabel(self.data.t("group_name") + " (ZH)"))
        self.name_zh_input = QLineEdit(
            self.group.get("name_zh", "") if self.group else ""
        )
        layout.addWidget(self.name_zh_input)

        # Name (en)
        layout.addWidget(QLabel(self.data.t("group_name") + " (EN)"))
        self.name_en_input = QLineEdit(
            self.group.get("name_en", "") if self.group else ""
        )
        layout.addWidget(self.name_en_input)

        # Color
        color_row = QHBoxLayout()
        color_row.addWidget(QLabel(self.data.t("group_color")))
        self.color = self.group.get("color", PRIMARY) if self.group else PRIMARY
        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(32, 32)
        self.color_btn.setStyleSheet(
            f"QPushButton {{ background: {self.color}; border-radius: 16px; border: 2px solid {BORDER}; }}"
        )
        self.color_btn.clicked.connect(self._pick_color)
        color_row.addWidget(self.color_btn)
        color_row.addStretch()
        layout.addLayout(color_row)

        # Buttons
        btns = QHBoxLayout()
        cancel = QPushButton(self.data.t("cancel"))
        cancel.clicked.connect(self.reject)
        cancel.setStyleSheet(f"QPushButton {{ color: {TEXT}; border: 1px solid {BORDER}; border-radius: 6px; padding: 8px 20px; }}")
        btns.addWidget(cancel)

        if self.group:
            delete = QPushButton(self.data.t("delete"))
            delete.clicked.connect(self._delete)
            delete.setStyleSheet(
                "QPushButton { background: #d13438; color: white; border: none; border-radius: 6px; padding: 8px 20px; }"
                "QPushButton:hover { background: #a8282c; }"
            )
            btns.addWidget(delete)

        save = QPushButton(self.data.t("save"))
        save.clicked.connect(self._save)
        save.setStyleSheet(
            f"QPushButton {{ background: {PRIMARY}; color: white; border: none; border-radius: 6px; padding: 8px 20px; }}"
            f"QPushButton:hover {{ background: {PRIMARY_HOVER}; }}"
        )
        btns.addWidget(save)
        layout.addLayout(btns)

    def _pick_color(self):
        color = QColorDialog.getColor(QColor(self.color), self)
        if color.isValid():
            self.color = color.name()
            self.color_btn.setStyleSheet(
                f"QPushButton {{ background: {self.color}; border-radius: 16px; border: 2px solid {BORDER}; }}"
            )

    def _save(self):
        name_zh = self.name_zh_input.text().strip()
        name_en = self.name_en_input.text().strip()
        if not name_zh:
            return
        if self.group:
            old_zh = self.group.get("name_zh", "")
            old_en = self.group.get("name_en", "")
            self.group["name_zh"] = name_zh
            self.group["name_en"] = name_en or name_zh
            self.group["color"] = self.color
            # Update all habits referencing old group name to new name
            for h in self.data.habits:
                if h.get("group") in (old_zh, old_en):
                    h["group"] = name_zh
            self.data.save_habits()
        else:
            self.data.groups.append({
                "name_zh": name_zh,
                "name_en": name_en or name_zh,
                "color": self.color,
                "collapsed": False,
                "order": len(self.data.groups),
            })
        self.data.save_groups()
        self.accept()

    def _delete(self):
        name = self.group.get("name_zh", "")
        reply = QMessageBox.question(
            self, self.data.t("delete_group"),
            self.data.fmt("confirm_delete_group", name=name),
        )
        if reply == QMessageBox.Yes:
            # Remove group and its habits
            self.data.habits = [h for h in self.data.habits if h.get("group") != name]
            self.data.groups = [g for g in self.data.groups if g != self.group]
            self.data.save_habits()
            self.data.save_groups()
            self.accept()


# ══════════════════════════════════════════════════════════════════
#  Main Window
# ══════════════════════════════════════════════════════════════════
class HabitApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.data = DataStore()
        self._habit_rows = {}  # habit_id -> HabitRow
        self._group_headers = {}  # group_name -> GroupHeader
        self._setup_ui()
        self._build_all()

    def _setup_ui(self):
        self.setWindowTitle(self.data.t("title"))
        self.setMinimumSize(480, 700)
        self.resize(520, 820)
        self.setStyleSheet(f"QMainWindow {{ background: {BG}; }}")

        # Icon
        if ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(ICON_PATH)))

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        self.root_layout = QVBoxLayout(central)
        self.root_layout.setContentsMargins(16, 12, 16, 12)
        self.root_layout.setSpacing(8)

        # ── Header ──
        header = QHBoxLayout()
        title = QLabel(self.data.t("title"))
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet(f"color: {TEXT}; border: none; background: transparent;")
        self._title_label = title
        header.addWidget(title)
        header.addStretch()

        lang_btn = QPushButton(self.data.t("lang"))
        lang_btn.setFlat(True)
        lang_btn.setFont(QFont("Segoe UI", 11))
        lang_btn.setStyleSheet(
            f"QPushButton {{ color: {TEXT_SEC}; border: 1px solid {BORDER}; "
            f"border-radius: 6px; padding: 4px 12px; }}"
            f"QPushButton:hover {{ color: {PRIMARY}; border-color: {PRIMARY}; }}"
        )
        lang_btn.clicked.connect(self._toggle_language)
        self._lang_btn = lang_btn
        header.addWidget(lang_btn)
        self.root_layout.addLayout(header)

        # ── Week Nav Bar ──
        self.week_nav = WeekNavBar(self.data)
        self.week_nav.date_clicked.connect(self._on_date_clicked)
        self.week_nav.week_changed.connect(self._refresh_week_nav_only)
        self.root_layout.addWidget(self.week_nav)

        # ── Scrollable habit list ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background: transparent; }}")
        self._scroll_content = QWidget()
        self._scroll_content.setStyleSheet(f"background: transparent;")
        self._habit_layout = QVBoxLayout(self._scroll_content)
        self._habit_layout.setContentsMargins(0, 0, 0, 0)
        self._habit_layout.setSpacing(4)
        self._habit_layout.addStretch()
        scroll.setWidget(self._scroll_content)
        self.root_layout.addWidget(scroll, 1)

        # ── Footer ──
        footer = QHBoxLayout()
        rate = self.data.week_completion_rate()
        self._footer_label = QLabel(
            self.data.t("week_completion") + f": {rate}%"
        )
        self._footer_label.setFont(QFont("Segoe UI", 11))
        self._footer_label.setStyleSheet(f"color: {TEXT_SEC}; border: none;")
        footer.addWidget(self._footer_label)
        footer.addStretch()

        stats_btn = QPushButton("📊")
        stats_btn.setFlat(True)
        stats_btn.setFont(QFont("Segoe UI", 13))
        stats_btn.setToolTip(self.data.t("stats_title"))
        stats_btn.clicked.connect(lambda: StatsDialog(self.data, parent=self).exec())
        footer.addWidget(stats_btn)

        add_btn = QPushButton("+")
        add_btn.setFont(QFont("Segoe UI", 16, QFont.Bold))
        add_btn.setFixedSize(40, 40)
        add_btn.setToolTip(self.data.t("add_habit"))
        add_btn.setStyleSheet(
            f"QPushButton {{ background: {PRIMARY}; color: white; border: none; border-radius: 20px; }}"
            f"QPushButton:hover {{ background: {PRIMARY_HOVER}; }}"
        )
        add_btn.clicked.connect(self._add_habit)
        footer.addWidget(add_btn)
        self.root_layout.addLayout(footer)

    # ── Build / Refresh ──
    def _build_all(self):
        self._clear_habits()
        groups = sorted(self.data.groups, key=lambda g: g.get("order", 0))
        today_str = self.data.selected_date.strftime("%Y-%m-%d")

        for group in groups:
            gname = group.get("name_zh" if self.data.lang == "zh" else "name_en", "")
            habits = self.data.get_habits_for_group(
                group.get("name_zh", group.get("name_en", ""))
            )

            # Group header
            header = GroupHeader(self.data, group)
            header.clicked.connect(lambda checked, g=group: self._toggle_group(g))
            header.context_menu_requested.connect(self._group_context_menu)
            header.dropped_on.connect(self._on_group_drop)
            self._habit_layout.insertWidget(self._habit_layout.count() - 1, header)
            self._group_headers[gname] = header

            if not group.get("collapsed", False):
                if not habits:
                    # Empty group drop zone
                    drop_zone = QLabel(
                        "  " + ("拖拽习惯到此处" if self.data.lang == "zh" else "Drop habit here")
                    )
                    drop_zone.setFont(QFont("Segoe UI", 10))
                    drop_zone.setStyleSheet(
                        f"QLabel {{ color: {TEXT_SEC}; border: 2px dashed {BORDER}; "
                        f"border-radius: 8px; padding: 16px; background: transparent; }}"
                    )
                    drop_zone.setAcceptDrops(True)
                    def _make_drop_handler(zone, grp_name):
                        def _drop(event):
                            dragged_id = event.mimeData().text()
                            for hh in self.data.habits:
                                if hh["id"] == dragged_id:
                                    hh["group"] = grp_name
                                    self.data.save_habits()
                                    self._refresh_all()
                                    break
                            event.acceptProposedAction()
                        def _drag_enter(event):
                            if event.mimeData().hasText():
                                zone.setStyleSheet(
                                    f"QLabel {{ color: {PRIMARY}; border: 2px dashed {PRIMARY}; "
                                    f"border-radius: 8px; padding: 16px; background: #e8f4fd; }}"
                                )
                                event.acceptProposedAction()
                        def _drag_leave(event):
                            zone.setStyleSheet(
                                f"QLabel {{ color: {TEXT_SEC}; border: 2px dashed {BORDER}; "
                                f"border-radius: 8px; padding: 16px; background: transparent; }}"
                            )
                        zone.dragEnterEvent = _drag_enter
                        zone.dragLeaveEvent = _drag_leave
                        zone.dropEvent = _drop
                        return drop_zone
                    drop_zone = _make_drop_handler(drop_zone, gname)
                    self._habit_layout.insertWidget(self._habit_layout.count() - 1, drop_zone)
                else:
                    for h in habits:
                        row = HabitRow(self.data, h, today_str)
                        row.checkin_toggled.connect(self._on_checkin_toggled)
                        row.context_menu_requested.connect(self._habit_context_menu)
                        row.dropped_on.connect(self._on_drag_drop)
                        self._habit_layout.insertWidget(self._habit_layout.count() - 1, row)
                        self._habit_rows[h["id"]] = row

                add_btn = QPushButton(f"  + {self.data.t('add_habit')}")
                add_btn.setFlat(True)
                add_btn.setFont(QFont("Segoe UI", 11))
                add_btn.setStyleSheet(
                    "QPushButton { color: #605e5c; border: none; text-align: left; padding: 6px 8px; }"
                    "QPushButton:hover { color: #0078d4; }"
                )
                gname_capture = gname
                add_btn.clicked.connect(lambda checked, gn=gname_capture: self._add_habit(gn))
                self._habit_layout.insertWidget(self._habit_layout.count() - 1, add_btn)

        self._update_footer()

    def _clear_habits(self):
        self._habit_rows.clear()
        self._group_headers.clear()
        # Remove all widgets except the stretch
        while self._habit_layout.count() > 1:
            item = self._habit_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _refresh_all(self):
        self._build_all()
        self.week_nav.refresh()

    def _refresh_week_nav_only(self):
        """Refresh just the nav bar dots without rebuilding the whole list."""
        today_str = self.data.selected_date.strftime("%Y-%m-%d")
        for row in self._habit_rows.values():
            row.refresh(today_str)
        self._update_footer()

    def _update_footer(self):
        rate = self.data.week_completion_rate()
        self._footer_label.setText(self.data.t("week_completion") + f": {rate}%")

    # ── Slots ──
    def _on_date_clicked(self, date_str):
        self._refresh_all()

    def _on_checkin_toggled(self, habit_id, date_str):
        self.week_nav.refresh()
        if habit_id in self._habit_rows:
            self._habit_rows[habit_id].refresh(
                self.data.selected_date.strftime("%Y-%m-%d")
            )
        self._update_footer()

    def _on_drag_drop(self, dragged_id, target_id):
        """Handle drag-and-drop reorder. Move dragged habit before target."""
        dragged = next((h for h in self.data.habits if h["id"] == dragged_id), None)
        target = next((h for h in self.data.habits if h["id"] == target_id), None)
        if not dragged or not target or dragged_id == target_id:
            return
        # Move dragged to same group as target
        dragged["group"] = target["group"]
        # Reorder: remove dragged, insert before target
        self.data.habits = [h for h in self.data.habits if h["id"] != dragged_id]
        target_idx = next(i for i, h in enumerate(self.data.habits) if h["id"] == target_id)
        self.data.habits.insert(target_idx, dragged)
        self.data.save_habits()
        self._refresh_all()

    def _toggle_group(self, group):
        group["collapsed"] = not group.get("collapsed", False)
        self.data.save_groups()
        self._refresh_all()

    def _on_group_drop(self, dragged_name, target_name):
        """Reorder groups by drag-and-drop."""
        dragged = next((g for g in self.data.groups
                        if g.get("name_zh") == dragged_name or g.get("name_en") == dragged_name), None)
        target = next((g for g in self.data.groups
                       if g.get("name_zh") == target_name or g.get("name_en") == target_name), None)
        if not dragged or not target or dragged == target:
            return
        # Reorder: move dragged to before target
        self.data.groups = [g for g in self.data.groups if g != dragged]
        target_idx = next(i for i, g in enumerate(self.data.groups) if g == target)
        self.data.groups.insert(target_idx, dragged)
        # Update order field
        for i, g in enumerate(self.data.groups):
            g["order"] = i
        self.data.save_groups()
        self._refresh_all()

    def _group_context_menu(self, group, pos):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: #ffffff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 4px; }"
            "QMenu::item { padding: 8px 28px; color: #1f1f1f; }"
            "QMenu::item:selected { background: #0078d4; color: #ffffff; border-radius: 4px; }"
            "QMenu::separator { height: 1px; background: #e0e0e0; margin: 4px 8px; }"
        )
        edit = menu.addAction(self.data.t("edit_group"))
        add = menu.addAction(self.data.t("add_habit"))
        menu.addSeparator()
        delete = menu.addAction(self.data.t("delete_group"))
        action = menu.exec(pos)
        if action == edit:
            dlg = GroupDialog(self.data, group, parent=self)
            if dlg.exec() == QDialog.Accepted:
                self._refresh_all()
        elif action == add:
            gname = group.get("name_zh", group.get("name_en", ""))
            self._add_habit(gname)
        elif action == delete:
            gname = group.get("name_zh", group.get("name_en", ""))
            habit_count = len(self.data.get_habits_for_group(
                group.get("name_zh", group.get("name_en", ""))))
            msg = self.data.fmt("confirm_delete_group", name=gname)
            if habit_count > 0:
                msg += "\n\n" + (
                    f"该分组下有 {habit_count} 个习惯，将被一并删除！"
                    if self.data.lang == "zh" else
                    f"This group has {habit_count} habit(s) which will also be deleted!"
                )
            reply = QMessageBox.question(self, self.data.t("delete_group"), msg)
            if reply == QMessageBox.Yes:
                self.data.habits = [h for h in self.data.habits
                                    if h.get("group") not in (
                                        group.get("name_zh", ""),
                                        group.get("name_en", ""),
                                    )]
                self.data.groups = [g for g in self.data.groups
                                    if g.get("name_zh") != group.get("name_zh")
                                    and g.get("name_en") != group.get("name_en")]
                self.data.save_habits()
                self.data.save_groups()
                self._refresh_all()

    def _add_habit(self, group_name=None):
        """Add a new habit, optionally pre-selecting a group."""
        dlg = HabitDialog(self.data, parent=self)
        if group_name:
            idx = dlg.group_combo.findText(group_name)
            if idx >= 0:
                dlg.group_combo.setCurrentIndex(idx)
        if dlg.exec() == QDialog.Accepted:
            self._refresh_all()

    def _toggle_language(self):
        self.data.lang = "en" if self.data.lang == "zh" else "zh"
        self.data.settings["lang"] = self.data.lang
        self.data.save_settings()
        self.setWindowTitle(self.data.t("title"))
        self._title_label.setText(self.data.t("title"))
        self._lang_btn.setText(self.data.t("lang"))
        self._refresh_all()

    # ── Context menu ──
    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: #ffffff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 4px; }"
            "QMenu::item { padding: 8px 28px; color: #1f1f1f; }"
            "QMenu::item:selected { background: #0078d4; color: #ffffff; border-radius: 4px; }"
        )
        add_habit = menu.addAction(self.data.t("add_habit"))
        add_group = menu.addAction(self.data.t("add_group"))

        action = menu.exec(event.globalPos())
        if action == add_habit:
            self._add_habit()
        elif action == add_group:
            dlg = GroupDialog(self.data, parent=self)
            if dlg.exec() == QDialog.Accepted:
                self._refresh_all()

    def _habit_context_menu(self, habit, pos):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: #ffffff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 4px; }"
            "QMenu::item { padding: 8px 28px; color: #1f1f1f; }"
            "QMenu::item:selected { background: #0078d4; color: #ffffff; border-radius: 4px; }"
            "QMenu::separator { height: 1px; background: #e0e0e0; margin: 4px 8px; }"
        )
        # Move to group submenu
        move_menu = menu.addMenu("→ " + ("移动到" if self.data.lang == "zh" else "Move to"))
        move_menu.setStyleSheet(
            "QMenu { background: #ffffff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 4px; }"
            "QMenu::item { padding: 8px 28px; color: #1f1f1f; }"
            "QMenu::item:selected { background: #0078d4; color: #ffffff; border-radius: 4px; }"
        )
        for g in self.data.groups:
            gname = g.get("name_zh" if self.data.lang == "zh" else "name_en", "")
            move_menu.addAction(gname)
        menu.addSeparator()
        edit = menu.addAction(self.data.t("edit_habit"))
        up = menu.addAction("↑ " + ("上移" if self.data.lang == "zh" else "Move Up"))
        down = menu.addAction("↓ " + ("下移" if self.data.lang == "zh" else "Move Down"))
        menu.addSeparator()
        delete = menu.addAction(self.data.t("delete_habit"))

        action = menu.exec(pos)
        if action and action.text() in [g.get("name_zh", "") for g in self.data.groups] + [g.get("name_en", "") for g in self.data.groups]:
            # Move to group
            for g in self.data.groups:
                if action.text() in (g.get("name_zh", ""), g.get("name_en", "")):
                    habit["group"] = g.get("name_zh", g.get("name_en", ""))
                    self.data.save_habits()
                    self._refresh_all()
                    return
        elif action == edit:
            dlg = HabitDialog(self.data, habit, parent=self)
            if dlg.exec() == QDialog.Accepted:
                self._refresh_all()
        elif action == up:
            idx = next((i for i, h in enumerate(self.data.habits) if h["id"] == habit["id"]), None)
            if idx is not None and idx > 0:
                self.data.habits[idx], self.data.habits[idx - 1] = self.data.habits[idx - 1], self.data.habits[idx]
                self.data.save_habits()
                self._refresh_all()
        elif action == down:
            idx = next((i for i, h in enumerate(self.data.habits) if h["id"] == habit["id"]), None)
            if idx is not None and idx < len(self.data.habits) - 1:
                self.data.habits[idx], self.data.habits[idx + 1] = self.data.habits[idx + 1], self.data.habits[idx]
                self.data.save_habits()
                self._refresh_all()
        elif action == delete:
            reply = QMessageBox.question(
                self, self.data.t("delete_habit"),
                self.data.fmt("confirm_delete_habit", name=habit.get("name", "")),
            )
            if reply == QMessageBox.Yes:
                self.data.habits = [h for h in self.data.habits if h["id"] != habit["id"]]
                self.data.save_habits()
                self._refresh_all()


# ══════════════════════════════════════════════════════════════════
#  CLI --send-report
# ══════════════════════════════════════════════════════════════════
def _send_report_and_exit():
    tp = POOL_DIR

    try:
        habits = json.loads((tp / "habits.json").read_text(encoding="utf-8"))
    except Exception:
        habits = []
    try:
        settings = json.loads((tp / "settings.json").read_text(encoding="utf-8"))
    except Exception:
        settings = {}

    if not settings.get("bot_enabled", False):
        print("Bot not enabled.")
        return

    lang = settings.get("lang", "zh")
    t = lambda key: TS.get(lang, TS["zh"]).get(key, TS["zh"].get(key, key))

    today_str = date.today().strftime("%Y-%m-%d")
    today_weekday = date.today().strftime("%A")
    today_display = f"{today_str} {today_weekday}"

    done_today = []
    pending_today = []
    for h in habits:
        if today_str in h.get("checkins", []):
            done_today.append(h["name"])
        else:
            pending_today.append(h["name"])

    total = len(habits)
    done_count = len(done_today)
    rate = round(done_count / total * 100) if total > 0 else 0

    lines = [
        f"## 🤖 ATM 今日习惯打卡",
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
        lines.append(f"- {t('bot_no_habits')}")

    message = "\n".join(lines)
    webhook = settings.get("webhook_url", DEFAULT_WEBHOOK)
    payload = json.dumps({"msgtype": "markdown", "markdown": {"content": message}}).encode("utf-8")

    try:
        req = urllib.request.Request(
            webhook, data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            if result.get("errcode") == 0:
                print(f"[{datetime.now()}] Report sent.")
            else:
                print(f"[{datetime.now()}] Failed: {result.get('errmsg')}")
    except Exception as exc:
        print(f"[{datetime.now()}] Error: {exc}")


# ══════════════════════════════════════════════════════════════════
#  Entry
# ══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    if "--send-report" in sys.argv:
        _send_report_and_exit()
        sys.exit(0)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    # Global stylesheet to fix Fusion theme visibility issues
    app.setStyleSheet(
        "QToolTip { color: #1f1f1f; background: #ffffff; border: 1px solid #e0e0e0; }"
        "QMessageBox { background: #ffffff; }"
        "QMessageBox QLabel { color: #1f1f1f; }"
    )
    window = HabitApp()
    window.show()
    sys.exit(app.exec())
