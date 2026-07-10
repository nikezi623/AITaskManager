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

CYCLE_LABELS = {"daily": "每天", "weekly": "每周", "monthly": "每月"}
CYCLE_VALUES = {value: key for key, value in CYCLE_LABELS.items()}


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
        self.title(APP_TITLE)
        self.set_window_icon()
        self.geometry("1220x760")
        self.minsize(1080, 700)

        POOL_DIR.mkdir(parents=True, exist_ok=True)
        self.tasks = self.load_tasks()
        self.periodic_tasks = self.load_periodic_tasks()
        self.api_key_var = tk.StringVar(value="")
        self.api_model_var = tk.StringVar(value="deepseek-chat")
        self.api_model_options = ["deepseek-chat", "deepseek-reasoner"]
        self.periodic_cycle_var = tk.StringVar(value="每天")
        self.font_size = tk.IntVar(value=12)
        self.status_var = tk.StringVar(value=f"任务池：{POOL_DIR}")
        self.quadrant_title_labels = []

        self.configure_style()
        self.build_ui()
        self.load_background()
        self.reset_periodic_tasks_if_needed()
        self.refresh_task_list()
        self.refresh_periodic_list()
        self.load_quadrants()
        self.after(500, self.check_periodic_notifications)

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
        style.configure("Treeview", font=("Microsoft YaHei UI", size), rowheight=size + 16)
        style.configure("Treeview.Heading", font=("Microsoft YaHei UI", size, "bold"))

    def build_ui(self):
        root = ttk.Frame(self, padding=18)
        root.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(root)
        header.pack(fill=tk.X, pady=(0, 14))
        font_controls = ttk.Frame(header)
        font_controls.pack(side=tk.RIGHT, anchor=tk.NE)
        ttk.Label(font_controls, text="字体大小", style="Subtitle.TLabel").pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(font_controls, text="A-", command=lambda: self.change_font_size(-1)).pack(side=tk.LEFT)
        ttk.Button(font_controls, text="A+", command=lambda: self.change_font_size(1)).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Label(header, text=APP_TITLE, style="Title.TLabel").pack(anchor=tk.W)
        ttk.Label(
            header,
            text="把任务放进任务池，一键调用 DeepSeek API 结合用户背景和周期任务做四象限规划。",
            style="Subtitle.TLabel",
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
        background_frame = ttk.LabelFrame(parent, text="用户背景", padding=10)
        background_frame.pack(fill=tk.X, pady=(0, 12))
        ttk.Label(
            background_frame,
            text="填写你的身份、目标、节奏和限制，AI 会据此调整优先级。",
            style="Card.TLabel",
        ).pack(anchor=tk.W, pady=(0, 6))
        self.background_input = tk.Text(background_frame, height=4, wrap=tk.WORD, font=("Microsoft YaHei UI", self.font_size.get()), relief=tk.SOLID, bd=1)
        self.background_input.pack(fill=tk.X)
        ttk.Button(background_frame, text="保存用户背景", command=self.save_background).pack(anchor=tk.E, pady=(8, 0))

        ttk.Label(parent, text="普通任务", style="Card.TLabel", font=("Microsoft YaHei UI", 13, "bold")).pack(anchor=tk.W)
        ttk.Label(parent, text="每行一个任务。重复任务会自动跳过；也可在右侧四象限结果中双击任务完成。", style="Card.TLabel").pack(anchor=tk.W, pady=(4, 8))

        self.task_input = tk.Text(parent, height=3, wrap=tk.WORD, font=("Microsoft YaHei UI", self.font_size.get()), relief=tk.SOLID, bd=1)
        self.task_input.pack(fill=tk.X)

        add_row = ttk.Frame(parent, style="Card.TFrame")
        add_row.pack(fill=tk.X, pady=8)
        ttk.Button(add_row, text="添加到任务池", style="Primary.TButton", command=self.add_tasks).pack(side=tk.LEFT)
        ttk.Button(add_row, text="清空输入", command=lambda: self.task_input.delete("1.0", tk.END)).pack(side=tk.LEFT, padx=(8, 0))

        list_frame = ttk.Frame(parent, style="Card.TFrame")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(6, 8))
        self.task_tree = ttk.Treeview(list_frame, columns=("done", "task"), show="headings", height=6, selectmode="extended")
        self.task_tree.heading("done", text="完成")
        self.task_tree.heading("task", text="任务")
        self.task_tree.column("done", width=62, anchor=tk.CENTER, stretch=False)
        self.task_tree.column("task", width=330, anchor=tk.W)
        self.task_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.task_tree.bind("<Double-1>", lambda _event: self.toggle_selected_tasks())
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.task_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.task_tree.configure(yscrollcommand=scrollbar.set)

        manage_row = ttk.Frame(parent, style="Card.TFrame")
        manage_row.pack(fill=tk.X)
        ttk.Button(manage_row, text="切换完成", command=self.toggle_selected_tasks).pack(side=tk.LEFT)
        ttk.Button(manage_row, text="删除选中", command=self.delete_selected).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(manage_row, text="清空任务池", command=self.clear_tasks).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(manage_row, text="打开文件夹", command=self.open_pool_folder).pack(side=tk.RIGHT)

        self.build_periodic_panel(parent)

        api_frame = ttk.LabelFrame(parent, text="DeepSeek API 设置", padding=10)
        api_frame.pack(fill=tk.X, pady=(14, 0))
        ttk.Label(api_frame, text="API Key", style="Card.TLabel").pack(anchor=tk.W)
        self.api_key_entry = ttk.Entry(api_frame, textvariable=self.api_key_var, show="*")
        self.api_key_entry.pack(fill=tk.X)
        ttk.Label(api_frame, text="模型名称", style="Card.TLabel").pack(anchor=tk.W, pady=(8, 0))
        self.api_model_combo = ttk.Combobox(api_frame, textvariable=self.api_model_var, values=self.api_model_options, state="readonly", width=30)
        self.api_model_combo.pack(fill=tk.X)
        ttk.Label(api_frame, text="使用 DeepSeek API 替代 opencode 终端，规划完成后自动刷新结果。", style="Card.TLabel").pack(anchor=tk.W, pady=(6, 0))

        self.plan_btn = ttk.Button(parent, text="开始 AI 四象限规划", style="Primary.TButton", command=self.plan_with_deepseek)
        self.plan_btn.pack(fill=tk.X, pady=(14, 0))
        ttk.Button(parent, text="刷新规划结果", command=self.load_quadrants).pack(fill=tk.X, pady=(8, 0))

    def build_periodic_panel(self, parent):
        periodic_frame = ttk.LabelFrame(parent, text="周期性任务", padding=10)
        periodic_frame.pack(fill=tk.BOTH, expand=True, pady=(12, 0))
        ttk.Label(periodic_frame, text="每天/每周/每月会自动刷新；临近周期结束未完成会弹窗提醒。", style="Card.TLabel").pack(anchor=tk.W)

        row = ttk.Frame(periodic_frame, style="Card.TFrame")
        row.pack(fill=tk.X, pady=(8, 6))
        self.periodic_input = ttk.Entry(row)
        self.periodic_input.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Combobox(row, textvariable=self.periodic_cycle_var, values=list(CYCLE_VALUES.keys()), width=8, state="readonly").pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(row, text="添加", command=self.add_periodic_task).pack(side=tk.LEFT, padx=(8, 0))

        tree_frame = ttk.Frame(periodic_frame, style="Card.TFrame")
        tree_frame.pack(fill=tk.BOTH, expand=True)
        self.periodic_tree = ttk.Treeview(
            tree_frame,
            columns=("done", "cycle", "deadline", "task"),
            show="headings",
            height=5,
            selectmode="extended",
        )
        self.periodic_tree.heading("done", text="完成")
        self.periodic_tree.heading("cycle", text="周期")
        self.periodic_tree.heading("deadline", text="截止")
        self.periodic_tree.heading("task", text="任务")
        self.periodic_tree.column("done", width=62, anchor=tk.CENTER, stretch=False)
        self.periodic_tree.column("cycle", width=58, anchor=tk.CENTER, stretch=False)
        self.periodic_tree.column("deadline", width=78, anchor=tk.CENTER, stretch=False)
        self.periodic_tree.column("task", width=250, anchor=tk.W)
        self.periodic_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.periodic_tree.bind("<Double-1>", lambda _event: self.toggle_selected_periodic_tasks())
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.periodic_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.periodic_tree.configure(yscrollcommand=scrollbar.set)

        actions = ttk.Frame(periodic_frame, style="Card.TFrame")
        actions.pack(fill=tk.X, pady=(6, 0))
        ttk.Button(actions, text="切换完成", command=self.toggle_selected_periodic_tasks).pack(side=tk.LEFT)
        ttk.Button(actions, text="删除选中", command=self.delete_selected_periodic_tasks).pack(side=tk.LEFT, padx=(8, 0))

    def build_quadrant_panel(self, parent):
        ttk.Label(parent, text="四象限规划结果", style="Card.TLabel", font=("Microsoft YaHei UI", 13, "bold")).pack(anchor=tk.W)
        ttk.Label(parent, text=f"DeepSeek API 规划完成后自动刷新；也可手动点击刷新按钮。双击某条任务可切换完成状态。", style="Card.TLabel").pack(anchor=tk.W, pady=(4, 10))

        grid = ttk.Frame(parent, style="Card.TFrame")
        grid.pack(fill=tk.BOTH, expand=True)
        for index in range(2):
            grid.columnconfigure(index, weight=1)
            grid.rowconfigure(index, weight=1)

        self.quadrant_boxes = {}
        quadrants = [
            ("重要且紧急", "#fee2e2"),
            ("重要不紧急", "#dcfce7"),
            ("不重要但紧急", "#fef3c7"),
            ("不重要不紧急", "#e0e7ff"),
        ]
        for i, (title, color) in enumerate(quadrants):
            frame = tk.Frame(grid, bg=color, padx=10, pady=10, highlightthickness=1, highlightbackground="#d1d5db")
            frame.grid(row=i // 2, column=i % 2, sticky="nsew", padx=6, pady=6)
            title_label = tk.Label(frame, text=title, bg=color, fg="#111827", font=("Microsoft YaHei UI", self.font_size.get(), "bold"))
            title_label.pack(anchor=tk.W)
            self.quadrant_title_labels.append(title_label)
            box = tk.Text(frame, wrap=tk.WORD, font=("Microsoft YaHei UI", self.font_size.get()), relief=tk.FLAT, bg="#ffffff")
            box.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
            box.bind("<Double-1>", lambda event, current_box=box: self.toggle_task_from_quadrant_line(current_box, event))
            self.quadrant_boxes[title] = box

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
        self.status_var.set(f"字体大小已调整为 {size}。")

    def all_children(self, widget):
        children = widget.winfo_children()
        for child in children:
            yield child
            yield from self.all_children(child)

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
            for item in data:
                if isinstance(item, dict) and item.get("text"):
                    cycle = item.get("cycle", "daily")
                    if cycle not in CYCLE_LABELS:
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
        lines = ["# 任务池", "", f"更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ""]
        lines.append("## 普通任务")
        lines.extend(f"- {task}" for task in normal_tasks)
        if not normal_tasks:
            lines.append("- 暂无")
        lines.extend(["", "## 周期性任务"])
        lines.extend(f"- {task}" for task in periodic_tasks)
        if not periodic_tasks:
            lines.append("- 暂无")
        TASKS_MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def load_background(self):
        if BACKGROUND_PATH.exists():
            self.background_input.insert("1.0", BACKGROUND_PATH.read_text(encoding="utf-8", errors="replace"))

    def save_background(self):
        content = self.background_input.get("1.0", tk.END).strip()
        BACKGROUND_PATH.write_text((content or "暂无用户背景") + "\n", encoding="utf-8")
        self.status_var.set(f"已保存用户背景：{BACKGROUND_PATH}")

    def normalize_task_text(self, text):
        return "".join(text.lower().split())

    def extract_task_text_from_quadrant_line(self, line):
        text = line.strip()
        if not text or "暂无" in text or "等待规划结果" in text:
            return ""
        text = text.lstrip("-•* ").strip()
        for marker in ("[x]", "[X]", "[ ]", "已完成", "未完成"):
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
            self.status_var.set("未能匹配该四象限任务，请确认任务名称与任务池一致。")
            return

        task["completed"] = not task.get("completed")
        self.save_tasks()
        self.refresh_task_list()
        self.refresh_periodic_list()

        status = "已完成" if task.get("completed") else "未完成"
        pool_label = "普通任务" if pool_name == "regular" else "周期性任务"
        self.status_var.set(f"已从四象限切换{pool_label}状态：{task['text']} -> {status}")

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
            messagebox.showinfo(APP_TITLE, "请先输入任务。")
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
        self.status_var.set(f"已添加 {added} 个任务，跳过 {skipped} 个重复任务。")

    def refresh_task_list(self):
        for item in self.task_tree.get_children():
            self.task_tree.delete(item)
        for idx, task in enumerate(self.tasks):
            done = "已完成" if task.get("completed") else "未完成"
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
        self.status_var.set("已更新普通任务完成状态。")

    def delete_selected(self):
        selected = [int(item_id) for item_id in self.task_tree.selection()]
        if not selected:
            return
        for index in reversed(selected):
            del self.tasks[index]
        self.save_tasks()
        self.refresh_task_list()
        self.status_var.set("已删除选中任务。")

    def clear_tasks(self):
        if not self.tasks:
            return
        if not messagebox.askyesno(APP_TITLE, "确定要清空普通任务池吗？"):
            return
        self.tasks.clear()
        self.save_tasks()
        self.refresh_task_list()
        self.status_var.set("普通任务池已清空。")

    def add_periodic_task(self):
        text = self.periodic_input.get().strip()
        if not text:
            messagebox.showinfo(APP_TITLE, "请先输入周期性任务。")
            return
        cycle = CYCLE_VALUES.get(self.periodic_cycle_var.get(), "daily")
        key = self.normalize_task_text(text)
        if any(self.normalize_task_text(task["text"]) == key and task["cycle"] == cycle for task in self.periodic_tasks):
            self.status_var.set("已跳过重复周期性任务。")
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
        self.status_var.set("已添加周期性任务。")

    def refresh_periodic_list(self):
        for item in self.periodic_tree.get_children():
            self.periodic_tree.delete(item)
        for idx, task in enumerate(self.periodic_tasks):
            done = "已完成" if task.get("completed") else "未完成"
            self.periodic_tree.insert(
                "",
                tk.END,
                iid=str(idx),
                values=(done, CYCLE_LABELS[task["cycle"]], self.deadline_label(task["cycle"]), task["text"]),
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
        self.status_var.set("已更新周期性任务完成状态。")

    def delete_selected_periodic_tasks(self):
        selected = [int(item_id) for item_id in self.periodic_tree.selection()]
        if not selected:
            return
        for index in reversed(selected):
            del self.periodic_tasks[index]
        self.save_tasks()
        self.refresh_periodic_list()
        self.status_var.set("已删除选中周期性任务。")

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
        return "今天"

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
            lines.append(f"- [{CYCLE_LABELS[task['cycle']]}，截止 {self.deadline_label(task['cycle'])}] {task['text']}")
            task["last_notified"] = self.current_cycle_key(task["cycle"])
        self.save_tasks()
        messagebox.showwarning(APP_TITLE, "以下周期性任务临近周期结束但尚未完成：\n\n" + "\n".join(lines))

    def create_prompt_file(self):
        prompt = f"""# opencode 四象限规划任务

请读取当前文件夹中的 `{BACKGROUND_MD}` 和 `{TASKS_MD}`。

请先理解用户背景，包括身份、长期目标、当前阶段、时间精力限制、工作/学习节奏和偏好。随后结合用户背景，把任务池内所有未完成任务划分到以下四个象限：

1. 重要且紧急
2. 重要不紧急
3. 不重要但紧急
4. 不重要不紧急

规划要求：

- 重要性要优先参考用户背景中的长期目标、角色责任和近期关键事项。
- 紧急性要参考任务时限、风险、依赖关系、周期截止时间和延误后果。
- 必须逐行处理 `tasks.md` 中的任务：一个输入任务行对应最终结果中的一个独立条目。
- 严禁把同一科目、同一项目、同一复习方向的多个任务合并、概括或改写成一个上位任务。
- 严禁使用“任务A（任务B、任务C）”这种括号合并写法；同一象限内也要分别写成多条。
- 最终结果中每条任务的冒号前必须保留原任务文本，不要用概括标题替代原任务。
- 只有文本完全重复、含义也完全相同的任务才可以合并；例如“数电补课”和“考前刷数电习题课”必须保留为两个任务，“补马原的笔记”和“马原刷题*10”也必须保留为两个任务。
- 已完成任务不会出现在任务池中，请只规划当前未完成任务。
- 周期性任务也要参与规划，并在原因中说明它的周期属性。
- 不要遗漏任务。

请把最终结果写入当前文件夹的 `{QUADRANTS_MD}`，格式必须如下：

## 重要且紧急
- 任务 A：简短原因

## 重要不紧急
- 任务 B：简短原因

## 不重要但紧急
- 任务 C：简短原因

## 不重要不紧急
- 任务 D：简短原因

如果某个象限没有任务，请写 `- 暂无`。
"""
        PROMPT_PATH.write_text(prompt, encoding="utf-8")

    def plan_with_deepseek(self):
        self.reset_periodic_tasks_if_needed()
        removed_completed = self.remove_completed_regular_tasks()
        removed_duplicates = self.deduplicate_regular_tasks()
        active_regular = [task for task in self.tasks if not task.get("completed")]
        active_periodic = [task for task in self.periodic_tasks if not task.get("completed")]
        if not active_regular and not active_periodic:
            messagebox.showinfo(APP_TITLE, "任务池为空，请先添加任务。")
            self.save_tasks()
            self.refresh_task_list()
            self.refresh_periodic_list()
            return

        self.save_tasks()
        self.write_tasks_md()
        self.save_background()
        self.refresh_task_list()
        self.refresh_periodic_list()

        background = BACKGROUND_PATH.read_text(encoding="utf-8", errors="replace") if BACKGROUND_PATH.exists() else "暂无用户背景"
        tasks_md = TASKS_MD_PATH.read_text(encoding="utf-8", errors="replace") if TASKS_MD_PATH.exists() else "暂无任务"

        system_prompt = "你是一个专业的任务规划助手，擅长使用艾森豪威尔四象限矩阵帮助用户规划任务。请严格按照用户提供的格式要求输出结果，不要添加额外说明。"

        user_prompt = f"""请根据以下用户背景和任务列表，将所有未完成任务划分到以下四个象限：

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

如果某个象限没有任务，请写 `- 暂无`。"""

        self.plan_btn.configure(state=tk.DISABLED, text="AI 规划中…")
        self.status_var.set("正在调用 DeepSeek API 进行四象限规划…")
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
                raise ValueError("API Key 不能为空")

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
        self.plan_btn.configure(state=tk.NORMAL, text="开始 AI 四象限规划")
        self.status_var.set(f"AI 规划完成；移除已完成 {removed_completed} 个，合并重复 {removed_duplicates} 个。")

    def _on_plan_error(self, error_msg):
        self.plan_btn.configure(state=tk.NORMAL, text="开始 AI 四象限规划")
        self.status_var.set(f"API 调用失败：{error_msg}")
        messagebox.showerror(APP_TITLE, f"DeepSeek API 调用失败：\n{error_msg}")

    def load_quadrants(self):
        for box in self.quadrant_boxes.values():
            box.delete("1.0", tk.END)

        if not QUADRANTS_PATH.exists():
            for box in self.quadrant_boxes.values():
                box.insert(tk.END, "等待规划结果...\n请点击左侧“开始 AI 四象限规划”。")
            return

        content = QUADRANTS_PATH.read_text(encoding="utf-8", errors="replace")
        sections = self.parse_quadrants(content)
        for title, box in self.quadrant_boxes.items():
            box.insert(tk.END, sections.get(title, "暂无"))
        self.status_var.set(f"已读取规划结果：{QUADRANTS_PATH}")

    def parse_quadrants(self, content):
        titles = list(self.quadrant_boxes.keys())
        current = None
        sections = {title: [] for title in titles}
        for line in content.splitlines():
            stripped = line.strip()
            # 剥离 markdown 标题标记和常见格式字符
            clean = stripped.lstrip("#").strip().strip("*").strip("_").strip()
            matched = None
            for title in titles:
                if title in clean:
                    matched = title
                    break
            if matched:
                current = matched
                continue
            if current and stripped:
                sections[current].append(line)
        return {key: "\n".join(value).strip() or "暂无" for key, value in sections.items()}

    def open_pool_folder(self):
        os.startfile(str(POOL_DIR))


if __name__ == "__main__":
    app = TaskManagerApp()
    app.mainloop()
