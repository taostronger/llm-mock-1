"""Recompute readable aggregates from per-run summary files; plots are optional."""
from pathlib import Path
import argparse,csv,json,statistics
ROOT=Path(__file__).resolve().parents[1]
ROUTE_LABELS={"steady_4":"稳态4集群","steady_8":"稳态8集群","steady_16":"稳态16集群","light_8":"低到达率","hot_shift_8":"热点转移","burst_8":"流量突发","decode_heavy_8":"长输出","small_cache_8":"小缓存","stale_8":"观测延迟","no_apc_8":"关闭APC"}
EPLB_LABELS={"steady":"稳态偏斜","shift":"热点突变","oscillate":"热点交替","uniform":"均匀激活","scale_4":"4设备突变","scale_16":"16设备突变","costly_shift":"高复制成本"}
def read(p):
    with p.open(encoding="utf-8",newline="") as f:return list(csv.DictReader(f))
def write(p,rows):
    with p.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def summarize(out,plots=False):
    routing=read(out/"routing_summary.csv");eplb=read(out/"eplb_summary.csv")
    data={"routing":[],"eplb":[]}
    for name,rows,key,metrics in [
      ("routing",routing,"policy",["ttft_mean_s","ttft_p95_s","e2e_mean_s","token_hit_ratio","switch_ratio"]),
      ("eplb",eplb,"mode",["mean_layer_ms","p95_layer_ms","mean_imbalance","layout_switches","weight_copies","flow_fallbacks"])]:
        for case in dict.fromkeys(r["case"] for r in rows):
            for mode in dict.fromkeys(r[key] for r in rows):
                group=[r for r in rows if r["case"]==case and r[key]==mode]
                data[name].append({"case":case,key:mode,"seeds":len(group),
                    **{m:statistics.mean(float(r[m]) for r in group) for m in metrics}})
        write(out/f"{name}_aggregate.csv",data[name])
    (out/"aggregates.json").write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    lines=["# 固定场景模拟结果","",
      "全部为合成输入下的模型时延；跨种子取各次指标的算术平均，P95列是各次P95的平均。",
      "相对变化为算法二/算法一−1；正值表示时延增加。生产10%收益不来自这些数据。","",
      "## 多套1P1D后端","",
      "| 场景 | 轮询均值/s | 最小等待均值/s | 算法一均值/s | 算法二均值/s | 二相对一 | 一P95/s | 二P95/s |",
      "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for case in dict.fromkeys(r["case"] for r in data["routing"]):
        d={r["policy"]:r for r in data["routing"] if r["case"]==case}
        a,b=d["algorithm_one"],d["algorithm_two"]
        lines.append(f"| {ROUTE_LABELS[case]} | {d['round_robin']['ttft_mean_s']:.4f} | {d['least_wait']['ttft_mean_s']:.4f} | {a['ttft_mean_s']:.4f} | {b['ttft_mean_s']:.4f} | {(b['ttft_mean_s']/a['ttft_mean_s']-1)*100:+.2f}% | {a['ttft_p95_s']:.4f} | {b['ttft_p95_s']:.4f} |")
    lines+=["","## EPLB单层时延（含测量窗口内的同步复制）","",
      "| 场景 | 均匀副本/ms | 静态/ms | 动态/ms | 动态相对静态 | 动态更新次数均值 |",
      "| --- | --- | --- | --- | --- | --- |"]
    for case in dict.fromkeys(r["case"] for r in data["eplb"]):
        d={r["mode"]:r for r in data["eplb"] if r["case"]==case}
        a,b=d["static"],d["dynamic"]
        lines.append(f"| {EPLB_LABELS[case]} | {d['uniform']['mean_layer_ms']:.4f} | {a['mean_layer_ms']:.4f} | {b['mean_layer_ms']:.4f} | {(b['mean_layer_ms']/a['mean_layer_ms']-1)*100:+.2f}% | {b['layout_switches']:.2f} |")
    lines+=["","模型和基线定义见 ../../docs/MODEL.md。逐请求/逐步记录、完整配置、源文件SHA随本目录保存。",
      "审查结果：算法二并非所有场景都更快；缓存容量和观测延迟可以改变取舍。EPLB的时延由激活量及假设速率换算，不是硬件测速。",""]
    (out/"RESULTS.md").write_text("\n".join(lines),encoding="utf-8")
    if plots:plot(out,data)
    return data
def plot(out,data):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    plt.rcParams.update({"font.family":["Microsoft YaHei","DejaVu Sans"],"axes.unicode_minus":False,
                        "font.size":10,"axes.spines.top":False,"axes.spines.right":False,
                        "savefig.dpi":200})
    folder=out/"figures";folder.mkdir(exist_ok=True)
    cases=list(dict.fromkeys(r["case"] for r in data["routing"]));x=np.arange(len(cases))
    fig,axes=plt.subplots(2,1,figsize=(10,7.2),sharex=True,layout="constrained")
    for ax,metric,title in zip(axes,["ttft_mean_s","ttft_p95_s"],["平均TTFT","P95 TTFT（各次P95的平均）"]):
        for i,(policy,label,color) in enumerate([("algorithm_one","算法一","#38638A"),("algorithm_two","算法二","#BC5747")]):
            vals=[next(r[metric] for r in data["routing"] if r["case"]==c and r["policy"]==policy) for c in cases]
            ax.bar(x+(i-.5)*.36,vals,.35,label=label,color=color)
        ax.set_yscale("log");ax.set_ylabel("时间 / s（对数刻度）");ax.set_title(title,loc="left")
        ax.grid(axis="y",alpha=.2);ax.set_axisbelow(True)
    axes[0].legend(frameon=False,ncols=2);axes[-1].set_xticks(x,[ROUTE_LABELS[c] for c in cases],rotation=22,ha="right")
    fig.savefig(folder/"routing_latency.png");plt.close(fig)
    cases=list(dict.fromkeys(r["case"] for r in data["eplb"]));x=np.arange(len(cases))
    fig,axes=plt.subplots(2,1,figsize=(10,7.2),layout="constrained")
    for i,(mode,label,color) in enumerate([("uniform","均匀副本基线","#AAB3BC"),("static","静态部署","#38638A"),("dynamic","动态调整","#BC5747")]):
        vals=[next(r["mean_layer_ms"] for r in data["eplb"] if r["case"]==c and r["mode"]==mode) for c in cases]
        axes[0].bar(x+(i-1)*.24,vals,.23,label=label,color=color)
    axes[0].set_xticks(x,[EPLB_LABELS[c] for c in cases],rotation=15,ha="right")
    axes[0].set_ylabel("单层平均时延 / ms");axes[0].legend(frameon=False,ncols=3);axes[0].grid(axis="y",alpha=.2);axes[0].set_axisbelow(True)
    for mode,label,color in [("static","静态部署","#38638A"),("dynamic","动态调整","#BC5747")]:
        rows=read(out/"eplb_steps"/f"shift_31_{mode}.csv")
        vals=np.asarray([float(r["layer_ms"]) for r in rows])
        smooth=np.convolve(vals,np.ones(8)/8,mode="valid")
        axes[1].plot(np.arange(7,len(vals)),smooth,label=label,color=color,lw=1.6)
    axes[1].axvline(180,color="#777777",ls="--",lw=1)
    axes[1].text(184,axes[1].get_ylim()[1]*.92,"热点变化",fontsize=9)
    axes[1].set_xlabel("执行步（种子31，8步移动平均）");axes[1].set_ylabel("单层时延 / ms")
    axes[1].grid(alpha=.2);axes[1].legend(frameon=False,ncols=2)
    fig.savefig(folder/"eplb_latency.png");plt.close(fig)
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--results",type=Path,default=ROOT/"results/reference");p.add_argument("--plots",action="store_true")
    a=p.parse_args();d=summarize(a.results,a.plots);print(json.dumps({k:len(v) for k,v in d.items()}))
