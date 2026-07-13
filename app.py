import json
import os
import sys
import threading
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk


APP_TITLE = "AI 任务管理系统"
TASK_POOL_DIR = "task_pool"
TASKS_JSON = "tasks.json"
PERIODIC_JSON = "periodic_tasks.json"
TASKS_MD = "tasks.md"
BACKGROUND_MD = "user_background.md"
CATEGORIES_JSON = "categories.json"
CATEGORY_RESULTS_MD = "category_results.md"
SETTINGS_JSON = "settings.json"
ICON_PATH = "photo/app_icon.ico"

# ── Fluent Design 配色 ──
FLUENT_BG = "#f0f2f5"
FLUENT_CARD_BG = "#ffffff"
FLUENT_PRIMARY = "#0078d4"
FLUENT_PRIMARY_HOVER = "#106ebe"
FLUENT_TEXT_PRIMARY = "#1f1f1f"
FLUENT_TEXT_SECONDARY = "#605e5c"
FLUENT_SUCCESS = "#107c10"
FLUENT_WARNING = "#ff8c00"
FLUENT_BORDER = "#e0e0e0"
FLUENT_CARD_BORDER = "#ebebeb"

# ── 默认分类 ──
DEFAULT_CATEGORIES = [
    {"name_zh": "重要任务", "name_en": "Important Tasks", "color": "#d13438"},
    {"name_zh": "日常任务", "name_en": "Daily Tasks", "color": "#0078d4"},
]

CATEGORY_COLOR_PALETTE = [
    "#d13438", "#0078d4", "#ff8c00", "#107c10",
    "#881798", "#00b7c3", "#498205", "#e81123",
]

# ── 企业微信 ──
DEFAULT_WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=708bb96a-fd4b-4754-b8fa-c3c02e60fcaf"

