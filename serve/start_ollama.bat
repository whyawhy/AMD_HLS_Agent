@echo off
REM 在 Windows 开发机上启动 Ollama 并确保模型就绪。
REM
REM 用法：
REM     serve\start_ollama.bat
REM     set MODEL=qwen2.5-coder:14b && serve\start_ollama.bat
REM
REM 注意：本机是 AMD 核显，Ollama 会走 CPU 或 Vulkan 后端，速度较慢，
REM 仅用于把流程跑通。正式评测请在带显卡的机器上跑 serve/start_vllm.sh。

setlocal
if "%MODEL%"=="" set MODEL=qwen2.5-coder:7b

where ollama >nul 2>&1
if errorlevel 1 (
    echo 未找到 ollama，请先安装： https://ollama.com/download/windows
    exit /b 1
)

echo 检查 ollama 服务 ...
curl -sf http://127.0.0.1:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo 服务未运行，请先打开 Ollama 应用（开始菜单搜 Ollama），或在另一个终端执行 ollama serve
    exit /b 1
)

echo 拉取模型 %MODEL%（已存在会跳过）...
ollama pull %MODEL%

echo.
echo 就绪。设置环境变量后即可运行智能体：
echo     set HLS_AGENT_BACKEND=ollama
echo     set HLS_AGENT_MODEL=%MODEL%
echo     py hls_agent.py --task 2mm
endlocal
