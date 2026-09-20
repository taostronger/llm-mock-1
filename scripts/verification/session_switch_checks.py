import json,random,math
from pathlib import Path
(Path(__file__).resolve().parents[2]/"results/verification").mkdir(parents=True,exist_ok=True)

def costs(w_a,w_b,theta_a,theta_b,n,v_a,v_b,kappa):
    stay=w_a+(1-theta_a)*n/v_a
    move=w_b+(1-theta_b)*n/v_b+kappa
    threshold=n*((1-theta_b)/v_b-(1-theta_a)/v_a)+kappa
    return {'stay':stay,'move':move,'threshold':threshold,'switch':move<stay,'gain':stay-move}

cases=[('原端缓存收益较大',(.7,.1,.8,0,1000,1000,1000,.05)),('原端复用较少',(.7,.1,.1,0,1000,1000,1000,.05)),('新端公共前缀更多',(.3,.1,.8,.9,1000,1000,1000,.05)),('新端速率减半',(.5,.1,.2,0,1000,1000,500,.05)),('等待更长但完整代价更低',(.1,.2,.2,0,1000,1000,2000,.05))]
result={'cases':[{'name':name,**costs(*args)} for name,args in cases]}
assert [v['switch'] for v in result['cases']]==[False,True,True,False,True]
rng=random.Random(20260920);checked=0
for _ in range(5000):
    wa,wb=rng.uniform(0,10),rng.uniform(0,10)
    ta,tb=rng.random(),rng.random();n=rng.uniform(1,100000)
    va,vb=rng.uniform(10,50000),rng.uniform(10,50000);k=rng.uniform(0,.3)
    c=costs(wa,wb,ta,tb,n,va,vb,k)
    assert math.isclose(c['gain'],wa-wb-c['threshold'],rel_tol=1e-10,abs_tol=1e-10)
    if abs(c['gain'])>1e-9:
        assert c['switch']==(wa-wb>c['threshold']);checked+=1
result['random_threshold_checks']=checked
result['algorithm_two_heterogeneous_counterexample']={'algorithm_two_decision':.4>1.2*.2,'general_decision':result['cases'][3]['switch']}
assert result['algorithm_two_heterogeneous_counterexample']=={'algorithm_two_decision':True,'general_decision':False}
result['zero_hit_fixed_cost_boundary']={'algorithm_two_decision':.03>0,'cost_aware_decision':costs(.03,0,0,0,1000,1000,1000,.05)['switch']}
assert not result['zero_hit_fixed_cost_boundary']['cost_aware_decision']
result['scope']='教学参数；仅核对代数、阈值和边界，不是生产性能实验'
(Path(__file__).resolve().parents[2]/'results/verification/session_switch_results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
