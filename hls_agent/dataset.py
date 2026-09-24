"""HLS-Eval 数据集适配（严格对齐官方 hls_eval/data.py 的 BenchmarkCase）。

题目的判定规则与官方一致：**目录下存在 hls_eval_config.toml 即为一题**，且必须满足
  - `top.txt` 非空            -> 顶层函数名
  - 恰好一个 stem 以 `_tb` 结尾的源文件 -> testbench
  - `kernel_description.md` 非空 -> 题面（喂给模型）
  - 恰好一个非 tb 的 .cpp     -> 参考实现（评测时不提供给模型）
  - `hls_eval_config.toml`    -> tags / tb_data

官方评测流程（hls_eval/eval.py 的 HLSGenerationZeroShotEvaluator）给模型的是
「题面 + 头文件 + testbench」，模型**只生成那一个 .cpp**；头文件与 testbench
由数据集提供且不可修改。
"""

from __future__ import annotations

import shutil
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

CPP_EXT = (".c", ".cc", ".cpp")
H_EXT = (".h", ".hh", ".hpp")


class DatasetError(RuntimeError):
    pass


@dataclass
class Task:
    """一道 HLS-Eval 题目。"""

    name: str
    root: Path  # 题目目录
    top: str  # 顶层函数名（top.txt）
    kernel_file: Path  # 参考实现 .cpp，同时决定生成的文件名
    header_file: Path  # 提供给模型的头文件，不可修改
    tb_file: Path  # testbench，不可修改
    description_file: Path  # kernel_description.md
    tags: List[str] = field(default_factory=list)
    tb_data: List[Path] = field(default_factory=list)  # toml 里声明的 tb_data
    variant: str = ""  # 所属数据集变体，如 polybench / chstone

    # ---- 惰性读取的内容 -------------------------------------------------
    _desc_cache: Optional[str] = None
    _header_cache: Optional[str] = None
    _tb_cache: Optional[str] = None

    @property
    def source_name(self) -> str:
        """要生成的文件名，必须与数据集里的参考实现同名。"""
        return self.kernel_file.name

    @property
    def header_name(self) -> str:
        return self.header_file.name

    @property
    def tb_name(self) -> str:
        return self.tb_file.name

    @property
    def description(self) -> str:
        if self._desc_cache is None:
            self._desc_cache = self.description_file.read_text(encoding="utf-8", errors="replace")
        return self._desc_cache

    @property
    def header_src(self) -> str:
        if self._header_cache is None:
            self._header_cache = self.header_file.read_text(encoding="utf-8", errors="replace")
        return self._header_cache

    @property
    def tb_src(self) -> str:
        if self._tb_cache is None:
            self._tb_cache = self.tb_file.read_text(encoding="utf-8", errors="replace")
        return self._tb_cache

    def reference_dump_file(self) -> Optional[Path]:
        """参考输出 dump。优先 HLS 版本（定点），没有就用通用版本。"""
        for name in ("tb_data_hls.txt", "tb_data.txt"):
            p = self.root / name
            if p.is_file():
                return p
        for p in self.tb_data:
            if p.is_file() and p.suffix == ".txt":
                return p
        return None

    def summary(self) -> str:
        return f"{self.name}  (top={self.top}, 变体={self.variant})"


# --------------------------------------------------------------------------
# 数据集
# --------------------------------------------------------------------------


