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
- 更重要的：官方 HLS-Eval 的 zero-shot 评测**根本不比对 dump**，只看 csim 返回码。
  因此数值比对在本项目中定位为**诊断信号**，不作为通过/失败的判据。

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
