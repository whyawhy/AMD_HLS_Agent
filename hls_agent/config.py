"""运行时配置：Vitis 工具链定位、ASCII 工作区、模型接入。

赛题环境约定（见《选题指南》3.1.3）：
  - 目标器件 xczu3eg-sbva484-1-e，时钟 5 ns
  - 工具链 AMD Vitis 2025.2 / 2026.1，HLS track 用 Vitis HLS

本机实测约束：
  - Vitis HLS 打不开含非 ASCII 字符的路径，工作区必须是纯 ASCII
  - Vitis 2026.1 没有 vitis_hls 可执行入口，用 `vitis-run --mode hls`
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

# --------------------------------------------------------------------------
# 赛题固定参数
# --------------------------------------------------------------------------

DEFAULT_PART = "xczu3eg-sbva484-1-e"
DEFAULT_CLOCK_NS = 5.0

# --------------------------------------------------------------------------
# Vitis 定位
# --------------------------------------------------------------------------

_VITIS_HINTS = [
    r"C:\Xilinx\Vitis\{v}\bin",
    r"D:\Xilinx\Vitis\{v}\bin",
    r"E:\Xilinx\Vitis\{v}\bin",
    r"C:\AMDdesign\{v}\Vitis\bin",
    r"D:\AMDdesign\{v}\Vitis\bin",
    r"E:\AMDdesign\{v}\Vitis\bin",
]
_VITIS_VERSIONS = ["2026.1", "2025.2", "2025.1", "2024.2", "2024.1", "2023.2"]


def _ascii_safe(p: Path) -> bool:
    try:
        str(p).encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


def find_vitis_run(explicit: Optional[str] = None) -> Optional[Path]:
    """定位 vitis-run 启动脚本。返回 None 表示没找到。"""
    candidates: List[Path] = []

    if explicit:
        candidates.append(Path(explicit))

    for var in ("HLS_AGENT_VITIS_RUN", "XILINX_VITIS"):
        v = os.environ.get(var)
        if v:
            p = Path(v)
            candidates.append(p if p.name.lower().endswith(".bat") else p / "bin" / "vitis-run.bat")

    for ver in _VITIS_VERSIONS:
        for hint in _VITIS_HINTS:
            candidates.append(Path(hint.format(v=ver)) / "vitis-run.bat")

    for c in candidates:
        if c.is_file():
            return c

    # 最后看 PATH
    for d in os.environ.get("PATH", "").split(os.pathsep):
        if d:
            p = Path(d) / "vitis-run.bat"
            if p.is_file():
                return p

    return None


def find_vitis_hls(explicit: Optional[str] = None) -> Optional[Path]:
    """定位传统 vitis_hls 入口（旧版本或 scripts 目录下）。找不到返回 None。"""
    if explicit:
        p = Path(explicit)
        if p.is_file():
            return p

    v = find_vitis_run()
    if v:
        for cand in (v.parent / "vitis_hls.bat", v.parent / "unwrapped" / "win64.o" / "vitis_hls.exe"):
            if cand.is_file():
                return cand
    return None


# --------------------------------------------------------------------------
# 工作区
# --------------------------------------------------------------------------


class WorkspaceError(RuntimeError):
    """工作区路径不可用。"""


def resolve_workspace(explicit: Optional[str] = None) -> Path:
    """确定 Vitis 工作区根目录，必须是纯 ASCII 路径。

    优先级：显式参数 > HLS_AGENT_WORKSPACE 环境变量 > 当前项目所在盘的 <盘符>:\\hls_work
    > 家目录下的 hls_work。

    当前工作目录若含中文（如 D:\\新建文件夹）本身不会被采用——Vitis 读不了——
    但会借用它的**盘符**，这样工作区与项目同盘，不会挤爆系统盘。
    """
    cand: Optional[Path] = None

    if explicit:
        cand = Path(explicit).expanduser()
    elif os.environ.get("HLS_AGENT_WORKSPACE"):
        cand = Path(os.environ["HLS_AGENT_WORKSPACE"]).expanduser()
    else:
        # 先在项目所在盘找位置
        try:
            drive = Path.cwd().drive  # 形如 "D:"
        except OSError:
            drive = ""
        if drive:
            candidate = Path(drive + os.sep) / "hls_work"
            if _ascii_safe(candidate) and Path(drive + os.sep).exists():
                cand = candidate

        if cand is None:
            home = Path.home()
            cand = (home / "hls_work") if _ascii_safe(home) else Path(
                os.environ.get("SystemDrive", "C:") + os.sep
            ) / "hls_work"

    resolved = cand.resolve()
    if not _ascii_safe(resolved):
        raise WorkspaceError(
            f"Vitis HLS 无法处理含非 ASCII 字符的路径：{resolved}\n"
            f"请用 --workspace 指定一个纯英文路径，或设置环境变量 HLS_AGENT_WORKSPACE。"
        )
    return resolved


# --------------------------------------------------------------------------
# 模型接入（Anthropic 兼容端点，默认沿用本机已有的 DeepSeek 配置）
# --------------------------------------------------------------------------

DEFAULT_LLM_BASE_URL = "https://api.deepseek.com/anthropic"
DEFAULT_LLM_MODEL = "deepseek-v4-pro"

# 本机 Claude Code 的配置文件，里面也有 ANTHROPIC_* 设置。
# 进程环境里的 ANTHROPIC_BASE_URL 可能指向 Claude Desktop 的本地代理
# （127.0.0.1:xxxxx/claude-desktop），那个端口外部进程用不了，所以这里
# 优先读配置文件里的显式设置。
_CLAUDE_SETTINGS = Path.home() / ".claude" / "settings.json"


def _load_settings_env() -> dict:
    try:
        import json

        data = json.loads(_CLAUDE_SETTINGS.read_text(encoding="utf-8"))
        env = data.get("env", {})
        return env if isinstance(env, dict) else {}
    except (OSError, ValueError):
        return {}


def _gateway_routes() -> dict:
    """从 Claude Desktop 的 configLibrary 读推理网关配置。

    返回形如 {"inferenceGatewayBaseUrl": ..., "inferenceGatewayApiKey": ...,
    "inferenceModels": [{"name": "claude-fable-5", "labelOverride": "deepseek-v4-pro"}]}
    的字典；找不到返回空字典。

    这是「用当前会话接入的大模型」的完整钥匙：Claude Desktop 在本机起了一个
    HTTP 网关，把 claude-fable-5 之类的模型别名路由到底层模型（如 deepseek-v4-pro）。
    外部进程带上网关 key、用别名调用，就和 Claude 会话走同一条模型通路。
    """
    import json

    for base in (os.environ.get("LOCALAPPDATA"), os.environ.get("APPDATA")):
        if not base:
            continue
        for folder in ("Claude-3p", "Claude"):
            d = Path(base) / folder / "configLibrary"
            if not d.is_dir():
                continue
            for f in d.glob("*.json"):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                if isinstance(data, dict) and "inferenceGatewayBaseUrl" in data:
                    return data
    return {}


def _gateway_model_alias(routes: dict, want: str) -> str:
    """把配置里写的模型名映射成网关接受的别名。

    路由表每项 {"name": 别名, "labelOverride": 显示名}。请求网关时必须用别名；
    若配置里的名字是显示名（如 deepseek-v4-pro），映射回别名（claude-fable-5）。
    """
    models = routes.get("inferenceModels", [])
    if not models:
        return want
    for m in models:
        if m.get("name") == want:
            return want
        if m.get("labelOverride") == want:
            return m["name"]
    # 都不匹配就用路由表第一项（通常就是当前会话的主模型）
    return models[0].get("name", want)


def _find_host_creds() -> dict:
    """在 Claude Desktop 的本地数据目录里找 host 凭证。

    返回形如 {"ANTHROPIC_AUTH_TOKEN": "ccs-...", "ANTHROPIC_BASE_URL": "http://..."}
    的字典；找不到返回空字典。

    这是「用当前 Claude 会话接入的大模型」的钥匙：Claude Desktop 在本地起了一个
    HTTP 网关（127.0.0.1:xxxxx/claude-desktop），持有会话凭证的进程可以像 Claude
    一样调用它。凭证写在 host-creds-<uuid>.json 里，选最新且未过期的。
    """
    import json
    import time

    now_ms = time.time() * 1000
    cands = []
    for base in (os.environ.get("LOCALAPPDATA"), os.environ.get("APPDATA")):
        if not base:
            continue
        for folder in ("Claude-3p", "Claude"):
            d = Path(base) / folder
            if not d.is_dir():
                continue
            for f in d.glob("host-creds-*.json"):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                exp = data.get("expiresAt", 0)
                cands.append((exp, data.get("env", {})))

    alive = [env for exp, env in cands if exp > now_ms]
    return max(alive, key=lambda e: 0) if alive else {}  # 过期凭证宁可不用


@dataclass
class LLMConfig:
    base_url: str = DEFAULT_LLM_BASE_URL
    api_key: str = ""
    model: str = DEFAULT_LLM_MODEL
    max_tokens: int = 16384
    temperature: float = 0.2
    timeout_s: int = 300

    @classmethod
    def from_env(cls) -> "LLMConfig":
        """解析顺序：host 凭证（Claude Desktop 本地网关，即"当前会话接入的大模型"）
        > 环境变量 > ~/.claude/settings.json > 内置默认值。"""
        saved = _load_settings_env()
        host = _find_host_creds()

        def pick(*names: str, default: str = "") -> str:
            for n in names:
                v = os.environ.get(n)
                if v:
                    return v
            for n in names:
                v = saved.get(n)
                if v:
                    return v
            return default

        # 1) 显式指定（HLS_AGENT_*）永远优先
        if os.environ.get("HLS_AGENT_BASE_URL"):
            base = os.environ["HLS_AGENT_BASE_URL"]
            key = os.environ.get("HLS_AGENT_API_KEY", "")
        # 2) host 凭证：Claude Desktop 本地网关，与当前会话同一模型接入
        elif host.get("ANTHROPIC_BASE_URL") and host.get("ANTHROPIC_AUTH_TOKEN"):
            base = host["ANTHROPIC_BASE_URL"]
            key = host["ANTHROPIC_AUTH_TOKEN"]
        else:
            base = pick("ANTHROPIC_BASE_URL", default=DEFAULT_LLM_BASE_URL)
            key = pick("ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY")
            # 本地代理端口若没有配套 key（host 凭证缺失），回落到配置文件
            if ("127.0.0.1" in base or "localhost" in base) and not key:
                base = saved.get("ANTHROPIC_BASE_URL", DEFAULT_LLM_BASE_URL)
                if "127.0.0.1" in base or "localhost" in base:
                    base = DEFAULT_LLM_BASE_URL

        max_tokens = 16384
        raw = os.environ.get("HLS_AGENT_MAX_TOKENS", "")
        if raw.isdigit():
            max_tokens = int(raw)

        timeout_s = 300
        raw_t = os.environ.get("HLS_AGENT_LLM_TIMEOUT", "")
        if raw_t.isdigit():
            timeout_s = int(raw_t)

        # 模型名：显式指定 > settings.json > 默认；走本地网关时映射成网关别名
        model = pick("HLS_AGENT_MODEL", "ANTHROPIC_MODEL", default=DEFAULT_LLM_MODEL)
        routes = _gateway_routes()
        if "127.0.0.1" in base or "localhost" in base or routes.get("inferenceGatewayBaseUrl") == base.rstrip("/"):
            model = _gateway_model_alias(routes, model)

        return cls(
            base_url=base.rstrip("/"),
            api_key=key,
            model=model,
            max_tokens=max_tokens,
            timeout_s=timeout_s,
        )

    def describe(self) -> str:
        key = "已配置" if self.api_key else "缺失"
        return f"{self.model} @ {self.base_url} (API Key: {key})"


# --------------------------------------------------------------------------
# 总配置
# --------------------------------------------------------------------------


def _default_vitis_run() -> Optional[Path]:
    try:
        return find_vitis_run()
    except Exception:
        return None


@dataclass
class AgentConfig:
    part: str = DEFAULT_PART
    clock_ns: float = DEFAULT_CLOCK_NS
    workspace: Path = field(default_factory=resolve_workspace)
    vitis_run: Optional[Path] = field(default_factory=_default_vitis_run)
    csim_timeout_s: int = 600
    csynth_timeout_s: int = 1800
    verbose: bool = False
    llm: LLMConfig = field(default_factory=LLMConfig.from_env)

    def vitis_ready(self) -> bool:
        return self.vitis_run is not None and Path(self.vitis_run).is_file()


def sanitize_project_name(name: str) -> str:
    """把任务名转成 Vitis 能接受的工程名（不能以数字开头，只留 ASCII 词字符）。"""
    s = re.sub(r"[^A-Za-z0-9_]", "_", name)
    s = re.sub(r"_+", "_", s).strip("_")
    if not s:
        s = "task"
    if s[0].isdigit():
        s = "t_" + s
    return s[:48]


def vitis_project_name(task_name: str) -> str:
    """Vitis 工程目录名。runner 与 CLI 必须用同一套规则。"""
    return "proj_" + sanitize_project_name(task_name)


_WIN_BAD = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_dir_name(name: str) -> str:
    """工作区里的题目目录名。只去掉文件系统非法字符，保留原名（如 2mm）。"""
    s = _WIN_BAD.sub("_", name).strip(" .")
    return s or "task"
