#!/usr/bin/env python3
"""多线程下载器（用于从魔搭拉大模型权重）。

单连接从魔搭下大文件约 6 MB/s，而它支持 Range 请求——分成多个区间
并发下载能显著提速。断点续传：中断后重跑会接着已完成的区间继续。

用法::

    python fetch_model.py <模型仓库> <文件名> [输出目录] [并发数]

示例::

    python fetch_model.py unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF \
        Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf models 16
"""

from __future__ import annotations

import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List, Optional

import requests

BASE = "https://www.modelscope.cn/api/v1/models/{repo}/repo"
CHUNK = 8 * 1024 * 1024  # 每个请求下 8 MB


def remote_size(url: str) -> int:
    r = requests.get(url, headers={"Range": "bytes=0-0"}, timeout=30, stream=True)
    r.close()
    cr = r.headers.get("Content-Range", "")
    if "/" in cr:
        return int(cr.rsplit("/", 1)[1])
    raise RuntimeError("服务端不支持 Range 请求，无法多线程下载")


def download(repo: str, fname: str, outdir: Path, conns: int = 16) -> Path:
    url = BASE.format(repo=repo) + f"?Revision=master&FilePath={fname}"
    total = remote_size(url)
    outdir.mkdir(parents=True, exist_ok=True)
    dest = outdir / fname

    # 预分配文件
    if not dest.exists() or dest.stat().st_size != total:
        with open(dest, "wb") as f:
            f.truncate(total)

    # 切分区间
    ranges: List[tuple[int, int]] = []
    pos = 0
    while pos < total:
        end = min(pos + CHUNK - 1, total - 1)
        ranges.append((pos, end))
        pos = end + 1

    # 断点续传：跳过已完成的区间
    done_file = outdir / (fname + ".done")
    done = set()
    if done_file.is_file():
        done = {int(x) for x in done_file.read_text().split() if x.isdigit()}

    got = {i: 0 for i in range(len(ranges))}
    lock = threading.Lock()
    t0 = time.time()
    failed: List[str] = []

    def fetch_chunk(idx: int) -> None:
        start, end = ranges[idx]
        if idx in done:
            got[idx] = end - start + 1
            return
        last_err = ""
        for attempt in range(5):
            try:
                with requests.get(url, headers={"Range": f"bytes={start}-{end}"},
                                  timeout=60, stream=True) as r:
                    if r.status_code not in (200, 206):
                        raise RuntimeError(f"HTTP {r.status_code}")
                    written = 0
                    with open(dest, "r+b") as f:
                        f.seek(start)
                        for block in r.iter_content(1024 * 256):
                            f.write(block)
                            written += len(block)
                            got[idx] = written
                    if written != end - start + 1:
                        raise RuntimeError(f"区间 {idx} 长度不符 {written}")
                with lock:
                    done.add(idx)
                    done_file.write_text(" ".join(str(d) for d in sorted(done)))
                return
            except Exception as e:
                last_err = f"{type(e).__name__}: {e}"
                time.sleep(2 * (attempt + 1))
        with lock:
            failed.append(f"区间 {idx}: {last_err}")

    # 进度上报线程
    monitor_stop = threading.Event()

    def monitor() -> None:
        while not monitor_stop.wait(3):
            cur = sum(got.values())
            dt = time.time() - t0
            if dt <= 0:
                continue
            avg = cur / 1024**2 / dt
            eta = (total - cur) / max(avg * 1024**2, 1)
            print(f"  {cur/total*100:5.1f}%  {cur/1024**3:.2f}/{total/1024**3:.2f} GB  "
                  f"{avg:5.1f} MB/s  剩余约 {eta/60:.0f} 分钟", flush=True)

    mon = threading.Thread(target=monitor, daemon=True)
    mon.start()

    with ThreadPoolExecutor(max_workers=conns) as pool:
        list(pool.map(fetch_chunk, range(len(ranges))))

    monitor_stop.set()

    if failed:
        raise RuntimeError(f"{len(failed)} 个区间失败（重跑本脚本可续传）: {failed[:3]}")

    if dest.stat().st_size != total:
        raise RuntimeError(f"文件大小不符: {dest.stat().st_size} != {total}")

    dt = time.time() - t0
    print(f"完成: {dest}  {total/1024**3:.2f} GB  用时 {dt/60:.1f} 分钟  "
          f"平均 {total/1024**2/dt:.1f} MB/s")
    done_file.unlink(missing_ok=True)
    return dest


def main(argv: Optional[List[str]] = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    argv = argv or []
    if len(argv) < 2:
        print(__doc__)
        return 2

    repo, fname = argv[0], argv[1]
    outdir = Path(argv[2]) if len(argv) > 2 else Path("models")
    conns = int(argv[3]) if len(argv) > 3 else 16

    print(f"仓库: {repo}")
    print(f"文件: {fname}")
    print(f"输出: {outdir.resolve()}")
    print(f"并发: {conns}")
    print()
    download(repo, fname, outdir, conns)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
