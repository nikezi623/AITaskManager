import json
import os
import sys
import threading
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
PROMPT_MD = "planning_prompt.md"
QUADRANTS_MD = "four_quadrants.md"
ICON_PATH = "photo/app_icon.ico"

# ── 四象限内部 key（语言无关） ──
QI_URGENT_IMPORTANT = "urgent_important"
QI_NOT_URGENT_IMPORTANT = "not_urgent_important"
QI_URGENT_NOT_IMPORTANT = "urgent_not_important"
QI_NOT_URGENT_NOT_IMPORTANT = "not_urgent_not_important"

QUADRANT_KEYS = [
    QI_URGENT_IMPORTANT,
    QI_NOT_URGENT_IMPORTANT,
    QI_URGENT_NOT_IMPORTANT,
    QI_NOT_URGENT_NOT_IMPORTANT,
]

QUADRANT_COLORS = {
    QI_URGENT_IMPORTANT: "#fee2e2",
    QI_NOT_URGENT_IMPORTANT: "#dcfce7",
    QI_URGENT_NOT_IMPORTANT: "#fef3c7",
    QI_NOT_URGENT_NOT_IMPORTANT: "#e0e7ff",
}

# ── 翻译字典 ──
TS = {
    "zh": {
        # 窗口
        "window_title": "AI 任务管理系统",
        # 头部
        "font_size_label": "字体大小",
        "subtitle": "把任务放进任务池，一键调用 DeepSeek API 结合用户背景和周期任务做四象限规划。",
        "lang_toggle": "EN",
        # 用户背景
        "background_frame": "用户背景",
        "background_hint": "填写你的身份、目标、节奏和限制，AI 会据此调整优先级。",
        "save_background": "保存用户背景",
        # 普通任务
        "regular_task_title": "普通任务",
        "regular_task_hint": "每行一个任务。重复任务会自动跳过；也可在右侧四象限结果中双击任务完成。",
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
        # API 设置
        "api_frame": "DeepSeek API 设置",
        "api_key_label": "API Key",
        "api_model_label": "模型名称",
        "api_hint": "使用 DeepSeek API 替代 opencode 终端，规划完成后自动刷新结果。",
        "plan_btn": "开始 AI 四象限规划",
        "planning_btn": "AI 规划中…",
        "refresh_result": "刷新规划结果",
        # 四象限标题
        "quadrant_title": "四象限规划结果",
        "quadrant_hint": "DeepSeek API 规划完成后自动刷新；也可手动点击刷新按钮。双击某条任务可切换完成状态。",
        "quadrant_urgent_important": "重要且紧急",
        "quadrant_not_urgent_important": "重要不紧急",
        "quadrant_urgent_not_important": "不重要但紧急",
        "quadrant_not_urgent_not_important": "不重要不紧急",
        "quadrant_empty": "暂无",
        "quadrant_waiting": '等待规划结果...\n请点击左侧"开始 AI 四象限规划"。',
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
        "status_quadrant_mismatch": "未能匹配该四象限任务，请确认任务名称与任务池一致。",
        "status_quadrant_toggled": "已从四象限切换{pool}状态：{task} -> {status}",
        "status_plan_complete": "AI 规划完成；移除已完成 {removed_completed} 个，合并重复 {removed_duplicates} 个。",
        "status_planning": "正在调用 DeepSeek API 进行四象限规划…",
        "status_api_error": "API 调用失败：{error}",
        "status_loaded": "已读取规划结果：{path}",
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
        # 周期提醒行模板
        "notify_line": "- [{cycle}，截止 {deadline}] {text}",
        "periodic_regular": "普通任务",
        "periodic_periodic": "周期性任务",
        # API prompt
        "api_system_prompt": "你是一个专业的任务规划助手，擅长使用艾森豪威尔四象限矩阵帮助用户规划任务。请严格按照用户提供的格式要求输出结果，不要添加额外说明。",
        "api_user_prompt": """请根据以下用户背景和任务列表，将所有未完成任务划分到以下四个象限：

1. 重要且紧急
2. 重要不紧急
3. 不重要但紧急
4. 不重要不紧急

## 用户背景
{background}

## 任务列表
{tasks_md}

## 规划要求
- 重要性要优先参考用户背景中的长期目标、角色责任和近期关键事项。
- 紧急性要参考任务时限、风险、依赖关系、周期截止时间和延误后果。
- 必须逐行处理任务列表中的任务：一个输入任务行对应最终结果中的一个独立条目。
- 严禁把同一科目、同一项目、同一复习方向的多个任务合并、概括或改写成一个上位任务。
- 严禁使用"任务A（任务B、任务C）"这种括号合并写法；同一象限内也要分别写成多条。
- 最终结果中每条任务的冒号前必须保留原任务文本，不要用概括标题替代原任务。
- 只有文本完全重复、含义也完全相同的任务才可以合并。
- 已完成任务不会出现在任务池中，请只规划当前未完成任务。
- 周期性任务也要参与规划，并在原因中说明它的周期属性。
- 不要遗漏任务。

请严格按照以下格式输出，直接写入文件内容：

## 重要且紧急
- 任务 A：简短原因

## 重要不紧急
- 任务 B：简短原因

## 不重要但紧急
- 任务 C：简短原因

## 不重要不紧急
- 任务 D：简短原因

如果某个象限没有任务，请写 `- 暂无`。""",
        "api_key_empty": "API Key 不能为空",
        "fallback_background": "暂无用户背景",
        "fallback_tasks": "暂无任务",
    },
    "en": {
        "window_title": "AI Task Manager",
        "font_size_label": "Font Size",
        "subtitle": "Drop tasks into the pool, then use DeepSeek API to auto-sort them with the Eisenhower Matrix based on your profile.",
        "lang_toggle": "中文",
        "background_frame": "User Profile",
        "background_hint": "Describe your identity, goals, schedule, and constraints. The AI will prioritize accordingly.",
        "save_background": "Save Profile",
        "regular_task_title": "Tasks",
        "regular_task_hint": "One task per line. Duplicates are auto-skipped. Double-click a task in the quadrant to toggle its status.",
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
        "api_frame": "DeepSeek API Settings",
        "api_key_label": "API Key",
        "api_model_label": "Model",
        "api_hint": "Uses DeepSeek API for quadrant planning. Results refresh automatically after planning.",
        "plan_btn": "Start AI Planning",
        "planning_btn": "Planning…",
        "refresh_result": "Refresh Results",
        "quadrant_title": "Eisenhower Matrix",
        "quadrant_hint": "Automatically refreshed after AI planning. Double-click a task to toggle its done status.",
        "quadrant_urgent_important": "Urgent & Important",
        "quadrant_not_urgent_important": "Not Urgent & Important",
        "quadrant_urgent_not_important": "Urgent & Not Important",
        "quadrant_not_urgent_not_important": "Not Urgent & Not Important",
        "quadrant_empty": "None",
        "quadrant_waiting": 'Waiting for planning...\nClick "Start AI Planning" on the left.',
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
        "status_quadrant_mismatch": "Could not match quadrant line to a task. Ensure the task text matches the pool.",
        "status_quadrant_toggled": "Toggled {pool} task from quadrant: {task} -> {status}",
        "status_plan_complete": "AI planning done. Removed {removed_completed} completed, merged {removed_duplicates} duplicate(s).",
        "status_planning": "Calling DeepSeek API for quadrant planning…",
        "status_api_error": "API call failed: {error}",
        "status_loaded": "Results loaded: {path}",
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
        "api_system_prompt": "You are a professional task planning assistant, skilled in using the Eisenhower Matrix to help users prioritize tasks. Output results strictly in the requested format without extra commentary.",
        "api_user_prompt": """Please categorize all unfinished tasks into the four quadrants below, based on the user profile and task list:

1. Urgent & Important
2. Not Urgent & Important
3. Urgent & Not Important
4. Not Urgent & Not Important

## User Profile
{background}

## Task List
{tasks_md}

## Planning Requirements
- Prioritize importance based on the user's long-term goals, role responsibilities, and recent key items.
- Judge urgency by deadlines, risks, dependencies, cycle end dates, and consequences of delay.
- Process every task line from the task list: one input line = one independent output entry.
- Do NOT merge, generalize, or rewrite multiple tasks from the same subject/project into a single parent task.
- Do NOT use "Task A (Task B, Task C)" bracket merging; list each task separately even within the same quadrant.
- Preserve the original task text before the colon in each output line; do not replace it with a summary title.
- Only merge tasks that are truly identical in both text and meaning.
- Completed tasks are excluded from the pool; only plan unfinished tasks.
- Recurring tasks must be included with their cycle attribute noted in the reason.
- Do not omit any task.

Output strictly in the following format:

## Urgent & Important
- Task A: brief reason

## Not Urgent & Important
- Task B: brief reason

## Urgent & Not Important
- Task C: brief reason

## Not Urgent & Not Important
- Task D: brief reason

If a quadrant has no tasks, write `- None`.""",
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
PROMPT_PATH = POOL_DIR / PROMPT_MD
QUADRANTS_PATH = POOL_DIR / QUADRANTS_MD


class TaskManagerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.lang = "zh"
        self.title(self.t("window_title"))
        self.set_window_icon()
        self.geometry("1220x760")
        self.minsize(1080, 700)

        POOL_DIR.mkdir(parents=True, exist_ok=True)
        self.tasks = self.load_tasks()
        self.periodic_tasks = self.load_periodic_tasks()
        self.api_key_var = tk.StringVar(value="")
        self.api_model_var = tk.StringVar(value="deepseek-chat")
        self.api_model_options = ["deepseek-chat", "deepseek-reasoner"]
        self.periodic_cycle_var = tk.StringVar(value=self.t("cycle_daily"))
        self.font_size = tk.IntVar(value=12)
        self.status_var = tk.StringVar(value=self._fmt("status_task_pool", path=POOL_DIR))
        self.quadrant_title_labels = []
        self._lang_widgets = []

        self.configure_style()
        self.build_ui()
        self.load_background()
        self.reset_periodic_tasks_if_needed()
        self.refresh_task_list()
        self.refresh_periodic_list()
        self.load_quadrants()
        self.after(500, self.check_periodic_notifications)

    # ── 国际化 ──
    def t(self, key: str) -> str:
        """返回当前语言的翻译字符串。"""
        return TS.get(self.lang, TS["zh"]).get(key, TS["zh"].get(key, key))

    def _fmt(self, key: str, **kwargs) -> str:
        """翻译并格式化。"""
        return self.t(key).format(**kwargs)

    def toggle_language(self):
        self.lang = "en" if self.lang == "zh" else "zh"
        self.title(self.t("window_title"))
        self.periodic_cycle_var.set(self.t("cycle_daily"))
        self.apply_language()
        self.refresh_task_list()
        self.refresh_periodic_list()
        self.load_quadrants()
        self.status_var.set(self._fmt("status_task_pool", path=POOL_DIR))

    def apply_language(self):
        """刷新所有已注册控件的文本。"""
        for widget, prop, key in self._lang_widgets:
            try:
                if prop == "text":
                    widget.configure(text=self.t(key))
                elif prop == "label":
                    if isinstance(widget, ttk.LabelFrame):
                        widget.configure(text=self.t(key))
                    else:
                        widget.configure(text=self.t(key))
            except (tk.TclError, AttributeError):
                pass

    def _reg(self, widget, prop: str, key: str):
        """注册需要语言切换刷新的控件。"""
        self._lang_widgets.append((widget, prop, key))
        return widget

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
        style.configure("TFrame", background="#f6f7fb")
        style.configure("Card.TFrame", background="#ffffff", relief="flat")
        style.configure("TLabel", font=("Microsoft YaHei UI", size), background="#f6f7fb", foreground="#1f2937")
        style.configure("Card.TLabel", font=("Microsoft YaHei UI", size), background="#ffffff", foreground="#1f2937")
        style.configure("Title.TLabel", font=("Microsoft YaHei UI", size + 8, "bold"), background="#f6f7fb")
        style.configure("Subtitle.TLabel", font=("Microsoft YaHei UI", size), foreground="#6b7280", background="#f6f7fb")
        style.configure("Primary.TButton", font=("Microsoft YaHei UI", size, "bold"), padding=(14, 8))
        style.configure("TButton", font=("Microsoft YaHei UI", size), padding=(10, 6))
        style.configure("Lang.TButton", font=("Microsoft YaHei UI", size - 1), padding=(8, 4))
        style.configure("Treeview", font=("Microsoft YaHei UI", size), rowheight=size + 16)
        style.configure("Treeview.Heading", font=("Microsoft YaHei UI", size, "bold"))

    def build_ui(self):
        root = ttk.Frame(self, padding=18)
        root.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(root)
        header.pack(fill=tk.X, pady=(0, 14))

        # 右上角：语言切换 + 字体缩放
        font_controls = ttk.Frame(header)
        font_controls.pack(side=tk.RIGHT, anchor=tk.NE)

        # 语言切换按钮
        lang_btn = ttk.Button(
            font_controls, text=self.t("lang_toggle"), style="Lang.TButton",
            command=self.toggle_language,
        )
        lang_btn.pack(side=tk.RIGHT, padx=(10, 0))
        self.lang_btn = lang_btn

        # 字体大小控件
        self._reg(
            ttk.Label(font_controls, text=self.t("font_size_label"), style="Subtitle.TLabel"),
            "text", "font_size_label",
        ).pack(side=tk.RIGHT, padx=(0, 6))
        ttk.Button(font_controls, text="A-", command=lambda: self.change_font_size(-1)).pack(side=tk.RIGHT)
        ttk.Button(font_controls, text="A+", command=lambda: self.change_font_size(1)).pack(side=tk.RIGHT, padx=(6, 0))

        ttk.Label(header, text=self.t("window_title"), style="Title.TLabel").pack(anchor=tk.W)
        self._reg(
            ttk.Label(header, text=self.t("subtitle"), style="Subtitle.TLabel"),
            "text", "subtitle",
        ).pack(anchor=tk.W, pady=(4, 0))

        body = ttk.PanedWindow(root, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(body, style="Card.TFrame")
        right = ttk.Frame(body, style="Card.TFrame", padding=14)
        body.add(left, weight=1)
        body.add(right, weight=2)

        task_panel = self.build_scrollable_panel(left)
        self.build_task_panel(task_panel)
        self.build_quadrant_panel(right)

        footer = ttk.Frame(root)
        footer.pack(fill=tk.X, pady=(12, 0))
        ttk.Label(footer, textvariable=self.status_var, style="Subtitle.TLabel").pack(side=tk.LEFT)

    def build_scrollable_panel(self, parent):
        canvas = tk.Canvas(parent, bg="#ffffff", highlightthickness=0)
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
        canvas.bind("<Enter>", lambda _event: canvas.bind_all("<MouseWheel>", on_mousewheel))
        canvas.bind("<Leave>", lambda _event: canvas.unbind_all("<MouseWheel>"))
        return content

    def build_task_panel(self, parent):
        # 用户背景
        self.background_frame_lf = self._reg(
            ttk.LabelFrame(parent, text=self.t("background_frame"), padding=10),
            "text", "background_frame",
        )
        self.background_frame_lf.pack(fill=tk.X, pady=(0, 12))
        self._reg(
            ttk.Label(
                self.background_frame_lf,
                text=self.t("background_hint"),
                style="Card.TLabel",
            ),
            "text", "background_hint",
        ).pack(anchor=tk.W, pady=(0, 6))
        self.background_input = tk.Text(
            self.background_frame_lf, height=4, wrap=tk.WORD,
            font=("Microsoft YaHei UI", self.font_size.get()), relief=tk.SOLID, bd=1,
        )
        self.background_input.pack(fill=tk.X)
        self._reg(
            ttk.Button(self.background_frame_lf, text=self.t("save_background"), command=self.save_background),
            "text", "save_background",
        ).pack(anchor=tk.E, pady=(8, 0))

        # 普通任务标题
        ttk.Label(parent, text=self.t("regular_task_title"), style="Card.TLabel",
                  font=("Microsoft YaHei UI", 13, "bold")).pack(anchor=tk.W)
        self._reg(
            ttk.Label(parent, text=self.t("regular_task_hint"), style="Card.TLabel"),
            "text", "regular_task_hint",
        ).pack(anchor=tk.W, pady=(4, 8))

        self.task_input = tk.Text(
            parent, height=3, wrap=tk.WORD,
            font=("Microsoft YaHei UI", self.font_size.get()), relief=tk.SOLID, bd=1,
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
        self.task_tree.bind("<Double-1>", lambda _event: self.toggle_selected_tasks())
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
            ttk.Button(parent, text=self.t("refresh_result"), command=self.load_quadrants),
            "text", "refresh_result",
        ).pack(fill=tk.X, pady=(8, 0))

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
            tree_frame,
            columns=("done", "cycle", "deadline", "task"),
            show="headings",
            height=5,
            selectmode="extended",
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
        self.periodic_tree.bind("<Double-1>", lambda _event: self.toggle_selected_periodic_tasks())
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

    def build_quadrant_panel(self, parent):
        ttk.Label(parent, text=self.t("quadrant_title"), style="Card.TLabel",
                  font=("Microsoft YaHei UI", 13, "bold")).pack(anchor=tk.W)
        self._reg(
            ttk.Label(parent, text=self.t("quadrant_hint"), style="Card.TLabel"),
            "text", "quadrant_hint",
        ).pack(anchor=tk.W, pady=(4, 10))

        grid = ttk.Frame(parent, style="Card.TFrame")
        grid.pack(fill=tk.BOTH, expand=True)
        for index in range(2):
            grid.columnconfigure(index, weight=1)
            grid.rowconfigure(index, weight=1)

        self.quadrant_boxes = {}
        self.quadrant_frames = {}
        for key in QUADRANT_KEYS:
            color = QUADRANT_COLORS[key]
            frame = tk.Frame(grid, bg=color, padx=10, pady=10,
                             highlightthickness=1, highlightbackground="#d1d5db")
            title_label = tk.Label(frame, text=self.t(f"quadrant_{key}"), bg=color, fg="#111827",
                                   font=("Microsoft YaHei UI", self.font_size.get(), "bold"))
            title_label.pack(anchor=tk.W)
            self.quadrant_title_labels.append(title_label)
            box = tk.Text(frame, wrap=tk.WORD, font=("Microsoft YaHei UI", self.font_size.get()),
                          relief=tk.FLAT, bg="#ffffff")
            box.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
            box.bind("<Double-1>", lambda event, current_box=box: self.toggle_task_from_quadrant_line(current_box, event))
            self.quadrant_boxes[key] = box
            self.quadrant_frames[key] = (title_label, color)

    def _refresh_quadrant_titles(self):
        for key in QUADRANT_KEYS:
            if key in self.quadrant_frames:
                title_label, _color = self.quadrant_frames[key]
                title_label.configure(text=self.t(f"quadrant_{key}"))

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

    def change_font_size(self, delta):
        next_size = max(10, min(22, self.font_size.get() + delta))
        self.font_size.set(next_size)
        self.apply_font_size()

    def apply_font_size(self):
        size = self.font_size.get()
        self.configure_style()
        for widget in self.all_children(self):
            if isinstance(widget, tk.Text):
                widget.configure(font=("Microsoft YaHei UI", size))
            elif isinstance(widget, tk.Label):
                weight = "bold" if widget in self.quadrant_title_labels else "normal"
                widget.configure(font=("Microsoft YaHei UI", size, weight))
        self.update_idletasks()
        self.status_var.set(self._fmt("status_font_changed", size=size))

    def all_children(self, widget):
        children = widget.winfo_children()
        for child in children:
            yield child
            yield from self.all_children(child)

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
                    tasks.append(
                        {
                            "id": item.get("id") or self.new_task_id(),
                            "text": item["text"].strip(),
                            "cycle": cycle,
                            "completed": bool(item.get("completed", False)),
                            "last_reset": item.get("last_reset") or self.current_cycle_key(cycle),
                            "last_notified": item.get("last_notified", ""),
                        }
                    )
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

    def normalize_task_text(self, text):
        return "".join(text.lower().split())

    def _is_placeholder_text(self, text):
        """判断四象限中某行是否为占位文本（中英文通用）。"""
        placeholders = ["暂无", "None", "等待规划结果", "Waiting for planning", "Start AI Planning",
                        "开始 AI 四象限规划"]
        for p in placeholders:
            if p in text:
                return True
        return False

    def extract_task_text_from_quadrant_line(self, line):
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

    def toggle_task_from_quadrant_line(self, box, event=None):
        index = f"@{event.x},{event.y}" if event else "insert"
        line = box.get(f"{index} linestart", f"{index} lineend")
        task_text = self.extract_task_text_from_quadrant_line(line)
        pool_name, task = self.match_task_by_text(task_text)
        if not task:
            self.status_var.set(self.t("status_quadrant_mismatch"))
            return

        task["completed"] = not task.get("completed")
        self.save_tasks()
        self.refresh_task_list()
        self.refresh_periodic_list()

        status = self.t("done_status") if task.get("completed") else self.t("undone_status")
        pool_label = self.t("periodic_regular") if pool_name == "regular" else self.t("periodic_periodic")
        self.status_var.set(self._fmt("status_quadrant_toggled", pool=pool_label, task=task["text"], status=status))

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

    def add_periodic_task(self):
        text = self.periodic_input.get().strip()
        if not text:
            messagebox.showinfo(self.t("notify_title"), self.t("dialog_input_periodic"))
            return
        cycle = self._cycle_values().get(self.periodic_cycle_var.get(), "daily")
        key = self.normalize_task_text(text)
        if any(self.normalize_task_text(task["text"]) == key and task["cycle"] == cycle for task in self.periodic_tasks):
            self.status_var.set(self.t("status_periodic_skipped"))
            return
        self.periodic_tasks.append(
            {
                "id": self.new_task_id(),
                "text": text,
                "cycle": cycle,
                "completed": False,
                "last_reset": self.current_cycle_key(cycle),
                "last_notified": "",
            }
        )
        self.periodic_input.delete(0, tk.END)
        self.save_tasks()
        self.refresh_periodic_list()
        self.status_var.set(self.t("status_periodic_added"))

    def refresh_periodic_list(self):
        for item in self.periodic_tree.get_children():
            self.periodic_tree.delete(item)
        for idx, task in enumerate(self.periodic_tasks):
            done = self.t("done_status") if task.get("completed") else self.t("undone_status")
            self.periodic_tree.insert(
                "",
                tk.END,
                iid=str(idx),
                values=(done, self._cycle_label(task["cycle"]), self.deadline_label(task["cycle"]), task["text"]),
            )

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

    def current_cycle_key(self, cycle):
        now = datetime.now()
        if cycle == "weekly":
            year, week, _weekday = now.isocalendar()
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
            lines.append(
                self._fmt("notify_line",
                          cycle=self._cycle_label(task["cycle"]),
                          deadline=self.deadline_label(task["cycle"]),
                          text=task["text"])
            )
            task["last_notified"] = self.current_cycle_key(task["cycle"])
        self.save_tasks()
        messagebox.showwarning(
            self.t("notify_title"),
            self._fmt("notify_periodic_warning", tasks="\n".join(lines)),
        )

    def plan_with_deepseek(self):
        self.reset_periodic_tasks_if_needed()
        removed_completed = self.remove_completed_regular_tasks()
        removed_duplicates = self.deduplicate_regular_tasks()
        active_regular = [task for task in self.tasks if not task.get("completed")]
        active_periodic = [task for task in self.periodic_tasks if not task.get("completed")]
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

        background = (
            BACKGROUND_PATH.read_text(encoding="utf-8", errors="replace")
            if BACKGROUND_PATH.exists()
            else self.t("fallback_background")
        )
        tasks_md = (
            TASKS_MD_PATH.read_text(encoding="utf-8", errors="replace")
            if TASKS_MD_PATH.exists()
            else self.t("fallback_tasks")
        )

        system_prompt = self.t("api_system_prompt")
        user_prompt = self._fmt("api_user_prompt", background=background, tasks_md=tasks_md)

        self._reg(self.plan_btn, "text", "plan_btn")
        self.plan_btn.configure(state=tk.DISABLED, text=self.t("planning_btn"))
        self.status_var.set(self.t("status_planning"))
        threading.Thread(
            target=self._call_deepseek_api,
            args=(system_prompt, user_prompt, removed_completed, removed_duplicates),
            daemon=True,
        ).start()

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
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
            )

            with urllib.request.urlopen(req, timeout=180) as response:
                result = json.loads(response.read().decode("utf-8"))
                content = result["choices"][0]["message"]["content"]

            QUADRANTS_PATH.write_text(content, encoding="utf-8")
            self.after(0, self._on_plan_complete, removed_completed, removed_duplicates)

        except Exception as exc:
            self.after(0, self._on_plan_error, str(exc))

    def _on_plan_complete(self, removed_completed, removed_duplicates):
        self.load_quadrants()
        self.plan_btn.configure(state=tk.NORMAL, text=self.t("plan_btn"))
        self.status_var.set(self._fmt(
            "status_plan_complete",
            removed_completed=removed_completed,
            removed_duplicates=removed_duplicates,
        ))

    def _on_plan_error(self, error_msg):
        self.plan_btn.configure(state=tk.NORMAL, text=self.t("plan_btn"))
        self.status_var.set(self._fmt("status_api_error", error=error_msg))
        messagebox.showerror(self.t("notify_title"), self._fmt("dialog_api_error", error=error_msg))

    def load_quadrants(self):
        for box in self.quadrant_boxes.values():
            box.delete("1.0", tk.END)

        if not QUADRANTS_PATH.exists():
            for key in QUADRANT_KEYS:
                self.quadrant_boxes[key].insert(tk.END, self.t("quadrant_waiting"))
            return

        content = QUADRANTS_PATH.read_text(encoding="utf-8", errors="replace")
        sections = self.parse_quadrants(content)
        for key in QUADRANT_KEYS:
            self.quadrant_boxes[key].insert(tk.END, sections.get(key, self.t("quadrant_empty")))
        self.status_var.set(self._fmt("status_loaded", path=QUADRANTS_PATH))

    def parse_quadrants(self, content):
        # 建立象限标题（当前语言）→ 内部 key 的映射
        title_to_key = {}
        for key in QUADRANT_KEYS:
            title_to_key[self.t(f"quadrant_{key}")] = key

        current = None
        sections = {key: [] for key in QUADRANT_KEYS}
        for line in content.splitlines():
            stripped = line.strip()
            clean = stripped.lstrip("#").strip().strip("*").strip("_").strip()
            matched = None
            for title, key in title_to_key.items():
                if title in clean:
                    matched = key
                    break
            if matched:
                current = matched
                continue
            if current and stripped:
                sections[current].append(line)
        return {
            key: "\n".join(value).strip() or self.t("quadrant_empty")
            for key, value in sections.items()
        }

    def open_pool_folder(self):
        os.startfile(str(POOL_DIR))


if __name__ == "__main__":
    app = TaskManagerApp()
    app.mainloop()
