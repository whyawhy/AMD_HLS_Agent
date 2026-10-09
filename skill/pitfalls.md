# 踩坑清单

本文件记录开发过程中**实际踩到并解决**的坑。每一条都标注了现象、根因和规避方式，
用来避免重复排查，也是设计报告里「技能包提炼过程」的素材来源。

---

## 1. Vitis HLS 打不开含非 ASCII 字符的路径

**现象**

在 `D:\新建文件夹` 这类含中文的目录下运行 Vitis，报：

```
run_hls.tcl can't be opened.
command 'set_msg_logfile' returned error code
```

随后进程以非零码退出，看起来像脚本写错了，实际是路径编码问题。

**根因**

Vitis HLS 内部的 Tcl 解释器按本地代码页处理路径，非 ASCII 字符会解析失败。

**规避**

- 工作区必须是纯 ASCII 路径。程序默认把它放在**当前项目所在盘**的
  `<盘符>:/hls_work`（例如 `D:/hls_work`），既保证纯英文，又不会挤爆系统盘。
- 可用 `--workspace` 或环境变量 `HLS_AGENT_WORKSPACE` 覆盖。
- `hls_agent/config.py::resolve_workspace` 会主动校验，遇到非 ASCII 路径直接报错，
  而不是等到 Vitis 崩掉。

---

## 2. `csim.exe` 缺 DLL 会「静默退出」

**现象**

Vitis 的 `csim_design -setup` 报告成功、`csim.exe` 也生成了，但手工执行它时：

- **0.1 秒内退出**
- **stdout / stderr 全空**
- 没有任何错误信息

看起来像卡死或死循环，极难定位。

**根因**

Vitis 生成的 `csim.exe` 依赖浮点算子模型的 DLL（`fpo_v7_1` 等）和 MinGW 运行时
（`tps/mingw/.../bin`）。这些目录不在系统 PATH 里，进程加载失败即退出，
且失败发生在 C++ 运行时的输出机制就绪之前，所以**看不到任何报错**。

**规避**

正确的 PATH 列表由 Vitis 自己写在该 csim build 目录的 `env.json` 里：

```json
{"PATH": [".../win64/tools/fpo_v7_1", ".../tps/mingw/10.0.0/win64.o/nt/bin"]}
```

`hls_agent/vitis.py::csim_env` 会读取它并注入子进程环境。若 `env.json` 缺失，
则按 Vitis 安装布局推断。

---

## 3. 推理模型的 `max_tokens` 太小会让正文为空

**现象**

调用返回 HTTP 200，但正文一个字符都没有；错误信息形如
「模型只返回了思考内容，没有正文」。

**根因**

推理型模型（返回 `thinking` + `text` 两个 content 块）会先输出大量思考内容。
若 `max_tokens` 太小，预算在思考阶段就被耗尽，**正文块根本没来得及生成**。

**规避**

- 默认 `HLS_AGENT_MAX_TOKENS=16384`。
- `hls_agent/backends.py` 的响应解析会跳过 thinking 块；若正文为空但思考内容里
  含有代码，则回退使用思考内容，并给出明确报错（带 `stop_reason`）方便定位。

---

## 4. 定点运算不能按绝对误差比对

**现象**

生成的 `3mm` 相对参考输出的**最大绝对误差约 0.05**，看起来像算错了；但实际功能是对的。

**根因**

参考实现用 `D[i][j] *= beta;` 原地累加，生成的实现用局部变量累加后整体赋值。
两者数学等价，但 `ap_fixed<32,16>` 在每一步都做舍入，**舍入点不同**，
经过三次矩阵乘的累积后末位就差出 1e-3 量级。

**规避**

- 数值比对用**相对误差**（阈值 `1e-2`），不用绝对误差。
- 官方 HLS-Eval 的 zero-shot 评测**根本不比对 dump**，只看 csim 返回码；
  但 dump 型 testbench 不查数值，功能错误的代码也能「可运行」（见第 11、12 条）。
  因此本项目默认把 dump 比对纳入判定（`strict_dump`），`--official-pass` 可切回
  官方口径与排行榜对标。

