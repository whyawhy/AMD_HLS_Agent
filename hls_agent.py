#!/usr/bin/env python3
"""HLS 硬件评估标准测试题识别 + Vitis HLS C++ 代码生成 —— 命令行入口。

    python hls_agent.py --list
    python hls_agent.py "实现8点FIR低通滤波器，输入16位有符号数"
"""

import sys
from pathlib import Path

# 允许直接从仓库根目录运行：把脚本所在目录加入模块搜索路径
sys.path.insert(0, str(Path(__file__).resolve().parent))

from hls_agent.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
