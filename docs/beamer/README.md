# 大模型基础设施与 Agent 工程：面试项目介绍

面向不熟悉这些项目的面试官，先介绍各个大项目的目标、整体架构和上下游关系，再定位个人职责、实际使用的技术，以及代表性实现。内容覆盖推理系统、数据平台、网关、simulator 与 Agent 工程。保留个人贡献与团队/上游能力的区别；不使用企业标志或致谢页。

- [面试放映 PDF](project-introduction.pdf)
- [可编辑 Beamer 源文件](project-introduction.tex)
- [逐页讲述提示与开场话术](speaker-notes.md)
- [Simulator 独立报告](../simulator-technical-report.md)
- [DELM / Harness2 独立报告](../delm-harness2-technical-report.md)

## 本地编译

需要 Python 3.11+ 与包含 XeLaTeX 的 TeX Live 或 MiKTeX；安装 `beamer`、`ctex`、Fandol 字体、TikZ、PGFPlots。Python 脚本只使用标准库。

在本目录执行：

```bash
python build.py
```

脚本从仓库 `results/reference/` 的两个汇总 CSV 同步图表数据，执行两遍 XeLaTeX，再生成本目录 PDF。中间产物放在仓库忽略的 `_build/beamer/`。中文采用 TeX 发行版提供的 Fandol 字体，不依赖 Windows 专有字体。不要手改 `data/` 中的数值，应修改或重新生成正式实验记录后重建。

## 内容与使用

共 44 页：**26 页面试主讲＋18 页技术备份**。主讲页脚显示“页码/26”，备份页显示“备份 1–18”。主讲适合约 25–35 分钟；15–20 分钟可按讲述提示选页，备份无需顺序播放。

| 主讲页 | 项目及重点 |
|---|---|
| 1–2 | 项目全景与个人工作范围 |
| 3–10 | OmniInfer 总体框架、OmniPlacement 能力、Omni-EPLB 独立 SDK；个人核心与外围协作、接口及交付 |
| 11–14 | 企业数据工程平台与上游 DataHub；注册 SDK、身份权限、页面与 Data Agent |
| 15–19 | Omni-ELB 的 LiteLLM 路径与个人路由/状态工作；simulator 的项目背景与接口 |
| 20–24 | 编码 Agent 平台整体；Delm 与 Harness² 的位置、个人实现和可靠性案例 |
| 25–26 | 技术栈与可进一步展开的代表问题 |

大项目、上游框架和本人模块分别归因。Omni-EPLB 不代表替代全部 OmniInfer；独立交付不重复统计同源算法。内部平台采用功能名称介绍。数据平台的 React/TypeScript 与编码 Agent 平台的原生 JavaScript/CodeMirror 分别说明。

若只转交演示稿源码，可把 `.tex` 与 `data/` 放在同一目录，再运行两遍 `xelatex project-introduction.tex`。这种方式直接使用随附图表摘录，不需要 Python 或完整实验仓库；从仓库重新同步数据则使用上面的 `build.py`。

图中的“示意”数据只解释机制；两张定量实验图完全来自已有公开合成参考结果，不是 GPU/NPU 测量。Simulator 的条件回放一致性、执行模型预测能力、策略反事实排序分别讨论。Agent 单元回归的通过项和未通过/未执行项均保留，不把机制测试改写为任务成功率收益。

本目录不含公司部署图、内部链接、原始业务轨迹、员工信息、凭证、未公开验收指标，亦不分发被研究的 Agent 项目源码。公开讲解某个模块的设计，不意味着该模块的全部源码已有对外分发许可。仓库现有第三方代码及其他材料的许可范围不因此改变。

本次新增原创报告、Beamer 源码与生成演示稿采用 [MIT License（限定文件范围）](../NEW_MATERIALS_LICENSE.md)。