---

## 5. MachSuite 变体的 testbench 在 Windows 上风险高

**现象**

`machsuite` 变体的题目在 Windows 的 Vitis 里容易失败。

**根因**

它的 testbench 使用 POSIX 头文件（`fcntl.h` / `unistd.h` / `sys/stat.h`）和
`input.data` / `check.data` 文件 IO，依赖类 Unix 环境。

**规避**

开发期优先选择 `polybench` / `chstone` / `rosetta` 变体；`machsuite` 留到
Linux 评测机上再跑。

---

## 6. 模型不一定遵守输出格式

**现象**

提示词要求输出 `<OUTPUT_CODE name="x.cpp">...</OUTPUT_CODE>`，但模型有时返回
带叙述文字的回答、markdown 围栏代码块，甚至直接输出裸代码。

**规避**

`hls_agent/llm.py::extract_source` 实现了五级回退：

1. 官方 `<OUTPUT_CODE>` XML 格式
2. ` ```xxx.cpp ` 文件名围栏
3. 含顶层函数名的围栏代码块
4. 任意像 C++ 的围栏代码块（取最长的）
5. 整段文本本身就是 C++

另外，**抽取失败也要重试**——早期版本遇到抽取失败直接放弃，白白浪费重试额度。

---

## 7. Vitis 2026.1 已经没有 `vitis_hls` 命令

**现象**

按旧教程执行 `vitis_hls -f run.tcl` 提示找不到命令。

**根因**

2023.2 之后 Vitis 统一了入口。

**规避**

- 用 `vitis-run --mode hls --tcl run_hls.tcl`。
- `hls_agent/config.py::find_vitis_run` 在 Windows 上优先找 `vitis-run.bat`，
  在 Linux 上找 `vitis-run` / `vitis_hls`，并覆盖常见的安装目录。

---

## 8. 模型按 XML 格式输出时会把尖括号转义

**现象**

生成的 C++ 编译失败，报错：

```
2mm.cpp:3:9: error: use of class template 'ap_fixed' requires template arguments;
               argument deduction not allowed in typedef
