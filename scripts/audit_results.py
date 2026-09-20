"""Independently recalculate summaries from emitted event records."""
from pathlib import Path
import argparse,csv,json,math,hashlib
ROOT=Path(__file__).resolve().parents[1]
def read(p):
    with p.open(encoding="utf-8",newline="") as f:return list(csv.DictReader(f))
def near(a,b):assert math.isclose(float(a),float(b),rel_tol=1e-10,abs_tol=1e-9),(a,b)
def audit(out):
    route=read(out/"routing_summary.csv");eplb=read(out/"eplb_summary.csv")
    configs={(c["case"],str(c["seed"])):c for c in json.loads((out/"routing_configs.json").read_text())}
    groups={}
    for s in route:
        key=(s["case"],s["seed"]);groups.setdefault(key,set()).add(s["trace_sha256"])
        rows=read(out/"routing_requests"/f"{s['case']}_{s['seed']}_{s['policy']}.csv")
        cfg=configs[key];m=rows[int(len(rows)*cfg["warmup_fraction"]):]
        assert len(rows)==int(s["requests"]) and len(m)==int(s["measured"])
        for r in rows:
            times=[float(r[k]) for k in ["arrival","p_start","p_end","kv_start","kv_end","d_start","first","end"]]
            assert times==sorted(times)
            near(r["ttft"],float(r["first"])-float(r["arrival"]))
            near(r["ttft"],sum(float(r[k]) for k in ["p_wait","p_service","kv_wait","d_wait","decode_first"])+float(r["kv_end"])-float(r["kv_start"]))
            assert 0<=int(r["hit_tokens"])<=int(r["prompt"])
        vals=sorted(float(r["ttft"]) for r in m)
        near(s["ttft_mean_s"],sum(vals)/len(vals));near(s["ttft_p95_s"],vals[math.ceil(.95*len(vals))-1])
        near(s["token_hit_ratio"],sum(int(r["hit_tokens"]) for r in m)/sum(int(r["prompt"]) for r in m))
        assert int(s["max_decode_batch"])<=cfg["decode_slots"]
    assert all(len(v)==1 for v in groups.values())
    for s in eplb:
        rows=read(out/"eplb_steps"/f"{s['case']}_{s['seed']}_{s['mode']}.csv")
        vals=sorted(float(r["layer_ms"]) for r in rows)
        near(s["mean_layer_ms"],sum(vals)/len(vals));near(s["p95_layer_ms"],vals[math.ceil(.95*len(vals))-1])
        near(s["migration_total_ms"],sum(float(r["migration_ms"]) for r in rows))
        assert sum(int(r["tokens"]) for r in rows)==int(s["activation_total"])
        for r in rows:near(r["layer_ms"],float(r["compute_ms"])+float(r["migration_ms"]))
    manifest=json.loads((out/"run_manifest.json").read_text())
    for relative,digest in manifest["code_sha256"].items():
        assert hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()==digest,relative
    result={"passed":True,"routing_runs":len(route),"eplb_runs":len(eplb),
            "common_trace_groups":len(groups),"recomputed":"causality, decomposition, means, P95, APC, migration, conservation, source hashes"}
    (out/"audit.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result));return result
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--results",type=Path,default=ROOT/"results/reference")
    audit(p.parse_args().results)
