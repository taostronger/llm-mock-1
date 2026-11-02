# 核心概念与学习方法

这是两章样式验证。正文采用宋体十一磅，保留原生公式、可更新目录和页码。长路径与代码需要自动换行，表格应有重复表头和灰色细边。

## 一个公式与一段代码

等待时间的参考公式为 $\rho=\lambda\mathbb E[S]<1$，以及

$$
\mathbb E[W]=\frac{\lambda\mathbb E[S^2]}{2(1-\rho)}.
$$

```python
def compute_workload(request, state):
    return state.waiting_tokens + request.input_tokens
example_path = 'examples/long-reading-path/runtime-and-toolchain/board-mcp-wrapper-and-native-event-replay-checks.py'
```

| 机制 | 含义 | 不能说明的事 |
|---|---|---|
| 状态日志 | 能够回放任务事件及负责人 | 不能直接证明正文全部持久化 |
| 内容哈希 | 判断输入或产物内容有无变化 | 不能证明代码语义正确 |

### 深入问题

**问题：为什么核心函数正确仍可能在接口处失败？** 包装器需要正确等待异步结果，并正确编码和传递错误。测试应覆盖边界，而不只是验证纯函数。

# 工程验证与局限

第二章应另起一页，正文不应全部与下一段捆绑；没有附加空白页。

## 追问与练习

1. 解释正常结束、工作证据、候选产物与验收通过的区别。
2. 写出输入快照、配置、运行轨迹和结果的对应关系。

这份文件只用于构建与渲染 smoke 验证，留在 build 目录，不作为最终交付。