# ── 翻译字典 ──
TS = {
    "zh": {
        "window_title": "AI 任务管理系统",
        "font_size_label": "字体大小",
        "lang_toggle": "EN",
        "subtitle": "把任务放进任务池，一键调用 DeepSeek API 结合用户背景和周期任务做智能分类规划。",
        # 用户背景
        "background_frame": "用户背景",
        "background_hint": "填写你的身份、目标、节奏和限制，AI 会据此调整优先级。",
        "save_background": "保存用户背景",
        # 普通任务
        "regular_task_title": "普通任务",
        "regular_task_hint": "每行一个任务。重复任务会自动跳过；也可在右侧分类结果中双击任务完成。",
        "add_to_pool": "添加到任务池",
        "clear_input": "清空输入",
        "tree_done": "完成",
        "tree_task": "任务",
        "toggle_done": "切换完成",
        "delete_selected": "删除选中",
        "clear_pool": "清空任务池",
        "open_folder": "打开文件夹",
        "done_status": "已完成",
        "undone_status": "未完成",
        # 周期性任务
        "periodic_frame": "周期性任务",
        "periodic_hint": "每天/每周/每月会自动刷新；临近周期结束未完成会弹窗提醒。",
        "add_periodic": "添加",
        "periodic_tree_cycle": "周期",
        "periodic_tree_deadline": "截止",
        "periodic_tree_task": "任务",
        "cycle_daily": "每天",
        "cycle_weekly": "每周",
        "cycle_monthly": "每月",
        "deadline_today": "今天",
        # 分类管理
        "category_mgmt_title": "分类管理",
        "add_category": "添加分类",
        "delete_category": "删除分类",
        "category_plan_title": "分类规划结果",
        "category_plan_hint": "AI 根据你定义的分类规划任务。双击某条任务可切换完成状态。",
        "category_empty": "暂无",
        "category_waiting": '等待规划结果...\n请点击左侧"开始 AI 分类规划"。',
        "status_category_added": "已添加分类。",
        "status_category_deleted": "已删除分类。",
        "status_category_exists": "该分类名称已存在。",
        "status_category_min": "至少需要保留 1 个分类。",
        "status_category_loaded": "已读取规划结果：{path}",
        # API 设置
        "api_frame": "DeepSeek API 设置",
        "api_key_label": "API Key",
        "api_model_label": "模型名称",
        "api_hint": "使用 DeepSeek API，规划完成后自动刷新结果。",
        "plan_btn": "开始 AI 分类规划",
        "planning_btn": "AI 规划中…",
        "refresh_result": "刷新规划结果",
        # 企业微信
        "bot_frame": "企业微信机器人",
        "bot_webhook_label": "Webhook URL",
        "bot_enable": "启用每日提醒（06:05 发送）",
        "bot_status_enabled": "机器人已启用，每天 06:05 发送任务提醒。",
        "bot_status_disabled": "机器人已禁用",
        "bot_sent_title": "AI 任务管理系统 - 每日任务提醒",
        "bot_date_label": "日期",
        "bot_pending_tasks": "待完成任务",
        "bot_periodic_reminders": "周期任务提醒",
        "bot_no_tasks": "暂无待办任务",
        "bot_due": "截止",
        "bot_sending": "正在发送企业微信消息…",
        "status_bot_sent": "企业微信消息已发送",
        "status_bot_error": "企业微信消息发送失败：{error}",
        # 状态消息
        "status_task_pool": "任务池：{path}",
        "status_font_changed": "字体大小已调整为 {size}。",
        "status_background_saved": "已保存用户背景：{path}",
        "status_tasks_added": "已添加 {added} 个任务，跳过 {skipped} 个重复任务。",
        "status_regular_toggled": "已更新普通任务完成状态。",
        "status_regular_deleted": "已删除选中任务。",
        "status_pool_cleared": "普通任务池已清空。",
        "status_periodic_skipped": "已跳过重复周期性任务。",
        "status_periodic_added": "已添加周期性任务。",
        "status_periodic_toggled": "已更新周期性任务完成状态。",
        "status_periodic_deleted": "已删除选中周期性任务。",
        "status_category_mismatch": "未能匹配该分类任务，请确认任务名称与任务池一致。",
        "status_category_toggled": "已从分类结果切换{pool}状态：{task} -> {status}",
        "status_plan_complete": "AI 规划完成；移除已完成 {removed_completed} 个，合并重复 {removed_duplicates} 个。",
        "status_planning": "正在调用 DeepSeek API 进行智能规划…",
        "status_api_error": "API 调用失败：{error}",
        "status_loaded": "已读取规划结果：{path}",
        "settings_saved": "设置已保存。",
        # 弹窗
        "dialog_input_task": "请先输入任务。",
        "dialog_clear_confirm": "确定要清空普通任务池吗？",
        "dialog_input_periodic": "请先输入周期性任务。",
        "dialog_pool_empty": "任务池为空，请先添加任务。",
        "dialog_api_error": "DeepSeek API 调用失败：\n{error}",
        "notify_title": "AI 任务管理系统",
        "notify_periodic_warning": "以下周期性任务临近周期结束但尚未完成：\n\n{tasks}",
        # tasks.md 模板
        "tasks_md_title": "# 任务池",
        "tasks_md_updated": "更新时间：{time}",
        "tasks_md_regular": "## 普通任务",
        "tasks_md_periodic": "## 周期性任务",
        "tasks_md_empty": "- 暂无",
        # 周期提醒
        "notify_line": "- [{cycle}，截止 {deadline}] {text}",
        "periodic_regular": "普通任务",
        "periodic_periodic": "周期性任务",
        # API prompt
        "api_system_prompt": "你是一个专业的任务规划助手，擅长根据用户背景将任务分类到用户定义的类别中。请严格按照用户提供的分类和格式要求输出结果，不要添加额外说明。",
        "api_user_prompt": """请根据以下用户背景和任务列表，将所有未完成任务划分到以下分类：

{category_list}

## 用户背景
{background}

## 任务列表
{tasks_md}

## 规划要求
- 根据用户背景中的长期目标、角色责任和近期关键事项判断任务归属分类。
- 考虑任务时限、风险、依赖关系、周期截止时间。
- 必须逐行处理任务列表中的任务：一个输入任务行对应最终结果中的一个独立条目。
- 严禁把多个任务合并、概括或改写成一个上位任务。
- 最终结果中每条任务的冒号前必须保留原任务文本。
- 已完成任务不会出现在任务池中，请只规划当前未完成任务。
- 周期性任务也要参与规划，并在原因中说明它的周期属性。
- 不要遗漏任务。

请严格按照以下格式输出，直接写入文件内容：

{category_format}

如果某个分类没有任务，请写 `- 暂无`。""",
        "api_key_empty": "API Key 不能为空",
        "fallback_background": "暂无用户背景",
        "fallback_tasks": "暂无任务",
    },
    "en": {
        "window_title": "AI Task Manager",
        "font_size_label": "Font Size",
        "lang_toggle": "中文",
        "subtitle": "Drop tasks into the pool, then use DeepSeek API to auto-sort them by your custom categories.",
        "background_frame": "User Profile",
        "background_hint": "Describe your identity, goals, schedule, and constraints. The AI will prioritize accordingly.",
        "save_background": "Save Profile",
        "regular_task_title": "Tasks",
        "regular_task_hint": "One task per line. Duplicates are auto-skipped. Double-click a task in the category result to toggle status.",
        "add_to_pool": "Add to Pool",
        "clear_input": "Clear Input",
        "tree_done": "Done",
        "tree_task": "Task",
        "toggle_done": "Toggle Done",
        "delete_selected": "Delete Selected",
        "clear_pool": "Clear Pool",
        "open_folder": "Open Folder",
        "done_status": "Done",
        "undone_status": "Undone",
        "periodic_frame": "Recurring Tasks",
        "periodic_hint": "Daily/weekly/monthly auto-refresh. A reminder pops up near the end of each cycle.",
        "add_periodic": "Add",
        "periodic_tree_cycle": "Cycle",
        "periodic_tree_deadline": "Deadline",
        "periodic_tree_task": "Task",
        "cycle_daily": "Daily",
        "cycle_weekly": "Weekly",
        "cycle_monthly": "Monthly",
        "deadline_today": "Today",
        "category_mgmt_title": "Category Management",
        "add_category": "Add Category",
        "delete_category": "Delete Category",
        "category_plan_title": "Category Results",
        "category_plan_hint": "AI plans tasks by your custom categories. Double-click a task to toggle its status.",
        "category_empty": "None",
        "category_waiting": 'Waiting for planning...\nClick "Start AI Planning" on the left.',
        "status_category_added": "Category added.",
        "status_category_deleted": "Category deleted.",
        "status_category_exists": "Category name already exists.",
        "status_category_min": "At least 1 category is required.",
        "status_category_loaded": "Results loaded: {path}",
        "api_frame": "DeepSeek API Settings",
        "api_key_label": "API Key",
        "api_model_label": "Model",
        "api_hint": "Uses DeepSeek API. Results refresh automatically after planning.",
        "plan_btn": "Start AI Planning",
        "planning_btn": "Planning…",
        "refresh_result": "Refresh Results",
        "bot_frame": "WeChat Work Bot",
        "bot_webhook_label": "Webhook URL",
        "bot_enable": "Enable Daily Reminder (06:05)",
        "bot_status_enabled": "Bot enabled. Sends daily reminder at 06:05.",
        "bot_status_disabled": "Bot disabled",
        "bot_sent_title": "AI Task Manager - Daily Reminder",
        "bot_date_label": "Date",
        "bot_pending_tasks": "Pending Tasks",
        "bot_periodic_reminders": "Recurring Reminders",
        "bot_no_tasks": "No pending tasks",
        "bot_due": "Due",
        "bot_sending": "Sending WeChat Work message…",
        "status_bot_sent": "WeChat message sent",
        "status_bot_error": "WeChat message failed: {error}",
        "status_task_pool": "Task pool: {path}",
        "status_font_changed": "Font size changed to {size}.",
        "status_background_saved": "Profile saved: {path}",
        "status_tasks_added": "{added} task(s) added, {skipped} duplicate(s) skipped.",
        "status_regular_toggled": "Task done status updated.",
        "status_regular_deleted": "Selected task(s) deleted.",
        "status_pool_cleared": "Task pool cleared.",
        "status_periodic_skipped": "Duplicate recurring task skipped.",
        "status_periodic_added": "Recurring task added.",
        "status_periodic_toggled": "Recurring task done status updated.",
        "status_periodic_deleted": "Selected recurring task(s) deleted.",
        "status_category_mismatch": "Could not match category line to a task. Check the task name matches the pool.",
        "status_category_toggled": "Toggled {pool} task from category: {task} -> {status}",
        "status_plan_complete": "AI planning done. Removed {removed_completed} completed, merged {removed_duplicates} duplicate(s).",
        "status_planning": "Calling DeepSeek API for planning…",
        "status_api_error": "API call failed: {error}",
        "status_loaded": "Results loaded: {path}",
        "settings_saved": "Settings saved.",
        "dialog_input_task": "Please enter at least one task.",
        "dialog_clear_confirm": "Are you sure you want to clear the task pool?",
        "dialog_input_periodic": "Please enter a recurring task.",
        "dialog_pool_empty": "Task pool is empty. Please add tasks first.",
        "dialog_api_error": "DeepSeek API call failed:\n{error}",
        "notify_title": "AI Task Manager",
        "notify_periodic_warning": "The following recurring tasks are due soon but not yet completed:\n\n{tasks}",
        "tasks_md_title": "# Task Pool",
        "tasks_md_updated": "Updated: {time}",
        "tasks_md_regular": "## Regular Tasks",
        "tasks_md_periodic": "## Recurring Tasks",
        "tasks_md_empty": "- None",
        "notify_line": "- [{cycle}, due {deadline}] {text}",
        "periodic_regular": "Regular",
        "periodic_periodic": "Recurring",
        "api_system_prompt": "You are a professional task planning assistant. Categorize tasks into the user-defined categories based on their profile. Output results strictly in the requested format without extra commentary.",
        "api_user_prompt": """Please categorize all unfinished tasks into the following categories based on the user profile and task list:

{category_list}

## User Profile
{background}

## Task List
{tasks_md}

## Planning Requirements
- Determine which category each task belongs to based on the user's long-term goals, role responsibilities, and key priorities.
- Consider deadlines, risks, dependencies, and cycle end dates.
- Process every task line from the task list: one input line = one independent output entry.
- Do NOT merge, generalize, or rewrite multiple tasks into a single parent task.
- Preserve the original task text before the colon in each output line.
- Only plan unfinished tasks; completed tasks are excluded.
- Recurring tasks must be included with their cycle attribute noted in the reason.
- Do not omit any task.

Output strictly in the following format:

{category_format}

If a category has no tasks, write `- None`.""",
        "api_key_empty": "API Key cannot be empty",
        "fallback_background": "No user profile",
        "fallback_tasks": "No tasks",
    },
}


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def resource_path(relative_path: str) -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative_path
    return Path(__file__).resolve().parent / relative_path


BASE_DIR = app_dir()
POOL_DIR = BASE_DIR / TASK_POOL_DIR
TASKS_JSON_PATH = POOL_DIR / TASKS_JSON
PERIODIC_JSON_PATH = POOL_DIR / PERIODIC_JSON
TASKS_MD_PATH = POOL_DIR / TASKS_MD
BACKGROUND_PATH = POOL_DIR / BACKGROUND_MD
CATEGORIES_PATH = POOL_DIR / CATEGORIES_JSON
CATEGORY_RESULTS_PATH = POOL_DIR / CATEGORY_RESULTS_MD
SETTINGS_PATH = POOL_DIR / SETTINGS_JSON


class TaskManagerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.lang = "zh"
        self.title(self.t("window_title"))
        self.configure(bg=FLUENT_BG)
        self.set_window_icon()
        self.geometry("1220x760")
        self.minsize(1080, 700)

        POOL_DIR.mkdir(parents=True, exist_ok=True)
        self.tasks = self.load_tasks()
        self.periodic_tasks = self.load_periodic_tasks()
        self.categories = self.load_categories()
        self.api_key_var = tk.StringVar(value="")
        self.api_model_var = tk.StringVar(value="deepseek-chat")
        self.api_model_options = ["deepseek-chat", "deepseek-reasoner"]
        self.periodic_cycle_var = tk.StringVar(value=self.t("cycle_daily"))
        self.font_size = tk.IntVar(value=12)
        self.status_var = tk.StringVar(value=self._fmt("status_task_pool", path=POOL_DIR))
        self._lang_widgets = []

        # 企业微信
        self.bot_enabled = tk.BooleanVar(value=False)
        self.webhook_url_var = tk.StringVar(value=DEFAULT_WEBHOOK_URL)
        self._last_bot_date = ""
        self._bot_after_id = None

        self._load_settings()
        self.configure_style()
        self.build_ui()
        self.load_background()
        self.reset_periodic_tasks_if_needed()
        self.refresh_task_list()
        self.refresh_periodic_list()
        self.load_category_results()
        self.after(500, self.check_periodic_notifications)
        self.after(5000, self._schedule_bot_check)

    # ══════════════════════════════════════════════════════════════
    #  国际化
    # ══════════════════════════════════════════════════════════════
    def t(self, key: str) -> str:
        return TS.get(self.lang, TS["zh"]).get(key, TS["zh"].get(key, key))

    def _fmt(self, key: str, **kwargs) -> str:
        return self.t(key).format(**kwargs)

    def toggle_language(self):
        self.lang = "en" if self.lang == "zh" else "zh"
        self.title(self.t("window_title"))
        self.periodic_cycle_var.set(self.t("cycle_daily"))
        self.apply_language()
        self._refresh_tree_headings()
        self._refresh_combo_values()
        self._rebuild_category_cards()
        self.refresh_task_list()
        self.refresh_periodic_list()
        self.load_category_results()
        self.status_var.set(self._fmt("status_task_pool", path=POOL_DIR))

    def apply_language(self):
        for widget, prop, key in self._lang_widgets:
            try:
                if prop == "text":
                    widget.configure(text=self.t(key))
                elif prop == "label":
                    widget.configure(text=self.t(key))
            except (tk.TclError, AttributeError):
                pass

    def _reg(self, widget, prop: str, key: str):
        self._lang_widgets.append((widget, prop, key))
        return widget

    # ══════════════════════════════════════════════════════════════
    #  设置持久化
    # ══════════════════════════════════════════════════════════════
    def _load_settings(self):
        try:
            if SETTINGS_PATH.exists():
                data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
                if data.get("api_key"):
                    self.api_key_var.set(data["api_key"])
                if data.get("api_model"):
                    self.api_model_var.set(data["api_model"])
                if data.get("webhook_url"):
                    self.webhook_url_var.set(data["webhook_url"])
                if "bot_enabled" in data:
                    self.bot_enabled.set(data["bot_enabled"])
        except (json.JSONDecodeError, OSError):
            pass

    def _save_settings(self):
        data = {
            "api_key": self.api_key_var.get().strip(),
            "api_model": self.api_model_var.get().strip(),
            "webhook_url": self.webhook_url_var.get().strip(),
            "bot_enabled": self.bot_enabled.get(),
        }
        SETTINGS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # ══════════════════════════════════════════════════════════════
    #  分类管理
    # ══════════════════════════════════════════════════════════════
    def load_categories(self):
        if not CATEGORIES_PATH.exists():
            self.save_categories(DEFAULT_CATEGORIES)
            return [dict(c) for c in DEFAULT_CATEGORIES]
        try:
            data = json.loads(CATEGORIES_PATH.read_text(encoding="utf-8"))
            if not data or not isinstance(data, list):
                return [dict(c) for c in DEFAULT_CATEGORIES]
            for c in data:
                if "name_zh" not in c:
                    c["name_zh"] = c.get("name", "未命名")
                if "name_en" not in c:
                    c["name_en"] = c.get("name", "Unnamed")
                if "color" not in c:
                    c["color"] = "#0078d4"
            return data
        except (json.JSONDecodeError, OSError):
            return [dict(c) for c in DEFAULT_CATEGORIES]

    def save_categories(self, categories=None):
        cats = categories if categories is not None else self.categories
        CATEGORIES_PATH.write_text(json.dumps(cats, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_category_names(self):
        key = "name_zh" if self.lang == "zh" else "name_en"
        return [c[key] for c in self.categories]

    def _next_category_color(self):
        return CATEGORY_COLOR_PALETTE[len(self.categories) % len(CATEGORY_COLOR_PALETTE)]

    # ══════════════════════════════════════════════════════════════
    #  图标 & 样式
    # ══════════════════════════════════════════════════════════════
    def set_window_icon(self):
        icon = resource_path(ICON_PATH)
        if icon.exists():
            try:
                self.iconbitmap(str(icon))
            except tk.TclError:
                pass

    def configure_style(self):
        size = self.font_size.get()
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", font=("Segoe UI", size))
        style.configure("TFrame", background=FLUENT_BG)
        style.configure("Card.TFrame", background=FLUENT_CARD_BG, relief="flat")
        style.configure("TLabelframe", background=FLUENT_CARD_BG, relief="solid", borderwidth=1)
        style.configure("TLabelframe.Label",
                        font=("Segoe UI", size, "bold"),
                        background=FLUENT_CARD_BG,
                        foreground=FLUENT_TEXT_PRIMARY)
        style.configure("TLabel", font=("Segoe UI", size), background=FLUENT_BG, foreground=FLUENT_TEXT_PRIMARY)
        style.configure("Card.TLabel", font=("Segoe UI", size), background=FLUENT_CARD_BG, foreground=FLUENT_TEXT_PRIMARY)
        style.configure("Title.TLabel", font=("Segoe UI", size + 8, "bold"), background=FLUENT_BG, foreground=FLUENT_TEXT_PRIMARY)
        style.configure("Subtitle.TLabel", font=("Segoe UI", size), foreground=FLUENT_TEXT_SECONDARY, background=FLUENT_BG)
        style.configure("Primary.TButton", font=("Segoe UI", size, "bold"), padding=(16, 8))
        style.configure("TButton", font=("Segoe UI", size), padding=(12, 6))
        style.configure("Lang.TButton", font=("Segoe UI", size - 1), padding=(8, 4))
        style.configure("Treeview", font=("Segoe UI", size), rowheight=size + 16,
                        background=FLUENT_CARD_BG, fieldbackground=FLUENT_CARD_BG,
                        foreground=FLUENT_TEXT_PRIMARY)
        style.configure("Treeview.Heading", font=("Segoe UI", size, "bold"))
        style.configure("TCombobox", font=("Segoe UI", size), padding=(6, 4))
        style.configure("TEntry", font=("Segoe UI", size), padding=(6, 4))
        style.configure("TCheckbutton", font=("Segoe UI", size), background=FLUENT_CARD_BG,
                        foreground=FLUENT_TEXT_PRIMARY)

    # ══════════════════════════════════════════════════════════════
    #  UI 构建
    # ══════════════════════════════════════════════════════════════
    def build_ui(self):
        root = ttk.Frame(self, padding=(24, 18, 24, 18))
        root.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(root)
        header.pack(fill=tk.X, pady=(0, 14))

        # 右上角：语言切换 + 字体缩放
        font_controls = ttk.Frame(header)
        font_controls.pack(side=tk.RIGHT, anchor=tk.NE)
        ttk.Button(font_controls, text="A-", command=lambda: self.change_font_size(-1)).pack(side=tk.RIGHT)
        ttk.Button(font_controls, text="A+", command=lambda: self.change_font_size(1)).pack(side=tk.RIGHT, padx=(6, 0))
        self._reg(
            ttk.Label(font_controls, text=self.t("font_size_label"), style="Subtitle.TLabel"),
            "text", "font_size_label",
        ).pack(side=tk.RIGHT, padx=(0, 6))
        lang_btn = ttk.Button(
            font_controls, text=self.t("lang_toggle"), style="Lang.TButton",
            command=self.toggle_language,
        )
        lang_btn.pack(side=tk.RIGHT, padx=(10, 0))
        self.lang_btn = lang_btn

        ttk.Label(header, text=self.t("window_title"), style="Title.TLabel").pack(anchor=tk.W)
        self._reg(
            ttk.Label(header, text=self.t("subtitle"), style="Subtitle.TLabel"),
            "text", "subtitle",
        ).pack(anchor=tk.W, pady=(4, 0))

        # 分隔线
        sep = ttk.Frame(root, height=1, style="TFrame")
        sep.pack(fill=tk.X, pady=(0, 14))

        body = ttk.PanedWindow(root, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(body, style="Card.TFrame")
        right = ttk.Frame(body, style="Card.TFrame", padding=14)
        body.add(left, weight=1)
        body.add(right, weight=2)

        task_panel = self.build_scrollable_panel(left)
        self.build_task_panel(task_panel)
        self.build_category_panel(right)

        footer = ttk.Frame(root)
        footer.pack(fill=tk.X, pady=(12, 0))
        ttk.Label(footer, textvariable=self.status_var, style="Subtitle.TLabel").pack(side=tk.LEFT)

    def build_scrollable_panel(self, parent):
        canvas = tk.Canvas(parent, bg=FLUENT_CARD_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
        content = ttk.Frame(canvas, style="Card.TFrame", padding=14)
        window_id = canvas.create_window((0, 0), window=content, anchor=tk.NW)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def update_scroll_region(_event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def update_content_width(event):
            canvas.itemconfigure(window_id, width=event.width)

        def on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        content.bind("<Configure>", update_scroll_region)
        canvas.bind("<Configure>", update_content_width)
        canvas.bind("<Enter>", lambda _e: canvas.bind_all("<MouseWheel>", on_mousewheel))
        canvas.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))
        return content

    def build_task_panel(self, parent):
        # 用户背景
        self.background_frame_lf = self._reg(
            ttk.LabelFrame(parent, text=self.t("background_frame"), padding=10),
            "text", "background_frame",
        )
        self.background_frame_lf.pack(fill=tk.X, pady=(0, 12))
        self._reg(
            ttk.Label(self.background_frame_lf, text=self.t("background_hint"), style="Card.TLabel"),
            "text", "background_hint",
        ).pack(anchor=tk.W, pady=(0, 6))
        self.background_input = tk.Text(
            self.background_frame_lf, height=4, wrap=tk.WORD,
            font=("Segoe UI", self.font_size.get()), relief=tk.SOLID, bd=1,
            bg=FLUENT_CARD_BG, fg=FLUENT_TEXT_PRIMARY,
        )
        self.background_input.pack(fill=tk.X)
        self._reg(
            ttk.Button(self.background_frame_lf, text=self.t("save_background"), command=self.save_background),
            "text", "save_background",
        ).pack(anchor=tk.E, pady=(8, 0))

        # 普通任务
        ttk.Label(parent, text=self.t("regular_task_title"), style="Card.TLabel",
                  font=("Segoe UI", 13, "bold")).pack(anchor=tk.W)
        self._reg(
            ttk.Label(parent, text=self.t("regular_task_hint"), style="Card.TLabel"),
            "text", "regular_task_hint",
        ).pack(anchor=tk.W, pady=(4, 8))

        self.task_input = tk.Text(
            parent, height=3, wrap=tk.WORD,
            font=("Segoe UI", self.font_size.get()), relief=tk.SOLID, bd=1,
            bg=FLUENT_CARD_BG, fg=FLUENT_TEXT_PRIMARY,
        )
        self.task_input.pack(fill=tk.X)

        add_row = ttk.Frame(parent, style="Card.TFrame")
        add_row.pack(fill=tk.X, pady=8)
        self._reg(
            ttk.Button(add_row, text=self.t("add_to_pool"), style="Primary.TButton", command=self.add_tasks),
            "text", "add_to_pool",
        ).pack(side=tk.LEFT)
        self._reg(
            ttk.Button(add_row, text=self.t("clear_input"), command=lambda: self.task_input.delete("1.0", tk.END)),
            "text", "clear_input",
        ).pack(side=tk.LEFT, padx=(8, 0))

        list_frame = ttk.Frame(parent, style="Card.TFrame")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(6, 8))
        self.task_tree = ttk.Treeview(
            list_frame, columns=("done", "task"), show="headings", height=6, selectmode="extended",
        )
        self.task_tree.heading("done", text=self.t("tree_done"))
        self.task_tree.heading("task", text=self.t("tree_task"))
        self.task_tree.column("done", width=62, anchor=tk.CENTER, stretch=False)
        self.task_tree.column("task", width=330, anchor=tk.W)
        self.task_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.task_tree.bind("<Double-1>", lambda _e: self.toggle_selected_tasks())
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.task_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.task_tree.configure(yscrollcommand=scrollbar.set)

        manage_row = ttk.Frame(parent, style="Card.TFrame")
        manage_row.pack(fill=tk.X)
        self._reg(
            ttk.Button(manage_row, text=self.t("toggle_done"), command=self.toggle_selected_tasks),
            "text", "toggle_done",
        ).pack(side=tk.LEFT)
        self._reg(
            ttk.Button(manage_row, text=self.t("delete_selected"), command=self.delete_selected),
            "text", "delete_selected",
        ).pack(side=tk.LEFT, padx=(8, 0))
        self._reg(
            ttk.Button(manage_row, text=self.t("clear_pool"), command=self.clear_tasks),
            "text", "clear_pool",
        ).pack(side=tk.LEFT, padx=(8, 0))
        self._reg(
            ttk.Button(manage_row, text=self.t("open_folder"), command=self.open_pool_folder),
            "text", "open_folder",
        ).pack(side=tk.RIGHT)

        self.build_periodic_panel(parent)
        self.build_category_management(parent)

        # API 设置
        self.api_frame_lf = self._reg(
            ttk.LabelFrame(parent, text=self.t("api_frame"), padding=10),
            "text", "api_frame",
        )
        self.api_frame_lf.pack(fill=tk.X, pady=(14, 0))
        self._reg(
            ttk.Label(self.api_frame_lf, text=self.t("api_key_label"), style="Card.TLabel"),
            "text", "api_key_label",
        ).pack(anchor=tk.W)
        self.api_key_entry = ttk.Entry(self.api_frame_lf, textvariable=self.api_key_var, show="*")
        self.api_key_entry.pack(fill=tk.X)
        self._reg(
            ttk.Label(self.api_frame_lf, text=self.t("api_model_label"), style="Card.TLabel"),
            "text", "api_model_label",
        ).pack(anchor=tk.W, pady=(8, 0))
        self.api_model_combo = ttk.Combobox(
            self.api_frame_lf, textvariable=self.api_model_var,
            values=self.api_model_options, state="readonly", width=30,
        )
        self.api_model_combo.pack(fill=tk.X)
        self._reg(
            ttk.Label(self.api_frame_lf, text=self.t("api_hint"), style="Card.TLabel"),
            "text", "api_hint",
        ).pack(anchor=tk.W, pady=(6, 0))

        self.plan_btn = self._reg(
            ttk.Button(parent, text=self.t("plan_btn"), style="Primary.TButton", command=self.plan_with_deepseek),
            "text", "plan_btn",
        )
        self.plan_btn.pack(fill=tk.X, pady=(14, 0))
        self._reg(
            ttk.Button(parent, text=self.t("refresh_result"), command=self.load_category_results),
            "text", "refresh_result",
        ).pack(fill=tk.X, pady=(8, 0))

        # 企业微信机器人
        self.build_bot_panel(parent)

    def build_periodic_panel(self, parent):
        self.periodic_frame_lf = self._reg(
            ttk.LabelFrame(parent, text=self.t("periodic_frame"), padding=10),
            "text", "periodic_frame",
        )
        self.periodic_frame_lf.pack(fill=tk.BOTH, expand=True, pady=(12, 0))
        self._reg(
            ttk.Label(self.periodic_frame_lf, text=self.t("periodic_hint"), style="Card.TLabel"),
            "text", "periodic_hint",
        ).pack(anchor=tk.W)

        row = ttk.Frame(self.periodic_frame_lf, style="Card.TFrame")
        row.pack(fill=tk.X, pady=(8, 6))
        self.periodic_input = ttk.Entry(row)
        self.periodic_input.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.periodic_combo = ttk.Combobox(
            row, textvariable=self.periodic_cycle_var,
            values=[self.t("cycle_daily"), self.t("cycle_weekly"), self.t("cycle_monthly")],
            width=8, state="readonly",
        )
        self.periodic_combo.pack(side=tk.LEFT, padx=(8, 0))
        self._reg(
            ttk.Button(row, text=self.t("add_periodic"), command=self.add_periodic_task),
            "text", "add_periodic",
        ).pack(side=tk.LEFT, padx=(8, 0))

        tree_frame = ttk.Frame(self.periodic_frame_lf, style="Card.TFrame")
        tree_frame.pack(fill=tk.BOTH, expand=True)
        self.periodic_tree = ttk.Treeview(
            tree_frame, columns=("done", "cycle", "deadline", "task"),
            show="headings", height=5, selectmode="extended",
        )
        self.periodic_tree.heading("done", text=self.t("tree_done"))
        self.periodic_tree.heading("cycle", text=self.t("periodic_tree_cycle"))
        self.periodic_tree.heading("deadline", text=self.t("periodic_tree_deadline"))
        self.periodic_tree.heading("task", text=self.t("periodic_tree_task"))
        self.periodic_tree.column("done", width=62, anchor=tk.CENTER, stretch=False)
        self.periodic_tree.column("cycle", width=58, anchor=tk.CENTER, stretch=False)
        self.periodic_tree.column("deadline", width=78, anchor=tk.CENTER, stretch=False)
        self.periodic_tree.column("task", width=250, anchor=tk.W)
        self.periodic_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.periodic_tree.bind("<Double-1>", lambda _e: self.toggle_selected_periodic_tasks())
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.periodic_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.periodic_tree.configure(yscrollcommand=scrollbar.set)

        actions = ttk.Frame(self.periodic_frame_lf, style="Card.TFrame")
        actions.pack(fill=tk.X, pady=(6, 0))
        self._reg(
            ttk.Button(actions, text=self.t("toggle_done"), command=self.toggle_selected_periodic_tasks),
            "text", "toggle_done",
        ).pack(side=tk.LEFT)
        self._reg(
            ttk.Button(actions, text=self.t("delete_selected"), command=self.delete_selected_periodic_tasks),
            "text", "delete_selected",
        ).pack(side=tk.LEFT, padx=(8, 0))

    def build_category_management(self, parent):
        """分类管理 UI（左侧面板）"""
        self._cat_mgmt_lf = self._reg(
            ttk.LabelFrame(parent, text=self.t("category_mgmt_title"), padding=10),
            "text", "category_mgmt_title",
        )
        self._cat_mgmt_lf.pack(fill=tk.X, pady=(12, 0))

        cat_row = ttk.Frame(self._cat_mgmt_lf, style="Card.TFrame")
        cat_row.pack(fill=tk.X, pady=(0, 6))
        self._category_entry = ttk.Entry(cat_row)
        self._category_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._reg(
            ttk.Button(cat_row, text=self.t("add_category"), command=self._add_category),
            "text", "add_category",
        ).pack(side=tk.LEFT, padx=(8, 0))

        self._category_listbox = tk.Listbox(
            self._cat_mgmt_lf, height=4,
            font=("Segoe UI", self.font_size.get()),
            relief=tk.SOLID, bd=1, bg=FLUENT_CARD_BG, fg=FLUENT_TEXT_PRIMARY,
        )
        self._category_listbox.pack(fill=tk.X, pady=(0, 6))
        self._refresh_category_listbox()

        self._reg(
            ttk.Button(self._cat_mgmt_lf, text=self.t("delete_category"), command=self._delete_category),
            "text", "delete_category",
        ).pack(anchor=tk.E)

    def build_bot_panel(self, parent):
        """企业微信机器人设置 UI"""
        self._bot_frame_lf = self._reg(
            ttk.LabelFrame(parent, text=self.t("bot_frame"), padding=10),
            "text", "bot_frame",
        )
        self._bot_frame_lf.pack(fill=tk.X, pady=(14, 0))

        bot_check = ttk.Checkbutton(
            self._bot_frame_lf, text=self.t("bot_enable"),
            variable=self.bot_enabled, command=self._on_bot_toggle,
        )
        bot_check.pack(anchor=tk.W)
        self._reg(bot_check, "text", "bot_enable")

        ttk.Label(self._bot_frame_lf, text=self.t("bot_webhook_label"), style="Card.TLabel").pack(anchor=tk.W, pady=(6, 2))
        ttk.Entry(self._bot_frame_lf, textvariable=self.webhook_url_var).pack(fill=tk.X)

        self._bot_status_label = ttk.Label(
            self._bot_frame_lf,
            text=self.t("bot_status_disabled") if not self.bot_enabled.get() else self.t("bot_status_enabled"),
            style="Card.TLabel",
        )
        self._bot_status_label.pack(anchor=tk.W, pady=(4, 0))

    def build_category_panel(self, parent):
        """分类结果面板（右侧）"""
        ttk.Label(parent, text=self.t("category_plan_title"), style="Card.TLabel",
                  font=("Segoe UI", 13, "bold")).pack(anchor=tk.W)
        self._reg(
            ttk.Label(parent, text=self.t("category_plan_hint"), style="Card.TLabel"),
            "text", "category_plan_hint",
        ).pack(anchor=tk.W, pady=(4, 10))

        self._cat_canvas = tk.Canvas(parent, bg=FLUENT_CARD_BG, highlightthickness=0)
        self._cat_scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self._cat_canvas.yview)
        self._cat_content = ttk.Frame(self._cat_canvas, style="Card.TFrame")
        self._cat_window_id = self._cat_canvas.create_window((0, 0), window=self._cat_content, anchor=tk.NW)
        self._cat_canvas.configure(yscrollcommand=self._cat_scrollbar.set)
        self._cat_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._cat_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def _cat_configure(event):
            self._cat_canvas.configure(scrollregion=self._cat_canvas.bbox("all"))

        def _cat_resize(event):
            self._cat_canvas.itemconfigure(self._cat_window_id, width=event.width - 4)

        def _cat_mousewheel(event):
            self._cat_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        self._cat_content.bind("<Configure>", _cat_configure)
        self._cat_canvas.bind("<Configure>", _cat_resize)
        self._cat_canvas.bind("<Enter>", lambda _e: self._cat_canvas.bind_all("<MouseWheel>", _cat_mousewheel))
        self._cat_canvas.bind("<Leave>", lambda _e: self._cat_canvas.unbind_all("<MouseWheel>"))

        self._category_cards = {}
        self._rebuild_category_cards()

    def _rebuild_category_cards(self):
        for info in getattr(self, "_category_cards", {}).values():
            info["frame"].destroy()
        self._category_cards = {}

        cat_names = self.get_category_names()
        if not cat_names:
            placeholder = tk.Label(
                self._cat_content, text=self.t("category_empty"),
                bg=FLUENT_CARD_BG, fg=FLUENT_TEXT_SECONDARY,
                font=("Segoe UI", self.font_size.get()),
            )
            placeholder.pack(pady=20)
            self._category_cards["_placeholder"] = {"frame": placeholder, "text": None}
            return

        for idx, (cat_data, cat_name) in enumerate(zip(self.categories, cat_names)):
            color = cat_data.get("color", self._next_category_color())
            card = tk.Frame(
                self._cat_content, bg=FLUENT_CARD_BG,
                highlightthickness=1, highlightbackground=FLUENT_CARD_BORDER,
            )
            card.pack(fill=tk.X, pady=(0, 10))

            header = tk.Frame(card, bg=color, height=32)
            header.pack(fill=tk.X)
            header.pack_propagate(False)
            tk.Label(
                header, text=cat_name, bg=color, fg="#ffffff",
                font=("Segoe UI", self.font_size.get(), "bold"),
                anchor=tk.W, padx=12,
            ).pack(fill=tk.BOTH, expand=True)

            text_box = tk.Text(
                card, wrap=tk.WORD, font=("Segoe UI", self.font_size.get()),
                relief=tk.FLAT, bg=FLUENT_CARD_BG, fg=FLUENT_TEXT_PRIMARY,
                padx=12, pady=8, height=5,
            )
            text_box.pack(fill=tk.BOTH, expand=True)
            text_box.bind("<Double-1>", lambda e, box=None: self.toggle_task_from_category_line(e.widget, e))
            self._category_cards[cat_name] = {"frame": card, "text": text_box}

    # ══════════════════════════════════════════════════════════════
    #  分类管理操作
    # ══════════════════════════════════════════════════════════════
    def _refresh_category_listbox(self):
        self._category_listbox.delete(0, tk.END)
        for name in self.get_category_names():
            self._category_listbox.insert(tk.END, name)

    def _add_category(self):
        name = self._category_entry.get().strip()
        if not name:
            return
        key = "name_zh" if self.lang == "zh" else "name_en"
        current_names = [c.get(key, "") for c in self.categories]
        if name in current_names:
            self.status_var.set(self.t("status_category_exists"))
            return
        if self.lang == "zh":
            self.categories.append({"name_zh": name, "name_en": name, "color": self._next_category_color()})
        else:
            self.categories.append({"name_zh": name, "name_en": name, "color": self._next_category_color()})
        self.save_categories()
        self._category_entry.delete(0, tk.END)
        self._refresh_category_listbox()
        self._rebuild_category_cards()
        self.load_category_results()
        self.status_var.set(self.t("status_category_added"))

    def _delete_category(self):
        if len(self.categories) <= 1:
            self.status_var.set(self.t("status_category_min"))
            return
        selection = self._category_listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        if idx < len(self.categories):
            del self.categories[idx]
            self.save_categories()
            self._refresh_category_listbox()
            self._rebuild_category_cards()
            self.load_category_results()
            self.status_var.set(self.t("status_category_deleted"))

    # ══════════════════════════════════════════════════════════════
    #  字体缩放
    # ══════════════════════════════════════════════════════════════
    def change_font_size(self, delta):
        next_size = max(10, min(22, self.font_size.get() + delta))
        self.font_size.set(next_size)
        self.apply_font_size()

    def apply_font_size(self):
        size = self.font_size.get()
        self.configure_style()
        for widget in self.all_children(self):
            if isinstance(widget, tk.Text):
                widget.configure(font=("Segoe UI", size))
            elif isinstance(widget, tk.Label):
                widget.configure(font=("Segoe UI", size, "normal"))
        self._rebuild_category_cards()
        self.update_idletasks()
        self.status_var.set(self._fmt("status_font_changed", size=size))

    def all_children(self, widget):
        children = widget.winfo_children()
        for child in children:
            yield child
            yield from self.all_children(child)

    # ══════════════════════════════════════════════════════════════
    #  周期标签辅助
    # ══════════════════════════════════════════════════════════════
    def _cycle_labels(self):
        return {
            "daily": self.t("cycle_daily"),
            "weekly": self.t("cycle_weekly"),
            "monthly": self.t("cycle_monthly"),
        }

    def _cycle_values(self):
        labels = self._cycle_labels()
        return {v: k for k, v in labels.items()}

    def _cycle_label(self, cycle: str) -> str:
        return self._cycle_labels().get(cycle, self.t("cycle_daily"))

    def _refresh_tree_headings(self):
        self.task_tree.heading("done", text=self.t("tree_done"))
        self.task_tree.heading("task", text=self.t("tree_task"))
        self.periodic_tree.heading("done", text=self.t("tree_done"))
        self.periodic_tree.heading("cycle", text=self.t("periodic_tree_cycle"))
        self.periodic_tree.heading("deadline", text=self.t("periodic_tree_deadline"))
        self.periodic_tree.heading("task", text=self.t("periodic_tree_task"))

    def _refresh_combo_values(self):
        self.periodic_combo.configure(values=[
            self.t("cycle_daily"), self.t("cycle_weekly"), self.t("cycle_monthly"),
        ])

    # ══════════════════════════════════════════════════════════════
    #  任务持久化
    # ══════════════════════════════════════════════════════════════
    def load_tasks(self):
        if not TASKS_JSON_PATH.exists():
            return []
        try:
            data = json.loads(TASKS_JSON_PATH.read_text(encoding="utf-8"))
            tasks = []
            for item in data:
                if isinstance(item, str):
                    text = item.strip()
                    if text:
                        tasks.append({"text": text, "completed": False})
                elif isinstance(item, dict) and item.get("text"):
                    tasks.append({"text": item["text"].strip(), "completed": bool(item.get("completed", False))})
            return tasks
        except (json.JSONDecodeError, OSError):
            return []

    def load_periodic_tasks(self):
        if not PERIODIC_JSON_PATH.exists():
            return []
        try:
            data = json.loads(PERIODIC_JSON_PATH.read_text(encoding="utf-8"))
            tasks = []
            valid_cycles = {"daily", "weekly", "monthly"}
            for item in data:
                if isinstance(item, dict) and item.get("text"):
                    cycle = item.get("cycle", "daily")
                    if cycle not in valid_cycles:
                        cycle = "daily"
                    tasks.append({
                        "id": item.get("id") or self.new_task_id(),
                        "text": item["text"].strip(),
                        "cycle": cycle,
                        "completed": bool(item.get("completed", False)),
                        "last_reset": item.get("last_reset") or self.current_cycle_key(cycle),
                        "last_notified": item.get("last_notified", ""),
                    })
            return tasks
        except (json.JSONDecodeError, OSError):
            return []

    def save_tasks(self):
        TASKS_JSON_PATH.write_text(json.dumps(self.tasks, ensure_ascii=False, indent=2), encoding="utf-8")
        PERIODIC_JSON_PATH.write_text(json.dumps(self.periodic_tasks, ensure_ascii=False, indent=2), encoding="utf-8")

    def write_tasks_md(self):
        normal_tasks = self.unique_texts(task["text"] for task in self.tasks if not task.get("completed"))
        periodic_tasks = self.unique_texts(task["text"] for task in self.periodic_tasks if not task.get("completed"))
        lines = [
            self.t("tasks_md_title"), "",
            self._fmt("tasks_md_updated", time=datetime.now().strftime('%Y-%m-%d %H:%M:%S')), "",
        ]
        lines.append(self.t("tasks_md_regular"))
        lines.extend(f"- {task}" for task in normal_tasks)
        if not normal_tasks:
            lines.append(self.t("tasks_md_empty"))
        lines.extend(["", self.t("tasks_md_periodic")])
        lines.extend(f"- {task}" for task in periodic_tasks)
        if not periodic_tasks:
            lines.append(self.t("tasks_md_empty"))
        TASKS_MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def load_background(self):
        if BACKGROUND_PATH.exists():
            self.background_input.insert("1.0", BACKGROUND_PATH.read_text(encoding="utf-8", errors="replace"))

    def save_background(self):
        content = self.background_input.get("1.0", tk.END).strip()
        BACKGROUND_PATH.write_text((content or self.t("fallback_background")) + "\n", encoding="utf-8")
        self.status_var.set(self._fmt("status_background_saved", path=BACKGROUND_PATH))

    # ══════════════════════════════════════════════════════════════
    #  任务文本匹配
    # ══════════════════════════════════════════════════════════════
    def normalize_task_text(self, text):
        return "".join(text.lower().split())

    def _is_placeholder_text(self, text):
        placeholders = ["暂无", "None", "等待规划结果", "Waiting for planning",
                        "Start AI Planning", "开始 AI 分类规划"]
        for p in placeholders:
            if p in text:
                return True
        return False

    def extract_task_text_from_line(self, line):
        text = line.strip()
        if not text or self._is_placeholder_text(text):
            return ""
        text = text.lstrip("-•* ").strip()
        for marker in ("[x]", "[X]", "[ ]", self.t("done_status"), self.t("undone_status"), "已完成", "未完成"):
            if text.startswith(marker):
                text = text[len(marker):].strip()
        if text.startswith("[") and "]" in text:
            text = text.split("]", 1)[1].strip()
        for separator in ("：", ":", " - ", " -- "):
            if separator in text:
                text = text.split(separator, 1)[0].strip()
                break
        return text.strip()

    def match_task_by_text(self, text):
        target = self.normalize_task_text(text)
        if not target:
            return None, None
        pools = (("regular", self.tasks), ("periodic", self.periodic_tasks))
        for pool_name, tasks in pools:
            for task in tasks:
                if self.normalize_task_text(task["text"]) == target:
                    return pool_name, task
        for pool_name, tasks in pools:
            for task in tasks:
                task_key = self.normalize_task_text(task["text"])
                if len(target) >= 4 and (target in task_key or task_key in target):
                    return pool_name, task
        return None, None

    def toggle_task_from_category_line(self, box, event=None):
        index = f"@{event.x},{event.y}" if event else "insert"
        line = box.get(f"{index} linestart", f"{index} lineend")
        task_text = self.extract_task_text_from_line(line)
        pool_name, task = self.match_task_by_text(task_text)
        if not task:
            self.status_var.set(self.t("status_category_mismatch"))
            return
        task["completed"] = not task.get("completed")
        self.save_tasks()
        self.refresh_task_list()
        self.refresh_periodic_list()
        status = self.t("done_status") if task.get("completed") else self.t("undone_status")
        pool_label = self.t("periodic_regular") if pool_name == "regular" else self.t("periodic_periodic")
        self.status_var.set(self._fmt("status_category_toggled", pool=pool_label, task=task["text"], status=status))

    # ══════════════════════════════════════════════════════════════
    #  分类结果展示
    # ══════════════════════════════════════════════════════════════
    def load_category_results(self):
        for info in self._category_cards.values():
            if info.get("text"):
                info["text"].delete("1.0", tk.END)

        if not CATEGORY_RESULTS_PATH.exists():
            for info in self._category_cards.values():
                if info.get("text"):
                    info["text"].insert(tk.END, self.t("category_waiting"))
            return

        content = CATEGORY_RESULTS_PATH.read_text(encoding="utf-8", errors="replace")
        sections = self.parse_categories(content)
        cat_names = self.get_category_names()
        for cat_name in cat_names:
            if cat_name in self._category_cards and self._category_cards[cat_name].get("text"):
                self._category_cards[cat_name]["text"].insert(
                    tk.END, sections.get(cat_name, self.t("category_empty")))
        self.status_var.set(self._fmt("status_loaded", path=CATEGORY_RESULTS_PATH))

    def parse_categories(self, content):
        cat_names = self.get_category_names()
        sections = {name: [] for name in cat_names}
        current = None
        for line in content.splitlines():
            stripped = line.strip()
            clean = stripped.lstrip("#").strip().strip("*").strip("_").strip()
            matched = None
            for cat_name in cat_names:
                if cat_name in clean:
                    matched = cat_name
                    break
            if matched:
                current = matched
                continue
            if current and stripped:
                sections[current].append(line)
        return {name: "\n".join(lines).strip() or self.t("category_empty")
                for name, lines in sections.items()}

    # ══════════════════════════════════════════════════════════════
    #  任务操作
    # ══════════════════════════════════════════════════════════════
    def unique_texts(self, texts):
        seen = set()
        result = []
        for text in texts:
            clean = text.strip()
            key = self.normalize_task_text(clean)
            if clean and key not in seen:
                seen.add(key)
                result.append(clean)
        return result

    def deduplicate_regular_tasks(self):
        seen = set()
        deduped = []
        removed = 0
        for task in self.tasks:
            key = self.normalize_task_text(task["text"])
            if key in seen:
                removed += 1
                continue
            seen.add(key)
            deduped.append(task)
        self.tasks = deduped
        return removed

    def remove_completed_regular_tasks(self):
        before = len(self.tasks)
        self.tasks = [task for task in self.tasks if not task.get("completed")]
        return before - len(self.tasks)

    def new_task_id(self):
        return datetime.now().strftime("%Y%m%d%H%M%S%f")

    def add_tasks(self):
        raw = self.task_input.get("1.0", tk.END).strip()
        if not raw:
            messagebox.showinfo(self.t("notify_title"), self.t("dialog_input_task"))
            return
        new_tasks = [line.strip(" -\t") for line in raw.splitlines() if line.strip(" -\t")]
        existing = {self.normalize_task_text(task["text"]) for task in self.tasks}
        added = 0
        skipped = 0
        for task in new_tasks:
            key = self.normalize_task_text(task)
            if key in existing:
                skipped += 1
                continue
            self.tasks.append({"text": task, "completed": False})
            existing.add(key)
            added += 1
        self.task_input.delete("1.0", tk.END)
        self.save_tasks()
        self.refresh_task_list()
        self.status_var.set(self._fmt("status_tasks_added", added=added, skipped=skipped))

    def refresh_task_list(self):
        for item in self.task_tree.get_children():
            self.task_tree.delete(item)
        for idx, task in enumerate(self.tasks):
            done = self.t("done_status") if task.get("completed") else self.t("undone_status")
            self.task_tree.insert("", tk.END, iid=str(idx), values=(done, task["text"]))

    def toggle_selected_tasks(self):
        selected = list(self.task_tree.selection())
        if not selected:
            return
        for item_id in selected:
            index = int(item_id)
            self.tasks[index]["completed"] = not self.tasks[index].get("completed")
        self.save_tasks()
        self.refresh_task_list()
        self.status_var.set(self.t("status_regular_toggled"))

    def delete_selected(self):
        selected = [int(item_id) for item_id in self.task_tree.selection()]
        if not selected:
            return
        for index in reversed(selected):
            del self.tasks[index]
        self.save_tasks()
        self.refresh_task_list()
        self.status_var.set(self.t("status_regular_deleted"))

    def clear_tasks(self):
        if not self.tasks:
            return
        if not messagebox.askyesno(self.t("notify_title"), self.t("dialog_clear_confirm")):
            return
        self.tasks.clear()
        self.save_tasks()
        self.refresh_task_list()
        self.status_var.set(self.t("status_pool_cleared"))

    # ══════════════════════════════════════════════════════════════
    #  周期性任务操作
    # ══════════════════════════════════════════════════════════════
    def add_periodic_task(self):
        text = self.periodic_input.get().strip()
        if not text:
            messagebox.showinfo(self.t("notify_title"), self.t("dialog_input_periodic"))
            return
        cycle = self._cycle_values().get(self.periodic_cycle_var.get(), "daily")
        key = self.normalize_task_text(text)
        if any(self.normalize_task_text(t["text"]) == key and t["cycle"] == cycle for t in self.periodic_tasks):
            self.status_var.set(self.t("status_periodic_skipped"))
            return
        self.periodic_tasks.append({
            "id": self.new_task_id(), "text": text, "cycle": cycle,
            "completed": False, "last_reset": self.current_cycle_key(cycle), "last_notified": "",
        })
        self.periodic_input.delete(0, tk.END)
        self.save_tasks()
        self.refresh_periodic_list()
        self.status_var.set(self.t("status_periodic_added"))

    def refresh_periodic_list(self):
        for item in self.periodic_tree.get_children():
            self.periodic_tree.delete(item)
        for idx, task in enumerate(self.periodic_tasks):
            done = self.t("done_status") if task.get("completed") else self.t("undone_status")
            self.periodic_tree.insert("", tk.END, iid=str(idx),
                                      values=(done, self._cycle_label(task["cycle"]),
                                              self.deadline_label(task["cycle"]), task["text"]))

    def toggle_selected_periodic_tasks(self):
        selected = list(self.periodic_tree.selection())
        if not selected:
            return
        for item_id in selected:
            index = int(item_id)
            self.periodic_tasks[index]["completed"] = not self.periodic_tasks[index].get("completed")
        self.save_tasks()
        self.refresh_periodic_list()
        self.status_var.set(self.t("status_periodic_toggled"))

    def delete_selected_periodic_tasks(self):
        selected = [int(item_id) for item_id in self.periodic_tree.selection()]
        if not selected:
            return
        for index in reversed(selected):
            del self.periodic_tasks[index]
        self.save_tasks()
        self.refresh_periodic_list()
        self.status_var.set(self.t("status_periodic_deleted"))

    # ══════════════════════════════════════════════════════════════
    #  周期时间逻辑
    # ══════════════════════════════════════════════════════════════
    def current_cycle_key(self, cycle):
        now = datetime.now()
        if cycle == "weekly":
            year, week, _wd = now.isocalendar()
            return f"{year}-W{week:02d}"
        if cycle == "monthly":
            return now.strftime("%Y-%m")
        return now.strftime("%Y-%m-%d")

    def reset_periodic_tasks_if_needed(self):
        changed = False
        for task in self.periodic_tasks:
            key = self.current_cycle_key(task["cycle"])
            if task.get("last_reset") != key:
                task["completed"] = False
                task["last_reset"] = key
                task["last_notified"] = ""
                changed = True
        if changed:
            self.save_tasks()

    def deadline_label(self, cycle):
        now = datetime.now()
        if cycle == "weekly":
            return (now + timedelta(days=6 - now.weekday())).strftime("%m-%d")
        if cycle == "monthly":
            next_month = (now.replace(day=28) + timedelta(days=4)).replace(day=1)
            return (next_month - timedelta(days=1)).strftime("%m-%d")
        return self.t("deadline_today")

    def is_near_period_end(self, cycle):
        now = datetime.now()
        if cycle == "daily":
            return now.hour >= 20
        if cycle == "weekly":
            return now.weekday() >= 5
        next_month = (now.replace(day=28) + timedelta(days=4)).replace(day=1)
        last_day = next_month - timedelta(days=1)
        return (last_day.date() - now.date()).days <= 2

    def check_periodic_notifications(self):
        self.reset_periodic_tasks_if_needed()
        self.notify_unfinished_periodic_tasks()
        self.after(10 * 60 * 1000, self.check_periodic_notifications)

    def notify_unfinished_periodic_tasks(self):
        unfinished = []
        for task in self.periodic_tasks:
            cycle_key = self.current_cycle_key(task["cycle"])
            if task.get("completed"):
                continue
            if task.get("last_notified") == cycle_key:
                continue
            if self.is_near_period_end(task["cycle"]):
                unfinished.append(task)
        if not unfinished:
            return
        lines = []
        for task in unfinished:
            lines.append(self._fmt("notify_line", cycle=self._cycle_label(task["cycle"]),
                                   deadline=self.deadline_label(task["cycle"]), text=task["text"]))
            task["last_notified"] = self.current_cycle_key(task["cycle"])
        self.save_tasks()
        messagebox.showwarning(self.t("notify_title"),
                               self._fmt("notify_periodic_warning", tasks="\n".join(lines)))

    # ══════════════════════════════════════════════════════════════
    #  DeepSeek API 规划
    # ══════════════════════════════════════════════════════════════
    def plan_with_deepseek(self):
        self._save_settings()
        self.reset_periodic_tasks_if_needed()
        removed_completed = self.remove_completed_regular_tasks()
        removed_duplicates = self.deduplicate_regular_tasks()
        active_regular = [t for t in self.tasks if not t.get("completed")]
        active_periodic = [t for t in self.periodic_tasks if not t.get("completed")]
        if not active_regular and not active_periodic:
            messagebox.showinfo(self.t("notify_title"), self.t("dialog_pool_empty"))
            self.save_tasks()
            self.refresh_task_list()
            self.refresh_periodic_list()
            return

        self.save_tasks()
        self.write_tasks_md()
        self.save_background()
        self.refresh_task_list()
        self.refresh_periodic_list()

        background = (BACKGROUND_PATH.read_text(encoding="utf-8", errors="replace")
                      if BACKGROUND_PATH.exists() else self.t("fallback_background"))
        tasks_md = (TASKS_MD_PATH.read_text(encoding="utf-8", errors="replace")
                    if TASKS_MD_PATH.exists() else self.t("fallback_tasks"))

        # 动态构建分类列表和输出格式
        cat_names = self.get_category_names()
        category_list = "\n".join(f"{i + 1}. {name}" for i, name in enumerate(cat_names))
        category_format = "\n\n".join(f"## {name}\n- 任务：简短原因" for name in cat_names)

        system_prompt = self.t("api_system_prompt")
        user_prompt = self._fmt("api_user_prompt", background=background, tasks_md=tasks_md,
                                category_list=category_list, category_format=category_format)

        self.plan_btn.configure(state=tk.DISABLED, text=self.t("planning_btn"))
        self.status_var.set(self.t("status_planning"))
        threading.Thread(target=self._call_deepseek_api,
                         args=(system_prompt, user_prompt, removed_completed, removed_duplicates),
                         daemon=True).start()

    def _call_deepseek_api(self, system_prompt, user_prompt, removed_completed, removed_duplicates):
        try:
            api_key = self.api_key_var.get().strip()
            model = self.api_model_var.get().strip() or "deepseek-chat"
            if not api_key:
                raise ValueError(self.t("api_key_empty"))

            payload = json.dumps({
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.7,
                "max_tokens": 4096,
            }).encode("utf-8")

            req = urllib.request.Request(
                "https://api.deepseek.com/chat/completions",
                data=payload,
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
            )
            with urllib.request.urlopen(req, timeout=180) as response:
                result = json.loads(response.read().decode("utf-8"))
                content = result["choices"][0]["message"]["content"]

            CATEGORY_RESULTS_PATH.write_text(content, encoding="utf-8")
            self.after(0, self._on_plan_complete, removed_completed, removed_duplicates)
        except Exception as exc:
            self.after(0, self._on_plan_error, str(exc))

    def _on_plan_complete(self, removed_completed, removed_duplicates):
        self.load_category_results()
        self.plan_btn.configure(state=tk.NORMAL, text=self.t("plan_btn"))
        self.status_var.set(self._fmt("status_plan_complete",
                                      removed_completed=removed_completed,
                                      removed_duplicates=removed_duplicates))

    def _on_plan_error(self, error_msg):
        self.plan_btn.configure(state=tk.NORMAL, text=self.t("plan_btn"))
        self.status_var.set(self._fmt("status_api_error", error=error_msg))
        messagebox.showerror(self.t("notify_title"),
                             self._fmt("dialog_api_error", error=error_msg))

    # ══════════════════════════════════════════════════════════════
    #  企业微信机器人
    # ══════════════════════════════════════════════════════════════
    def _on_bot_toggle(self):
        self._save_settings()
        if self.bot_enabled.get():
            self._bot_status_label.configure(text=self.t("bot_status_enabled"))
        else:
            self._bot_status_label.configure(text=self.t("bot_status_disabled"))

    def _schedule_bot_check(self):
        if self._bot_after_id:
            self.after_cancel(self._bot_after_id)
        self._bot_after_id = self.after(30000, self._bot_check_time)

    def _bot_check_time(self):
        if not self.bot_enabled.get():
            self._schedule_bot_check()
            return
        now = datetime.now()
        today_key = now.strftime("%Y-%m-%d")
        if now.hour == 6 and now.minute == 5 and self._last_bot_date != today_key:
            self._last_bot_date = today_key
            self.status_var.set(self.t("bot_sending"))
            threading.Thread(target=self._send_bot_message, daemon=True).start()
        self._schedule_bot_check()

    def _send_bot_message(self):
        last_error = ""
        for attempt in range(3):
            try:
                message = self._build_bot_message()
                payload = json.dumps({
                    "msgtype": "markdown",
                    "markdown": {"content": message},
                }).encode("utf-8")
                webhook_url = self.webhook_url_var.get().strip()
                if not webhook_url:
                    return
                req = urllib.request.Request(
                    webhook_url, data=payload,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    result = json.loads(resp.read().decode("utf-8"))
                    if result.get("errcode") == 0:
                        self.after(0, lambda: self.status_var.set(self.t("status_bot_sent")))
                        return
                    last_error = result.get("errmsg", "unknown error")
            except Exception as exc:
                last_error = str(exc)
                if attempt < 2:
                    time.sleep(2)
        self.after(0, lambda: self.status_var.set(
            self._fmt("status_bot_error", error=last_error)))

    def _build_bot_message(self):
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d %A")
        pending_regular = [t for t in self.tasks if not t.get("completed")]
        pending_periodic = [t for t in self.periodic_tasks if not t.get("completed")]
        lines = [
            f"## {self.t('bot_sent_title')}",
            "",
            f"**{self.t('bot_date_label')}**: {date_str}",
            "",
        ]
        lines.append(f"### {self.t('bot_pending_tasks')}")
        if pending_regular:
            for t in pending_regular:
                lines.append(f"- {t['text']}")
        else:
            lines.append(f"- {self.t('bot_no_tasks')}")
        if pending_periodic:
            lines.extend(["", f"### {self.t('bot_periodic_reminders')}"])
            for t in pending_periodic:
                dl = self.deadline_label(t["cycle"])
                cl = self._cycle_label(t["cycle"])
                lines.append(f"- [{cl}, {self.t('bot_due')} {dl}] {t['text']}")
        return "\n".join(lines)

    # ══════════════════════════════════════════════════════════════
    #  其他
    # ══════════════════════════════════════════════════════════════
    def open_pool_folder(self):
        os.startfile(str(POOL_DIR))


if __name__ == "__main__":
    app = TaskManagerApp()
    app.mainloop()
