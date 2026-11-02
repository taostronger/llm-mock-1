# 大模型系统与智能体工程：Beamer 项目介绍

这份中文技术交流稿介绍专家负载均衡、元数据治理、推理路由、服务 simulator，以及 DELM 适配与 Harness2。面向对外学术和工程交流，保留个人贡献与团队/上游能力的区别。封面不使用企业标志，正文没有致谢页。

- [放映 PDF](project-introduction.pdf)
- [可编辑 Beamer 源文件](project-introduction.tex)
- [讲述提示](speaker-notes.md)
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

共 34 页，正文 30 页、技术附录 4 页。正文按五个方向展开，附录包含数学性质、统计口径、排队分析与资料入口。短交流可按讲述提示选取 14 页；完整讲述适合约 30–40 分钟并另留问答时间。

若只转交演示稿源码，可把 `.tex` 与 `data/` 放在同一目录，再运行两遍 `xelatex project-introduction.tex`。这种方式直接使用随附图表摘录，不需要 Python 或完整实验仓库；从仓库重新同步数据则使用上面的 `build.py`。

图中的“示意”数据只解释机制；两张定量实验图完全来自已有公开合成参考结果，不是 GPU/NPU 测量。Simulator 的条件回放一致性、执行模型预测能力、策略反事实排序分别讨论。Agent 单元回归的通过项和未通过/未执行项均保留，不把机制测试改写为任务成功率收益。

本目录不含公司部署图、内部链接、原始业务轨迹、员工信息、凭证、未公开验收指标，亦不分发被研究的 Agent 项目源码。公开讲解某个模块的设计，不意味着该模块的全部源码已有对外分发许可。仓库现有第三方代码及其他材料的许可范围不因此改变。

本次新增原创报告、Beamer 源码与生成演示稿采用 [MIT License（限定文件范围）](../NEW_MATERIALS_LICENSE.md)。
