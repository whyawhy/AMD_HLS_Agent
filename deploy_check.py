#!/usr/bin/env python3
"""部署自检：在新机器上确认「能不能跑起来」，并给出还缺什么。

在实验室/评测机上执行::

    python deploy_check.py

它会逐项检查并给出结论：

  1. Python 版本与依赖
  2. Vitis HLS 是否找到、是哪个入口（vitis-run / vitis_hls）
  3. HLS-Eval 数据集是否找到（含题目数抽样）
  4. 模型推理服务是否可用（本地优先，远程兜底）
  5. 工作区路径是否可写（Windows 上还要求纯 ASCII）

最后给出一份「下一步该做什么」的清单。
"""

from __future__ import annotations

import os
import platform
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

OK = "  [OK]  "
WARN = "  [警告]"
FAIL = "  [缺失]"
SEP = "=" * 72


def sec(title: str) -> None:
    print()
    print(SEP)
    print(f"  {title}")
    print(SEP)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    missing = []
    warnings = []

    print(SEP)
    print("  HLS Agent 部署自检")
    print(SEP)
    print(f"  平台: {platform.platform()}")
    print(f"  Python: {sys.version.split()[0]}  ({sys.executable})")

    # ---- 1. 依赖 ----
    sec("1. Python 依赖")
    try:
        import requests  # noqa: F401

        print(f"{OK} requests 已安装")
    except ImportError:
        print(f"{FAIL} 缺少 requests —— 执行: pip install -r requirements.txt")
        missing.append("requests")

    # ---- 2. Vitis ----
    sec("2. Vitis HLS")
    try:
        from hls_agent.config import find_vitis_run

        vitis = find_vitis_run()
        if vitis:
            print(f"{OK} 找到入口: {vitis}")
            if "vitis_hls" in vitis.name.lower():
                print("       调用方式: vitis_hls -f script.tcl（旧入口）")
            else:
                print("       调用方式: vitis-run --mode hls --tcl script.tcl")
            # 版本
            try:
                import subprocess

                p = subprocess.run([str(vitis), "--version"], capture_output=True,
                                   text=True, timeout=60, errors="replace")
                v = (p.stdout or p.stderr or "").strip().splitlines()
                if v:
                    print(f"       版本: {v[0][:80]}")
            except Exception:
                pass
        else:
            print(f"{FAIL} 没找到 Vitis 入口")
            print("       解决：把 Vitis 的 bin 目录加入 PATH，")
            print("             或设置环境变量 HLS_AGENT_VITIS_RUN 指向入口文件")
            missing.append("vitis")
    except Exception as e:
        print(f"{FAIL} 检查异常: {e}")
        missing.append("vitis")

    # ---- 3. 数据集 ----
    sec("3. HLS-Eval 数据集")
    try:
        from hls_agent.dataset import HlsEvalDataset, locate_dataset

        root = locate_dataset()
        if root:
            d = HlsEvalDataset(root)
            tasks = d.tasks()
            print(f"{OK} 数据集: {root}")
            print(f"       扫到 {len(tasks)} 道题")
            variants = {}
            for t in tasks:
                variants[t.variant] = variants.get(t.variant, 0) + 1
            for v, n in sorted(variants.items()):
                print(f"         {v:<32} {n} 题")
        else:
            print(f"{FAIL} 没找到数据集")
            print("       解决：git clone https://github.com/sharc-lab/HLS-Eval")
            print("             或设置 HLS_AGENT_DATASET 指向 hls_eval_data 目录")
            missing.append("dataset")
    except Exception as e:
        print(f"{FAIL} 检查异常: {e}")
        missing.append("dataset")

    # ---- 4. 模型服务 ----
    sec("4. 模型推理服务")
    try:
        from hls_agent.config import LLMConfig
        from hls_agent.llm import probe_backends

        cfg = LLMConfig.from_env()
        print(f"       配置: backend={cfg.backend} model={cfg.model}")
        any_ok = False
        for name, ok, why in probe_backends(cfg):
            print(f"  [{'可用' if ok else '不可用'}] {name:<10} {why}")
            any_ok = any_ok or ok
        if any_ok:
            print(f"{OK} 至少一个后端可用")
        else:
            print(f"{FAIL} 没有可用的推理服务")
            print("       解决（带显卡机器推荐）: bash serve/start_vllm.sh")
            print("       或设置 HLS_AGENT_BASE_URL / HLS_AGENT_API_KEY 指向可用端点")
            missing.append("model")
    except Exception as e:
        print(f"{FAIL} 检查异常: {e}")
        missing.append("model")

    # ---- 5. 工作区 ----
    sec("5. Vitis 工作区")
    try:
        from hls_agent.config import resolve_workspace

        ws = resolve_workspace()
        ws.mkdir(parents=True, exist_ok=True)
        probe = ws / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        print(f"{OK} 工作区可写: {ws}")
        if os.name == "nt":
            try:
                str(ws).encode("ascii")
                print(f"{OK} 路径为纯 ASCII（Vitis 在 Windows 上的硬性要求）")
            except UnicodeEncodeError:
                print(f"{FAIL} 路径含非 ASCII 字符，Vitis 会打不开脚本")
                missing.append("workspace-ascii")
        free = shutil.disk_usage(ws).free / (1024 ** 3)
        print(f"       可用空间: {free:.1f} GB")
        if free < 5:
            print(f"{WARN} 空间偏小，批量评测（每题的 Vitis 工程约几百 MB）可能不够")
            warnings.append("disk")
    except Exception as e:
        print(f"{FAIL} 工作区不可用: {e}")
        missing.append("workspace")

    # ---- 结论 ----
    sec("结论")
    if not missing:
        print(f"{OK} 环境齐备，可以开始跑题：")
        print()
        print("        python hls_agent.py --task 2mm          # 单题")
        print("        python hls_agent.py --list              # 列出全部题目")
        print("        python eval.py --max 5 --jobs 4         # 批量评测（并行）")
        return 0

    print(f"{FAIL} 还缺 {len(missing)} 项: {', '.join(missing)}")
    print()
    print("       按上面各节的「解决」提示处理后，重新运行本脚本。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
