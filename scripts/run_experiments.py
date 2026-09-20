"""Run fixed scenarios with common traces and deterministic routing randomness."""
from pathlib import Path
import argparse,csv,json,sys,platform,hashlib,logging
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"src"))
from llm_repro.routing import Config,make_trace,simulate
from llm_repro.eplb import simulate_eplb
logging.disable(logging.WARNING)

def csv_out(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",type=Path,default=ROOT/"results"/"reference")
    parser.add_argument("--quick",action="store_true")
    args=parser.parse_args();out=args.out;out.mkdir(parents=True,exist_ok=True)
    seeds=[31] if args.quick else [31,47,89]
    routing=[];configs=[]
    # Fixed scenarios, no parameter selection based on an algorithm's measured benefit.
    scenarios=[
      ("steady_4",dict(clusters=4,arrival_rate=7)),
      ("steady_8",dict(clusters=8,arrival_rate=14)),
      ("steady_16",dict(clusters=16,arrival_rate=28)),
      ("light_8",dict(clusters=8,arrival_rate=4)),
      ("hot_shift_8",dict(clusters=8,arrival_rate=14,scenario="hot_shift")),
      ("burst_8",dict(clusters=8,arrival_rate=14,scenario="burst")),
      ("decode_heavy_8",dict(clusters=8,arrival_rate=6,long_output=True,mean_output_estimate=448)),
      ("small_cache_8",dict(clusters=8,arrival_rate=14,cache_blocks=1024)),
      ("stale_8",dict(clusters=8,arrival_rate=14,observation_delay=2.0)),
      ("no_apc_8",dict(clusters=8,arrival_rate=14,cache_enabled=False)),
    ]
    if args.quick:scenarios=scenarios[:3]
    for name,options in scenarios:
        for seed in seeds:
            cfg=Config(seed=seed,requests=400 if args.quick else 1800,**options)
            from dataclasses import asdict
            configs.append({"case":name,**asdict(cfg)})
            trace=make_trace(cfg)
            for policy in ["round_robin","least_wait","algorithm_one","algorithm_two"]:
                summary,rows=simulate(cfg,policy,trace);summary["case"]=name;routing.append(summary)
                csv_out(out/"routing_requests"/f"{name}_{seed}_{policy}.csv",rows)
            print("routing",name,seed,flush=True)
    csv_out(out/"routing_summary.csv",routing)
    (out/"routing_configs.json").write_text(json.dumps(configs,ensure_ascii=False,indent=2),encoding="utf-8")
    eplb=[];econfigs=[]
    ecases=[("steady","steady",32,8,6,.15),("shift","shift",32,8,6,.15),
            ("oscillate","oscillate",32,8,6,.15),("uniform","uniform",32,8,6,.15),
            ("scale_4","shift",16,4,6,.15),("scale_16","shift",64,16,6,.15),
            ("costly_shift","shift",32,8,6,1.5)]
    if args.quick:ecases=ecases[:2]
    for name,scenario,experts,ranks,capacity,cost in ecases:
        for seed in seeds:
            c=dict(experts=experts,ranks=ranks,capacity=capacity,seed=seed,scenario=scenario,
                   copy_ms=cost,steps=100 if args.quick else 360)
            econfigs.append({"case":name,**c})
            for mode in ["uniform","static","dynamic"]:
                s,rows=simulate_eplb(**c,mode=mode);s["case"]=name;eplb.append(s)
                csv_out(out/"eplb_steps"/f"{name}_{seed}_{mode}.csv",rows)
            print("eplb",name,seed,flush=True)
    csv_out(out/"eplb_summary.csv",eplb)
    (out/"eplb_configs.json").write_text(json.dumps(econfigs,indent=2),encoding="utf-8")
    import numpy
    manifest={"python":platform.python_version(),"numpy":numpy.__version__,
        "routing_runs":len(routing),"eplb_runs":len(eplb),
        "simulation_only":True,"seeds":seeds,
        "code_sha256":{str(p.relative_to(ROOT)).replace("\\","/"):hashlib.sha256(p.read_bytes()).hexdigest()
           for folder in [ROOT/"src",ROOT/"scripts"] for p in sorted(folder.rglob("*.py"))}}
    (out/"run_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
if __name__=="__main__":main()
