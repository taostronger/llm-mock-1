# 大模型调度算法复现

配套博士后研究报告的独立代码目录，可整体移动后建立仓库。包含两个请求路由算法的多集群1P1D时延模拟，以及Omni-EPLB静态部署函数和动态调整模型的复现。

这里生成的是**合成负载下的模型结果**。不启动vLLM、不加载模型、不需要GPU/NPU；模拟时延不是vLLM实测时延，也不是生产中TTFT降低10%的来源。

## 先了解研究与实验

新增的对外交流材料（2026-11-02）：

- [面试项目介绍 Beamer（PDF）](docs/beamer/project-introduction.pdf)：26 页主讲＋18 页技术备份，先介绍 OmniInfer、Omni-EPLB、数据平台、网关与 Agent 大项目，再展开个人模块和技术栈；无企业标志、无致谢页。
- [Beamer 源码与编译说明](docs/beamer/README.md)：提供可编辑 `.tex`、图表原始数据入口和讲述提示。
- [Simulator 独立技术报告](docs/simulator-technical-report.md)：真实插件接入、开环/闭环、经验后端与验证边界。
- [Delm / Harness² 独立技术报告](docs/delm-harness2-technical-report.md)：协作运行时、配置调优适配、可靠交付与真实回归结果。

以上新材料为脱敏技术概述，不含原始业务轨迹或源项目部署配置；未将其他项目的源码一并迁入。既有报告与答辩文件按历史版本保留，对外介绍可优先使用本次 Beamer。

本次新增原创交流材料采用 [限定范围的 MIT License](docs/NEW_MATERIALS_LICENSE.md)，不改变已有研究代码、第三方代码或归档文件的许可状态。

[算法、测试场景与博士后研究报告总结](docs/ALGORITHMS_SCENARIOS_REPORT.md)：介绍两个研究问题、算法一与算法二、EPLB静态和动态方案、全部测试场景，以及结果和复现方法。

报告与答辩材料：

- [博士后研究报告（Word）](docs/博士后研究报告-陶壮.docx)
- [博士后出站考核汇报（PPTX）](docs/博士后出站考核汇报-陶壮-学术简洁版-20260922.pptx)
- [博士后出站考核汇报（PDF）](docs/博士后出站考核汇报-陶壮-学术简洁版-20260922.pdf)

## 快速运行

推荐Python 3.11及以上；本次参考运行的精确版本见 results/reference/run_manifest.json。在此目录执行：

~~~bash
python -m venv .venv
# Windows PowerShell：.\.venv\Scripts\Activate.ps1
# Linux/macOS：source .venv/bin/activate
python -m pip install -r requirements-lock.txt
python -m unittest discover -s tests -v
python scripts/run_experiments.py --quick --out results/local/quick
~~~

完整复现实验：

~~~bash
python scripts/run_experiments.py --out results/local/full
python scripts/audit_results.py --results results/local/full
python scripts/summarize_results.py --results results/local/full
~~~

最后一个命令生成汇总CSV、JSON和RESULTS.md。需要图时：

~~~bash
python -m pip install ".[plots]"
python scripts/summarize_results.py --results results/local/full --plots
~~~

原报告中的数学核验：

~~~bash
python scripts/verification/placement_checks.py
python scripts/verification/queue_checks.py
python scripts/verification/cache_checks.py
python scripts/verification/session_switch_checks.py
~~~

## 内容

- src/llm_repro/routing.py：离散事件模拟，有限APC缓存、P等待、串行KV链路、D连续批处理和会话映射。
- src/llm_repro/eplb.py：调用静态部署函数；用过去窗口预测负载，模拟更新与权重复制开销。
- src/llm_repro/vendor/：原Omni-EPLB的两个静态函数、MIT许可和来源记录。
- scripts/run_experiments.py：固定场景、三个种子、公共输入轨迹。
- tests/test_models.py：解析时延、缓存驻留、阈值、候选取整、容量、token守恒及确定性检查。
- docs/MODEL.md：模型假设、参数、指标口径和实现边界。
- results/reference/：本报告采用的全部逐请求/逐步记录、汇总及配置。
- results/reference/RESULTS.md：结果阅读入口，包含退化场景。
- scripts/verification/：原报告的小规模枚举和排队公式核验。

## 复现对象

**请求路由：**算法一优先保持健康会话，新会话在最低 max(1,ceil(0.1N)) 个负载候选中选择；算法二只替换已有会话分支，按式（5.6）比较等待差和原后端缓存代价。两者使用相同拓扑、状态协议、请求轨迹和固定参数。另设逐请求轮询、最小预计等待两个对照。

**EPLB：**直接复用Omni-EPLB的副本分配和受约束贪心放置函数。动态窗口、更新门槛、整数量化和时延换算由本项目提供，不是生产C++运行时的等价实现。没有复现全模型通信、算子内核、Ascend设备性能或论文系统消融点值。

本目录不携带模型权重、真实业务请求或内部部署配置。第三方代码保留原许可；已有复现代码等其他自写部分尚未指定对外开源许可。2026-11-02 新增交流材料的许可范围见上文，不扩大到既有文件。
