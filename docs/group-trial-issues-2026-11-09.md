# 组内试用问题与进展记录（2026-11-09）

这份记录记录组内 Windows 试用中实际遇到的安装/操作问题及后续进展，不改变 v0.1.0 的代码、数据和 tag。

## 问题 1：`uv sync` 自动选到 Python 3.15，PyYAML 构建超时

### 现象

同门在 Windows PowerShell 中执行：

```powershell
uv sync --locked
```

环境：

- `uv 0.13.7`
- Windows PowerShell
- `uv sync` 创建虚拟环境时显示 `Using CPython 3.15.2`

报错关键行：

```text
error: Failed to download and build `pyyaml==6.0.3`
  cause: Failed to install requirements from `build-system.requires`
  cause: Failed to download `setuptools==84.2.1`
  cause: Failed to download distribution due to network timeout.
         Try increasing UV_HTTP_TIMEOUT (current value: 30s).
```

### 原因

1. `uv` 自动选择了最新的 CPython 3.15.2。
2. `pyyaml==6.0.3` 没有匹配 3.15 的现成预编译包，`uv` 退回到源码构建。
3. 源码构建需要临时下载 `setuptools==84.2.1`，网络在 30 秒后超时。

这不是项目代码或数据的问题，也不是电脑坏了。

### 处理

固定 Python 3.12，并给下载留出更长时间：

```powershell
cd D:\rnp
$env:UV_HTTP_TIMEOUT="120"
uv python install 3.12
uv venv --python 3.12 --clear .venv
uv sync --locked --python 3.12
uv run rnp --version
```

预期最后一行显示 `0.1.0`。

如果仍然超时，可把 `UV_HTTP_TIMEOUT` 调到 `300` 后重试；也可以换手机热点重试。不要使用不明镜像。

### 状态

- 指南已更新：`docs/group-quickstart-windows-v0.1.0.docx`，commit `5926877`（`docs: pin the Windows quickstart to Python 3.12`）。
- 指南新增了“为什么要指定 3.12”说明和对应排查行。
- 同门按新命令重试后已成功完成测试（作者 2026-11-10 说明）。

## 问题 2：`rnp intersect --targets` 被换行成两次执行

### 现象

同门执行时，命令在 `--targets` 后断成两行：

```powershell
uv run rnp intersect --config examples/quickstart/run.yaml --targets
```

随后出现：

```text
rnp intersect: error: argument --targets: expected one argument
```

下一行 `results/quickstart/targets.tsv` 停在新的 PowerShell 提示符后，并没有作为 `--targets` 的值传给命令。

### 原因

指南/PDF 或聊天窗口里的长命令自动折行，复制时把换行也带进了 PowerShell。PowerShell 先执行了缺少参数的前半句，所以 `--targets` 收到 0 个参数。

不是数据问题，也不是 `ingest stp` 的问题；前一步已经成功。

### 处理

改用短变量写法，一行一行执行，避免长命令在参数中间断开：

```powershell
cd D:\rnp
$cfg = "examples/quickstart/run.yaml"
$targets = "results/quickstart/targets.tsv"
uv run rnp intersect --config $cfg --targets $targets
```

之后：

```powershell
$net = "results/quickstart/intersect"
uv run rnp network --config $cfg --intersect $net
```

如果关掉 PowerShell，`$cfg` 等变量会丢失，需要重新执行赋值。

### 状态

- 已将短变量写法发给同门。
- 指南已在第 4.3/4.4 节前新增“从 uv 选到行尾、整行复制、不要在中途回车”的提示。
- 同门改用短变量写法后已成功完成测试（作者 2026-11-10 说明）。

## 2026-11-11 完成情况（用户报告）

按用户最新口径，已完成教学流程的共 5 人：

| 角色 | 人数 | 情况 |
|---|---:|---|
| 同门 | 1 | 已完成；即最早遇到 uv/PATH、Python 3.15 和命令换行问题的那位 |
| 师姐 | 2 | 已完成教学流程；其中 1 位经历了上面的 uv/PATH、Python 3.15 和命令换行问题，最终跑通 |
| 师兄 | 1 | 已完成教学流程，未遇到报错 |
| 师妹 | 1 | 已完成；经历 uv/PATH、Python 3.15/PyYAML 和命令换行问题，按修正后的命令跑通 |

说明：

- 完成的是 Windows 教学假数据流程（validate → ingest → intersect → network），不等于完整科研复现。
- 问卷为可选择性填写，截至收尾仍只收到 **1 份**；汇总见 [`docs/group-feedback-summary-2026-11-10.md`](group-feedback-summary-2026-11-10.md)。单份问卷不能代表 5 位完成者，也不能据此宣称正式用户验证完成。
- 这些问题都不是 v0.1.0 的代码缺陷；问题 2 是指南长命令换行导致的复制问题，指南第 4.3/4.4 节已补防换行提示。
- 2026-11-11 起试用阶段收尾：不再等待更多问卷；后续如继续收集，另起一轮并按多份答卷汇总，不把 n=1 写成比例或“用户验证完成”。