class HlsEvalDataset:
    """扫描 HLS-Eval 数据集目录树。"""

    def __init__(self, root: Path):
        root = Path(root).resolve()
        if not root.is_dir():
            raise DatasetError(f"数据集目录不存在: {root}")
        self.root = root
        self._tasks: Optional[List[Task]] = None
        self._errors: List[str] = []

    # ------------------------------------------------------------------
    def tasks(self) -> List[Task]:
        if self._tasks is None:
            self._tasks, self._errors = self._scan()
        return self._tasks

    @property
    def errors(self) -> List[str]:
        """扫描时被跳过的目录及原因。"""
        self.tasks()
        return self._errors

    def get(self, name: str) -> Task:
        for t in self.tasks():
            if t.name.lower() == name.lower():
                return t
        raise DatasetError(f"数据集里没有题目 '{name}'")

    def variants(self) -> List[str]:
        return sorted({t.variant for t in self.tasks() if t.variant})

    # ------------------------------------------------------------------
    def _scan(self) -> tuple[List[Task], List[str]]:
        tasks: List[Task] = []
        errors: List[str] = []
        seen: Dict[str, int] = {}

        dirs = sorted(d for d in self.root.rglob("*") if d.is_dir())
        for d in dirs:
            if not (d / "hls_eval_config.toml").is_file():
                continue
            try:
                t = self._build_task(d)
            except DatasetError as e:
                errors.append(f"{d}: {e}")
                continue

            # 不同变体下会有同名题目（如 polybench/2mm 与 fixed__small/2mm），
            # 用相对路径消歧：第一个占用裸名，后续加变体前缀
            if t.name in seen:
                seen[t.name] += 1
                rel = d.relative_to(self.root)
                t.name = f"{rel.parts[0]}__{t.name}" if len(rel.parts) > 1 else f"{t.name}__{seen[t.name]}"
            else:
                seen[t.name] = 1
            tasks.append(t)

        tasks.sort(key=lambda x: (x.variant, x.name))
        return tasks, errors

    def _build_task(self, d: Path) -> Task:
        toml_fp = d / "hls_eval_config.toml"
        try:
            cfg = tomllib.loads(toml_fp.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as e:
            raise DatasetError(f"hls_eval_config.toml 无法解析: {e}") from e

        top_fp = d / "top.txt"
        if not top_fp.is_file() or not top_fp.read_text(encoding="utf-8").strip():
            raise DatasetError("top.txt 缺失或为空")
        top = top_fp.read_text(encoding="utf-8").strip()

        desc_fp = d / "kernel_description.md"
        if not desc_fp.is_file() or not desc_fp.read_text(encoding="utf-8").strip():
            raise DatasetError("kernel_description.md 缺失或为空")

        files = [f for f in d.glob("*") if f.is_file()]
        tb_matches = [f for f in files if f.stem.endswith("_tb") and f.suffix in CPP_EXT]
        if len(tb_matches) != 1:
            raise DatasetError(f"期望恰好 1 个 _tb 文件，实际 {len(tb_matches)} 个")
        tb_file = tb_matches[0]

        kernels = [f for f in files if f.suffix in CPP_EXT and f != tb_file]
        if len(kernels) != 1:
            raise DatasetError(f"期望恰好 1 个内核 .cpp，实际 {len(kernels)} 个")
        kernel_file = kernels[0]

        headers = [f for f in files if f.suffix in H_EXT]
        if len(headers) != 1:
            raise DatasetError(f"期望恰好 1 个头文件，实际 {len(headers)} 个")
        header_file = headers[0]

        tb_data: List[Path] = []
        for name in cfg.get("tb_data", []):
            p = d / name
            if p.is_file():
                tb_data.append(p)

        try:
            variant = d.relative_to(self.root).parts[0]
        except (ValueError, IndexError):
            variant = ""

        return Task(
            name=d.name,
            root=d,
            top=top,
            kernel_file=kernel_file,
            header_file=header_file,
            tb_file=tb_file,
            description_file=desc_fp,
            tags=list(cfg.get("tags", [])),
            tb_data=tb_data,
            variant=variant,
        )


# --------------------------------------------------------------------------
# 定位
# --------------------------------------------------------------------------


def default_dataset_roots() -> List[Path]:
    home = Path.home()
    return [
        Path(r"E:\HLS-Eval\hls-eval-main\hls_eval_data"),
        Path(r"E:\HLS-Eval\hls-eval-main"),
        Path(r"E:\HLS-Eval"),
        Path(r"D:\HLS-Eval\hls-eval-main\hls_eval_data"),
        Path(r"D:\HLS-Eval"),
        Path(r"C:\HLS-Eval"),
        home / "HLS-Eval" / "hls-eval-main" / "hls_eval_data",
        home / "HLS-Eval",
    ]


def locate_dataset(explicit: Optional[str] = None) -> Optional[Path]:
    """找到数据集根目录并返回可用的那个。

    官方仓库解压后题目在 `hls_eval_data/` 下，但也接受直接指向该目录或仓库根。
    """
    def usable(p: Path) -> bool:
        if not p.is_dir():
            return False
        # 只要下面某处存在 hls_eval_config.toml 就算可用
        return next(p.rglob("hls_eval_config.toml"), None) is not None

    if explicit:
        p = Path(explicit)
        if usable(p):
            return p
        # 允许指向仓库根
        for sub in ("hls_eval_data", "hls-eval-main/hls_eval_data"):
            if usable(p / sub):
                return p / sub
        return None

    for c in default_dataset_roots():
        if usable(c):
            return c
    return None


def copy_task_into(task: Task, dest: Path) -> None:
    """把数据集提供的文件复制进工作目录（头文件 + testbench + tb_data）。"""
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(task.header_file, dest / task.header_file.name)
    shutil.copy2(task.tb_file, dest / task.tb_file.name)
    for f in task.tb_data:
        shutil.copy2(f, dest / f.name)
    ref = task.reference_dump_file()
    if ref is not None:
        shutil.copy2(ref, dest / ref.name)
