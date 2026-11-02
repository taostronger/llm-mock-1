# 手册构建、核查与练习

本目录保存生成54页学习手册所用工具的可维护版本。最终Word/PDF/Markdown位于上一级；依赖、源项目、历史渲染PNG和构建中间文件未打包。迁移只调整工具配置，不改手册正文或重新生成已核查交付文件。

## 生成Word

需要Codex托管Python/Node依赖（Python端含python-docx，Node端含docx），以及Pandoc。默认托管目录为当前用户的 `.cache/codex-runtimes/codex-primary-runtime`；可用环境变量指定另一个已准备好的目录。工具不会安装依赖。

在本手册目录 `docs/interview-preparation` 下运行：

```powershell
$manualRuntime = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime'
$env:CODEX_MANUAL_RUNTIME = $manualRuntime
$manualPython = Join-Path $manualRuntime 'dependencies/python/python.exe'
& $manualPython ./build/build_handbook.py
```

默认读取上一级的 `项目面试准备手册-陶壮.md`，输出同名Word。`--input`、`--output` 可改路径。构建链是 `create_reference.cjs` 创建样式→Pandoc生成原生公式/表格/目录字段→`polish_docx.py` 统一Letter、宋体11pt、黑色标题和表格页码。普通构建不要求渲染器；自动目录内容仍需Word或渲染步骤更新。

## 渲染与目录更新

```powershell
& $manualPython ./build/build_handbook.py --render
# 只检查小型样式样本，不覆盖正式手册：
& $manualPython ./build/build_handbook.py --smoke
```

当前备用渲染路径要求Windows和本机Microsoft Word。`render_with_word.py` 加载已安装的 `render_docx.py`，只在该进程替换PDF转换函数；`word_export.ps1` 隐藏启动Word、禁用宏/链接更新、更新目录和页码、保存Word并导出PDF，再由原渲染器与Poppler生成PNG。它只关闭自己的文档和Word实例。首次还保留原渲染器的诊断，缺LibreOffice时可在日志看到原因。

可配置环境变量：

| 变量 | 含义 |
|---|---|
| `CODEX_MANUAL_RUNTIME` | 托管runtime根，含 `dependencies/python`、`dependencies/node` 等 |
| `CODEX_MANUAL_PANDOC` | Pandoc可执行文件；默认先查PATH，再查当前用户安装目录 |
| `CODEX_MANUAL_RENDERER` | 已安装 `render_docx.py` 文件；未指定时在当前用户的documents插件缓存中查找 |
| `CODEX_MANUAL_POPPLER` | Poppler二进制目录；默认使用托管runtime目录 |
| `CODEX_MANUAL_PWSH` | PowerShell可执行文件；默认使用托管runtime内的pwsh.exe |

渲染器不随本仓库分发。没有该文件时，`--render` 会清楚报错；可显式配置后重试，或只构建Word。`--qa-dir` 可指定渲染目录；仅对build内目标子目录的旧 `page-*.png` 作逐文件清理，避免减少页数后残留旧图，不递归清空目录。生成的日志、原始Word、PNG和测试JSON由 `.gitignore` 排除。渲染成功不等于视觉验收，修改正文后仍须检查所有页面。

## 内容核查

```powershell
& $manualPython ./build/validate_handbook.py --final --docx
```

脚本对照七章和合并稿，统计问题、练习、围栏与链接，检查Word标题/正文/代码/表格覆盖、原生数学对象、审阅残留及常见敏感信息模式。报告写入本地 `build/validation-report.json`。源码导航含作者工作区绝对路径，在其他机器上可能报告目标不存在；这不表示项目源文件随仓库提供。零模式命中不等于全面泄密审计，文本覆盖不证明公式数学等价或页面排版正确；请阅读报告里的限制。

## 无模型练习

```powershell
& $manualPython ./build/simulator-exercise-1.py
& $manualPython ./build/simulator-exercise-2.py
```

两个脚本仅用Python标准库，分别演算理想闭环并发，以及P95/CV的口径差异；数字均为合成例子，不代表生产容量或延迟。

Agent序号探针需要本人有权读取的外部源码快照，含 `server/src/board.js`；本仓库不附该项目代码。Node路径可按前面runtime配置：

```powershell
$env:CODEX_AGENT_SOURCE_ROOT = 'E:/authorized-checkouts/agent-platform'
$manualNode = Join-Path $manualRuntime 'dependencies/node/bin/node.exe'
& $manualNode ./build/agent-sequence-probe.cjs
```

也可将源码根作为首个位置参数。未提供路径或缺少board.js时会报错，不输出伪造的通过结果。探针调用真实Board类，不调用SDK或模型，输出六步状态及超时事件到本地JSON；序号依赖手册所核对的源码版本，其他版本应重新检查事件追加规则。另一边界探针见上一级 `chapters/agent-boundary-probes.cjs`，其依赖配置见手册入口。
