# AMD HLS Agent

> 自动生成 Vitis HLS C++ 代码、并调用本机 Vitis HLS 工具链完成编译/仿真/综合验证的智能体项目。

**当前状态**：最小闭环已完成（读题 → 生成代码 → Vitis 验证 → 四级判定），正在持续优化中。

**仓库地址**：`<在这里填写仓库地址>`

---

## 1. 项目简介

本项目是一个 HLS（高层次综合）智能体：从 HLS-Eval 测试题集中读取题目（题面 + 头文件 + 测试台），调用大模型生成对应的 C++ 内核实现，再自动调用本机的 AMD Vitis HLS 工具链进行编译、仿真、综合，最后按「可解析 → 可编译 → 可运行 → 可综合」四级口径给出判定结果。

它面向 AMD FPGA 竞赛赛道（HLS 方向），用于把「读题 → 生成代码 → 工具验证 → 失败修复」这条链路自动化。

---

## 2. 环境准备（第一次使用需要做）

### 2.1 安装 VS Code

1. 打开浏览器，访问 https://code.visualstudio.com/
2. 点击页面上的 **Download for Windows** 按钮
3. 下载完成后双击安装包，一路点击「下一步」，使用默认设置即可
4. 安装完成后打开 VS Code

### 2.2 安装 Git

1. 打开浏览器，访问 https://git-scm.com/download/win
2. 点击 **64-bit Git for Windows Setup** 下载
3. 双击安装，一路「下一步」使用默认设置
4. 安装完成后，在任意文件夹里**右键**，应该能看到 **Open Git Bash here** 菜单项

### 2.3 配置 Git 身份

1. 打开 VS Code
2. 点击顶部菜单 **Terminal → New Terminal**（终端 → 新建终端）
3. 在终端里输入下面两条命令（把名字和邮箱换成你自己的，**每条输入后按回车**）：

```bash
git config --global user.name "你的名字"
```

```bash
git config --global user.email "你的邮箱"
```

> 这两条命令**只需要执行一次**，之后 Git 会记住你的身份。

### 2.4 安装 Python

1. 打开浏览器，访问 https://www.python.org/downloads/
2. 下载最新版 Python
3. 双击安装，**安装时一定要勾选 Add Python to PATH**（这一步很关键）
4. 安装完成后，在 VS Code 终端里输入下面的命令确认：

```bash
python --version
```

如果输出类似 `Python 3.12.4`，说明安装成功。

### 2.5 安装 Agent 开发常用工具（可选，推荐）

在 VS Code 左侧点击**扩展图标**（四个小方块），在搜索框里搜索并安装：

- **Python**（微软官方出品）—— Python 代码高亮与调试
- **GitLens** —— 方便查看代码历史和每行的修改记录

如果你使用 Cursor、Cline 等 Agent 工具，它们同样作为 VS Code 扩展安装：在扩展市场搜索对应名称，点击 Install 即可。

### 2.6 运行本 Agent 的前置条件（队内环境）

真正跑起来这个 Agent 还需要以下条件（不满足的话先看第 3 节把代码拉下来，再找队长确认环境）：

- **AMD Vitis HLS**（2025.2 或更新）—— 提供编译仿真综合工具链
- **HLS-Eval 数据集** —— 题目来源（默认位置见 `hls_agent/config.py` 与 `hls_agent/dataset.py`）
- **模型接入** —— 程序自动发现本机的模型网关配置（详见 `hls_agent/config.py` 的说明）

---

## 3. 获取项目代码（第一次使用）

### 3.1 克隆仓库

1. 打开 VS Code
2. 点击顶部菜单 **Terminal → New Terminal**
3. 在终端里输入（把地址换成第 1 节里填写的实际仓库地址）：

```bash
git clone <仓库地址>
```

4. 按回车，等待下载完成

### 3.2 打开项目

1. 在 VS Code 中点击顶部菜单 **File → Open Folder**（文件 → 打开文件夹）
2. 选择刚刚克隆下来的项目文件夹（名字是 `AMD_HLS_Agent` 或你看到的项目名）
3. 点击「打开」

### 3.3 安装项目依赖

1. 在 VS Code 终端里输入：

```bash
pip install -r requirements.txt
```

2. 等待安装完成（本项目依赖很少，很快）

---

## 4. 日常修改与上传流程（每次修改都要做）

> **记住总原则：先 pull，再改，再 push。**

