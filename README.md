# AI 任务管理系统 (ATM)

一个基于 Python Tkinter 的 Windows 桌面任务管理工具，集成 **DeepSeek API**，能够结合用户背景自动将任务按**艾森豪威尔四象限**进行智能规划。

## ✨ 功能特性

- **📋 普通任务管理** — 录入、完成、删除、去重，支持批量操作
- **🔁 周期性任务** — 每日/每周/每月自动刷新；临近周期结束弹窗提醒
- **👤 用户背景** — 保存你的身份、目标与约束，AI 据此判断任务优先级
- **🤖 AI 四象限规划** — 一键调用 DeepSeek API，将任务智能划分到：
  - 🔴 重要且紧急
  - 🟢 重要不紧急
  - 🟡 不重要但紧急
  - 🔵 不重要不紧急
- **🖱️ 四象限交互** — 双击结果中的任意任务可直接切换完成状态
- **🔤 字体缩放** — `A+` / `A-` 全局调节 UI 字体大小（10~22px）
- **📦 一键打包** — PyInstaller 打包为独立 `.exe`，无需 Python 环境

## 🚀 快速开始

### 环境要求

- Python 3.8+
- Windows 操作系统

### 安装运行

```bash
# 克隆仓库
git clone https://github.com/nikezi623/AITaskManager.git
cd AITaskManager

# 运行
python app.py
```

首次运行时会在当前目录自动创建 `task_pool/` 文件夹存放任务数据。

### 配置 DeepSeek API

1. 前往 [DeepSeek 开放平台](https://platform.deepseek.com/) 注册并获取 API Key
2. 在界面左侧 **「DeepSeek API 设置」** 中填入 Key
3. 选择模型（`deepseek-chat` 或 `deepseek-reasoner`）
4. 点击 **「开始 AI 四象限规划」**

## 📖 使用指南

1. 在 **「用户背景」** 栏填写你的身份、目标、节奏和限制
2. 在 **「普通任务」** 输入区逐行添加任务，点击"添加到任务池"
3. 周期性重复任务请添加到 **「周期性任务」** 栏目
4. 点击 **「开始 AI 四象限规划」**，等待 DeepSeek 返回结果
5. 在右侧四象限卡片中查看规划结果
6. 完成任务后可在列表中勾选，或**双击四象限中的任务行**快速切换状态

### 周期提醒规则

| 周期 | 提醒条件 |
|------|----------|
| 每日 | 晚 20:00 后未完成 |
| 每周 | 周六起未完成 |
| 每月 | 月末最后 3 天未完成 |

> 软件需保持运行，每 10 分钟自动检查一次；每个周期仅提醒一次。

## 📦 打包为 EXE

```bash
.\build.bat
```

生成文件：`dist\AI_TaskManager.exe`

## 📁 项目结构

```
AITaskManager/
├── app.py              # 主程序（Tkinter GUI + DeepSeek API）
├── build.bat           # PyInstaller 一键打包脚本
├── ATM.spec            # PyInstaller 配置
├── photo/
│   └── app_icon.ico    # 应用图标
├── .gitignore
└── README.md
```

运行时自动生成（已加入 `.gitignore`）：

```
task_pool/              # 任务数据目录
├── tasks.json          # 普通任务持久化
├── periodic_tasks.json # 周期性任务持久化
├── tasks.md            # 供 AI 阅读的任务列表
├── user_background.md  # 供 AI 阅读的用户背景
└── four_quadrants.md   # AI 输出的四象限结果
```

## 🛠️ 技术栈

| 层面 | 技术 |
|------|------|
| GUI | Tkinter (`clam` 主题) |
| AI | DeepSeek Chat / Reasoner API |
| 持久化 | JSON 文件 |
| 打包 | PyInstaller (`--onefile --windowed`) |

## 📄 License

MIT License — 详见 [LICENSE](LICENSE)

## 🙏 致谢

- [DeepSeek](https://www.deepseek.com/) — 提供高性价比的 AI API 服务
- 艾森豪威尔矩阵 — 经典的时间管理方法论