```

去看生成的文件，发现里面是：

```cpp
typedef ap_fixed&lt;64, 32&gt; t_accum;      // 实际想要 ap_fixed<64, 32>
```

**根因**

提示词要求模型把代码放在 `<OUTPUT_CODE name="x.cpp">` 标签里。模型**正确地**遵守了
XML 语义——在 XML 里 `<` 必须转义成 `&lt;`。而我们的抽取器是正则匹配，
不做反转义，于是转义字符被原样写进了 `.cpp`，编译器把 `ap_fixed&lt;64,32&gt;`
解析成没有模板参数的 `ap_fixed`。

**注意**：官方 HLS-Eval 的 `extract_code_xml_from_llm_output` 也是正则实现、
同样不做反转义，所以这个问题在官方流程里也存在。

**规避**

`hls_agent/llm.py::unescape_xml_entities` 在抽取后统一还原。对所有回退路径
（XML / 围栏 / 裸代码）都生效。真实 C++ 代码里几乎不会出现字面的 `&lt;`，
因此还原的误伤风险极低。

**为什么容易漏**

这条坑是**跑批量评测时**才暴露的——单题手工验证时模型往往不转义，
只有在真实批量运行、模型状态不同时才出现。这说明「跑真实数据」比「跑通一遍」重要。

---

## 9. 「可编译」与「可运行」是两级，必须分开验证

**根因**

官方 `VitisHLSCSimTool` 的执行方式是：

1. `csim_design -setup` —— **只编译**，不运行
2. 手工执行生成的 `csim.exe` —— 才是运行

**规避**

`hls_agent/vitis.py::run_csim` 严格按这个顺序做，分别记录两个阶段的返回码，
对应赛道的「可编译」和「可运行」两级判定。若合并成一次 `csim_design`，
就丢失了中间判据。

---

## 10. 推理模型的思考 token 是生成时间的主要来源

**现象**

单题总墙钟 100~150 秒，其中模型生成占 70~90%。查看响应发现输出 token 里
`thinking` 块和正文差不多长甚至更长——思考内容对最终代码没有贡献，却占了一半以上
的生成时间。

**根因**

推理模型（本机网关底层是 `deepseek-v4-pro`）在输出正文之前会先生成大段思考，
按 token 计费也按 token 耗时。

**规避**

调用时传 `thinking: {"type": "disabled"}`（Anthropic Messages 接口），
或 `budget:N` 给思考限定预算。实测效果：

| 配置 | 2mm 生成耗时 | 2mm 总墙钟 | 结果 |
| --- | --- | --- | --- |
| 思考开启（默认） | 76~148 s | 100~148 s | 通过 |
| 思考关闭 | **5.2 s** | **27 s** | 通过，数值完全一致 |

即 **5 倍以上提速，质量无损失**（2mm/3mm/chstone 均已验证）。

本项目中通过 `HLS_AGENT_THINKING=off`（默认）/ `budget:N` 控制，
见 `serve/env.example` 与 `hls_agent/backends.py::_thinking_payload`。
若遇到难题质量下降，把该题改用 `budget:2048` 或开启思考重跑即可。

**注意**：切到本地模型（如 qwen2.5-coder）后行为会不同——有些模型没有思考模式，
有些（qwen3）通过 `think: false` 关闭。接入新模型时要实测一次耗时构成。

---

## 11. 定点统计类 kernel：数学等价的公式误差会差几个数量级

**现象**

批量评测中 correlation / covariance 两题「可运行」判定通过（csim 返回码 0），
但 dump 比对发现**功能错误**：

| 题目 | 最大相对误差 |
| --- | --- |
| correlation | 8153%（绝对值 81.5，参考值域 [0,1] 内） |
| covariance | 200% |

**根因**

这两题的 testbench 是 dump 型（只打印结果、不自校验），所以功能错误的代码
照样「可运行」——官方四级判定只看返回码，**这是官方口径的盲区**。

更深一层：参考实现用的是「**先归一化、后点积**」的算法——把 data 除以
`sqrt(n)*stddev` 后相关矩阵就是点积，**除法只发生一次**。模型生成的实现
在数学上完全等价，但用的是「协方差除以标准差乘积」：

```cpp
corr = (sum_cov / n) / (stddev_i * stddev_j);   // 两次除法 + 一次 sqrt
```

`ap_fixed<32,16>` 每一步都舍入：sqrt 有误差、两次除法误差叠加，
当 stddev 很小（数据方差小）时分母趋近 0，误差被放大到爆炸。

**规避**

1. **把 dump 比对升级为硬判据**：本项目默认 `strict_dump=True`（用
   `--official-pass` 可切回官方口径）。作为参赛队要保证功能正确，
   评测统计以「数值一致」为准，官方口径另列。
2. **重试提示词给参考数值样例**：只告诉模型「数值不符」没用，要附上
   「参考前 6 个值 vs 实际前 6 个值」和最大误差位置，模型能立刻判断是
   精度问题还是算法问题（`runner.py::_dump_mismatch_detail`）。
3. **提示词防患于未然**：涉及除法/开方的题目，提示词里提醒
   「定点下数学等价的公式误差差异巨大，除法合并成一次、先归一化后点积」。
4. 若重试仍修不好，把「参考实现的关键结构」（先归一化再点积、eps 保护分支）
   作为领域知识直接写进提示词——这正是技能包的价值。

---

## 12. dump 型 testbench 的盲区（第 11 条的姊妹篇）

**根因**

HLS-Eval 的 testbench 有两种：自校验型（内部 compare、失败返回非 0）和
dump 型（只把结果打印到 `==BEGIN DUMP_ARRAYS==` 块，由外部脚本比对）。
官方四级判定只看 csim 返回码，所以 dump 型题目「功能错误」也能通过。

**规避**

本项目把 dump 比对纳入判定（`strict_dump`），并把比对详情（逐数组误差、
最大误差索引、参考/实际前 6 个值）落进评测结果和重试提示词。
跑分时注意区分两个口径：

- 官方口径（`--official-pass`）：可运行 = 返回码 0，用于与排行榜对标
- 严格口径（默认）：可运行且数值一致，用于保证真实正确率

---

## 13. 不要试图绕过 Vitis 用别的编译器做快速验证（Windows）

**现象/结论**

想用 Vitis 自带的 mingw g++ 或 clang 直接编译内核+测试台，绕过 Vitis 工程启动
的 ~10 秒开销。实测：

- Vitis 的 clang-16 只 target `x86_64-pc-windows-msvc`，本机没有 MSVC SDK，
  直接调用要么报 DLL 缺失（`sqlite3.51.1.dll`），要么落到 C++IDE 的 STL 上报
  「STL1000: Unexpected compiler version」；Vitis 内部靠 `-hls` 特殊模式 +
  一整套环境变量才能工作，复刻成本高。
- mingw g++ 能编过且**数值结果与 Vitis csim 完全一致**（2mm 最大绝对误差同为
  0.054072），但编译耗时 **28 秒**（ap_fixed 模板实例化），比 Vitis 的 ~17 秒还慢。

**结论**：Windows 上「绕过 Vitis 加速编译验证」这条路不通。要降总时间，
去砍模型生成时间（见第 10 条，5 倍收益），Vitis 的 ~17 秒是工具固定成本。

---

## 14. 静态预检必须接在主循环里（写了工具但不接入等于没有）

**现象/结论**

`skill/check_generated.py`（毫秒级的静态预检）早就写好了，但主流程一直没用它：
生成代码后直接进 Vitis（~20s），编译失败才发现漏 include、签名不符这类
一眼就能看出的问题——每次失败白白等一次 Vitis 往返。

**规避**

把静态检查抽成 `hls_agent/static_check.py` 的核心实现（CLI 薄封装保留在 skill），
接入 `runner.py` 重试循环：生成后先静态预检，有阻断项直接把「人话」错误
（如「没有 #include "2mm.h"」）回灌模型，**不跑 Vitis**。配合重试温度 0.7
（避免模型重复同样错误）和 csim 超时收紧到 240s，失败路径的时间成本大幅下降。

**教训**：工具只有接进主流程才算数。写好的校验脚本束之高阁 = 每次失败多付
20 秒 × 失败次数的时间税。

---

## 15. Windows 本机的 Vitis 缺 libhlsmc DLL（hls::sqrt 触发）

**现象**

代码用 `hls::sqrt` / `hls::log` 等数学函数后，csim 编译照常通过，但运行
`csim.exe` 时**立即崩溃**：返回码 3221225781（0xC0000135 = STATUS_DLL_NOT_FOUND），
stdout/stderr 全空，和「缺 DLL 静默退出」（第 2 条）是同一类症状。

**根因**

用 pefile 解析 csim.exe 的导入表：不含 hls 数学函数的 exe 只依赖
`KERNEL32/libstdc++-6/msvcrt`，含 `hls::sqrt` 的 exe 额外依赖
`libhlsmc++-GCC95-x64.dll`。**在整个 Vitis 2026.1 安装目录里搜索不到这个 DLL**
（`Get-ChildItem -Recurse -Filter 'libhlsmc*'` 无结果）——链接用的 import lib
存在，运行时 DLL 缺失，是 Vitis Windows 安装的硬伤。

**规避**

1. 这是 **Windows 开发机特有**问题；官方评测在 Linux 容器里，DLL 不存在此坑，
   不要因为 Windows 上跑不了就否定代码。
2. 静态预检对 `hls::` 数学函数给出警告；runner 检测到
   「0xC0000135 + 零输出」判定为环境受限，**停止重试**（重试无用，编译每次
   都成功），并在结果里注明。
3. 这类题（correlation / covariance 等含 sqrt 的统计 kernel）在 Windows 上
   只验证到「可编译」，数值正确性留给 Linux 评测机验证。
4. 若必须在本机验证数值：改写代码避免 hls::sqrt（用定点迭代法手写 sqrt），
   或在 Linux 容器（WSL2 + 官方镜像）里跑。

