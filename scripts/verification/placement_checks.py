from pathlib import Path
from itertools import product, combinations
from fractions import Fraction as F
import ast, heapq, json, logging
import numpy as np
from typing import List, Tuple, Union, Optional

OUT = Path(__file__).resolve().parents[2]/'results/verification'
OUT.mkdir(parents=True,exist_ok=True)
import argparse
parser=argparse.ArgumentParser()
parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[2]/'src/llm_repro/vendor/omni_eplb_static.py')
source=parser.parse_args().source
tree = ast.parse(source.read_text(encoding='utf-8'))
names = {'allocate_expert_deployments_improved', 'distribute_experts_to_ranks'}
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names], type_ignores=[]), str(source), 'exec'))
logging.disable(logging.CRITICAL)

def score(a, r):
    return max(F(x, y) for x,y in zip(a,r))

checks = 0
for E in range(1,5):
    for a in product(range(4), repeat=E):
        for cap in (1,2,3):
            opts = list(product(range(1,cap+1), repeat=E))
            for R in range(E*(cap-1)+2):
                got = allocate_expert_deployments_improved(list(a), cap-1, R, is_redundant=True)
                optimum = min(score(a,r) for r in opts if sum(r)-E<=R)
                assert score(a,got)==optimum, (a,cap,R,got,optimum)
                checks += 1

def best_placement(a,r,D,C):
    loads=[F(0)]*D
    counts=[0]*D
    best=None
    best_x=None
    rows=[]
    def dfs(e):
        nonlocal best,best_x
        if e==len(a):
            value=max(loads)
            if best is None or value<best:
                best=value
                best_x=[list(z) for z in rows]
            return
        for ds in combinations(range(D),r[e]):
            if any(counts[d]>=C for d in ds):
                continue
            for d in ds: counts[d]+=1;loads[d]+=F(a[e],r[e])
            rows.append(ds)
            if best is None or max(loads)<best: dfs(e+1)
            rows.pop()
            for d in ds: counts[d]-=1;loads[d]-=F(a[e],r[e])
    dfs(0)
    return best,best_x

counterexample=None
E,D,R=4,3,2
for a in product(range(1,8),repeat=E):
    if list(a)!=sorted(a,reverse=True): continue
    rg=allocate_expert_deployments_improved(list(a),2,R,is_redundant=True)
    bg,xg=best_placement(a,rg,D,2)
    for ra in product(range(1,D+1),repeat=E):
        if sum(ra)!=E+R: continue
        ba,xa=best_placement(a,ra,D,2)
        if ba is not None and bg is not None and ba<bg:
            counterexample=dict(loads=a,greedy_replicas=rg,greedy_replica_objective=str(score(a,rg)),greedy_best_device_load=str(bg),greedy_placement=xg,alternative_replicas=ra,alternative_replica_objective=str(score(a,ra)),alternative_device_load=str(ba),alternative_placement=xa)
            break
    if counterexample: break

example_loads=[100,90,10,9,8,7,1]
example_r=[1,1,1,1,1,1,3]
try:
    distribute_experts_to_ranks(example_loads,example_r,3)
    deadend='did not fail'
except Exception as e:
    deadend=type(e).__name__+': '+str(e)
feasible,layout=best_placement(example_loads,example_r,3,3)
result={'replica_exact_exhaustive_cases':checks,'domain':'E=1..4, each load=0..3, common cap=1..3, extra budget=0..E*(cap-1)+1; original Python allocation function extracted by AST; rational objective oracle','counterexample_two_stage':counterexample,'placement_deadend':{'loads':example_loads,'replicas':example_r,'ranks':3,'slots':3,'greedy_result':deadend,'feasible_best_load':str(feasible),'feasible_layout':layout},'scope':'Mathematical finite sanity checks; not hardware or production performance experiments.'}
(OUT/'placement_results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))

