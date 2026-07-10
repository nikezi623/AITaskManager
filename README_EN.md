# AI Task Manager (ATM)

> [中文版本](README.md)

A Windows desktop task management tool built with Python Tkinter, integrated with the **DeepSeek API** to automatically organize tasks using the **Eisenhower Matrix** based on your personal background.

## ✨ Features

- **📋 Task Management** — Add, complete, delete, and deduplicate tasks with batch operations
- **🔁 Recurring Tasks** — Daily/weekly/monthly auto-reset with deadline reminders
- **👤 User Profile** — Save your identity, goals, and constraints for AI-aware prioritization
- **🤖 AI Quadrant Planning** — One-click DeepSeek API call to sort tasks into:
  - 🔴 Urgent & Important
  - 🟢 Not Urgent & Important
  - 🟡 Urgent & Not Important
  - 🔵 Not Urgent & Not Important
- **🖱️ Quadrant Interaction** — Double-click any task in the matrix to toggle its completion status
- **🔤 Font Scaling** — `A+` / `A-` to adjust UI font size globally (10–22px)
- **📦 One-Click Build** — PyInstaller packaging into a standalone `.exe`

## 🚀 Quick Start

### Requirements

- Python 3.8+
- Windows OS

### Install & Run

```bash
# Clone the repository
git clone https://github.com/nikezi623/AITaskManager.git
cd AITaskManager

# Run
python app.py
```

On first launch, a `task_pool/` directory will be created automatically for task data.

### Configure DeepSeek API

1. Sign up at [DeepSeek Platform](https://platform.deepseek.com/) and get an API Key
2. Fill in your API Key under **"DeepSeek API Settings"** in the left panel
3. Select a model (`deepseek-chat` or `deepseek-reasoner`)
4. Click **"Start AI Quadrant Planning"**

## 📖 Usage

1. Fill in your background under **"User Profile"** — identity, goals, schedule, constraints
2. Enter tasks (one per line) in the **"Tasks"** input area and click "Add to Task Pool"
3. Add recurring tasks in the **"Recurring Tasks"** section
4. Click **"Start AI Quadrant Planning"** and wait for the DeepSeek response
5. Review results in the four colored quadrant cards on the right
6. Mark tasks complete in the list, or **double-click a task line in the quadrant** to toggle its status

### Recurring Task Reminders

| Cycle | Reminder Trigger |
|-------|------------------|
| Daily | After 20:00 if unfinished |
| Weekly | From Saturday if unfinished |
| Monthly | Last 3 days of the month if unfinished |

> The app must remain running. It checks every 10 minutes and notifies only once per cycle.

## 📦 Build EXE

```bash
.\build.bat
```

Output: `dist\AI_TaskManager.exe`

## 📁 Project Structure

```
AITaskManager/
├── app.py              # Main application (Tkinter GUI + DeepSeek API)
├── build.bat           # PyInstaller build script
├── ATM.spec            # PyInstaller spec
├── photo/
│   └── app_icon.ico    # Application icon
├── .gitignore
├── README.md           # Chinese README
└── README_EN.md        # English README (this file)
```

Generated at runtime (gitignored):

```
task_pool/              # Task data directory
├── tasks.json          # Regular task persistence
├── periodic_tasks.json # Recurring task persistence
├── tasks.md            # Task list for AI consumption
├── user_background.md  # User profile for AI context
└── four_quadrants.md   # AI-generated quadrant results
```

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| GUI | Tkinter (`clam` theme) |
| AI | DeepSeek Chat / Reasoner API |
| Persistence | JSON files |
| Packaging | PyInstaller (`--onefile --windowed`) |

## 📄 License

MIT License — see [LICENSE](LICENSE)

## 🙏 Acknowledgements

- [DeepSeek](https://www.deepseek.com/) — Cost-effective AI API
- Eisenhower Matrix — Classic time management methodology