### 4.1 开始修改前：拉取最新代码

1. 打开 VS Code 终端
2. 输入：

```bash
git pull
```

3. 如果提示有冲突（conflict），**暂停操作，联系队友一起解决**，不要强行覆盖。

### 4.2 修改代码

1. 在 VS Code 左侧文件树中点击要修改的文件
2. 修改完成后按 `Ctrl + S` 保存

### 4.3 查看修改了哪些文件

在终端输入：

```bash
git status
```

会列出你改过的文件（红色字）和已暂存的文件（绿色字）。

### 4.4 提交修改

在终端输入（两条命令，依次执行）：

```bash
git add .
```

```bash
git commit -m "说明这次改了什么"
```

> 提交信息要写清楚，例如 `git commit -m "优化日志解析逻辑"`，方便队友看懂历史。

### 4.5 推送到远程仓库

在终端输入：

```bash
git push
```

- 如果提示输入账号密码：输入你的 GitHub 账号，密码处粘贴 **Personal Access Token**（不是账号的登录密码；Token 在 GitHub 网页右上角头像 → Settings → Developer settings → Personal access tokens 里生成）
- 推送成功后，队友就能在 GitHub 网页上看到你的修改

---

## 5. 用 VS Code 图形界面操作（不想用命令行的替代方案）

1. 点 VS Code 左侧的 **源代码管理图标**（三个圆点用线连起来的图标）
2. 点开后能看到所有改动的文件列表
3. 在最上方的输入框里写提交信息（例如「修复了 xx 问题」）
4. 点输入框上方的 **✓（对勾）** 提交
5. 点 **同步更改（Sync Changes）** 或 **推送（Push）** 上传到远程仓库
6. 如果提示先拉取，就点 **拉取（Pull）**，再重复第 5 步

---

## 6. 项目目录结构说明

```
AMD_HLS_Agent/              # 项目根目录
├── README.md               # 本说明文件
├── hls_agent.py            # 程序入口：命令行运行这个文件
├── hls_agent/              # Agent 主程序包
│   ├── cli.py              # 命令行界面（读题、生成、跑 Vitis 的流程控制）
│   ├── config.py           # 自动查找 Vitis、工作区与模型接入配置
│   ├── dataset.py          # HLS-Eval 数据集扫描与题目读取
│   ├── vitis.py            # 驱动 Vitis HLS 编译/仿真/综合 + 四级判定
│   ├── llm.py              # 大模型客户端
│   ├── prompts.py          # 提示词（对齐官方 HLS-Eval 协议）
│   ├── runner.py           # 单题编排：生成 → 验证 → 失败重试
│   ├── knowledge_base.py   # 内置离线题库（12 类标准题模板）
│   ├── matcher.py          # 题目识别与参数抽取
│   ├── codegen.py          # 离线模板代码生成器
│   └── __init__.py
├── validate.py             # 生成代码的静态校验脚本
├── 题库示例.txt            # 离线题库的示例题目
├── requirements.txt        # Python 依赖清单
└── .gitignore              # Git 忽略规则（不提交游戏/会话/生成产物等）
```

> 说明：赛道提交物规划中的 `agent/`、`skill/`（技能包）、`baseline/`（基线脚本）、`run.sh`、`MODEL.md` 等文件尚未创建，后续迭代会逐步加入。

---

## 7. 常见问题

### `git push` 被拒绝怎么办？

先执行 `git pull` 拉取队友的最新修改，解决冲突后重新 `git add .`、`git commit`、`git push`。

### 忘记 `git pull` 直接改了怎么办？

依次执行：

```bash
git stash
```

```bash
git pull
```

```bash
git stash pop
```

先把你的修改暂存起来，拉取最新代码，再把修改恢复。

### 提示 Permission denied 怎么办？

检查是否登录了正确的 GitHub 账号：在终端执行 `git config user.email` 看当前邮箱，确认与你 GitHub 账号的邮箱一致；不一致就重新执行第 2.3 节的两条配置命令。

### 提示 large file 怎么办？

说明误提交了大文件（模型权重、数据集、Vitis 生成目录等）。检查 `.gitignore` 是否包含了这些目录；如果已经提交上去，联系队长协助从仓库历史中移除。

### 怎么查看历史提交？

安装 GitLens 扩展（见 2.5 节），或在终端输入：

```bash
git log
```

---

## 8. 联系方式

（待填写）
