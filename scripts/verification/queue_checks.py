"""Numerical checks for the report's idealized queueing model, not a serving benchmark.
Run with Python 3.10+; standard library only. Outputs are written beside this file.
"""
from pathlib import Path
import json, math, random, csv

OUT=Path(__file__).resolve().parents[2]/'results/verification'
OUT.mkdir(parents=True,exist_ok=True)

def rates_at(nu,means,seconds):
    return [0.0 if nu<=m else (1-1/math.sqrt(1+2*m*(nu-m)/b))/m for m,b in zip(means,seconds)]

def allocate(arrival,means,seconds):
    assert all(m>0 and b>=m*m for m,b in zip(means,seconds))
    assert 0<arrival<sum(1/m for m in means)
    lo=min(means); hi=max(1.0,max(means))
    while sum(rates_at(hi,means,seconds))<arrival: hi*=2
    for _ in range(100):
        mid=(lo+hi)/2
        if sum(rates_at(mid,means,seconds))<arrival:lo=mid
        else:hi=mid
    return rates_at((lo+hi)/2,means,seconds),(lo+hi)/2

def response(rates,means,seconds):
    if any(x*m>=1 for x,m in zip(rates,means)):return None
    return sum(x*m+x*x*b/(2*(1-x*m)) for x,m,b in zip(rates,means,seconds))/sum(rates)

def derivative(x,m,b):return m+b*x*(2-m*x)/(2*(1-m*x)**2)

rng=random.Random(20260918)
cases=1000; max_kkt=max_mass=0.0
for _ in range(cases):
    n=rng.randint(2,12); means=[rng.uniform(.1,3) for _ in range(n)]
    seconds=[m*m*rng.uniform(1,6) for m in means]
    total=rng.uniform(.1,.95)*sum(1/m for m in means)
    xs,nu=allocate(total,means,seconds)
    max_mass=max(max_mass,abs(sum(xs)-total))
    max_kkt=max(max_kkt,max(abs(derivative(x,m,b)-nu) if x>1e-12 else max(0,nu-m) for x,m,b in zip(xs,means,seconds)))
    assert all(x>=0 and x*m<1 for x,m in zip(xs,means))
    assert abs(sum(xs)-total)<1e-10
    assert all(abs(derivative(x,m,b)-nu)<1e-8 if x>1e-12 else m>=nu-1e-10 for x,m,b in zip(xs,means,seconds))

means=[1,.5,.25]; seconds=[2*m*m for m in means]
optimal,nu=allocate(4,means,seconds)
proportional=[4/7,8/7,16/7]; uniform=[4/3]*3
example=[]
for name,xs in [('uniform',uniform),('capacity_proportional',proportional),('marginal_cost_optimal',optimal)]:
    example.append({'method':name,'rates':xs,'rho':[x*m for x,m in zip(xs,means)],'mean_response_s':response(xs,means,seconds)})
grid_best=float('inf');grid_rates=None;grid_count=0
for i in range(100):
    for j in range(200):
        xs=[i/100,j/100,4-(i+j)/100]
        if xs[-1]<0:continue
        val=response(xs,means,seconds)
        if val is None:continue
        grid_count+=1
        if val<grid_best:grid_best=val;grid_rates=xs
assert response(optimal,means,seconds)<=grid_best+1e-12

bound_cases=50000; bound_max_violation=0.0
for _ in range(bound_cases):
    n=rng.randint(1,32); k=rng.randint(1,n); eps=rng.uniform(0,3)
    true=[rng.uniform(0,30) for _ in range(n)]
    observed=[max(0,q+rng.uniform(-eps,eps)) for q in true]
    selected=sorted(range(n),key=lambda i:observed[i])[:k]
    limit=sorted(true)[k-1]+2*eps
    assert max(true[i] for i in selected)<=limit+1e-12

threshold_cases=50000; accepted=0; false_accepts=0
for _ in range(threshold_cases):
    eta=rng.uniform(0,2);cost=rng.uniform(0,5);delta=rng.uniform(.001,2)
    old=rng.uniform(0,30);new=rng.uniform(0,30)
    oldhat=old+rng.uniform(-eta,eta);newhat=new+rng.uniform(-eta,eta)
    if oldhat-newhat>cost+2*eta+delta:
        accepted+=1
        if old-new-cost<=delta:false_accepts+=1
assert false_accepts==0

result={'seed':20260918,'model':'independent FCFS M/G/1 queues; fixed independent routing probabilities',
        'kkt_checks':cases,'max_rate_sum_error':max_mass,'max_kkt_residual':max_kkt,
        'mm1_example':example,'grid':{'step':.01,'feasible_points':grid_count,'best_response_s':grid_best,'rates':grid_rates},
        'snapshot_checks':bound_cases,'snapshot_violations':0,
        'switch_checks':threshold_cases,'switch_accepted':accepted,'switch_false_accepts':false_accepts}
(OUT/'queue_results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
with (OUT/'mg1_curves.csv').open('w',newline='',encoding='utf-8') as f:
    w=csv.writer(f);w.writerow(['rho','cs2','mean_waiting_over_mean_service'])
    for cs2 in [0,1,4]:
        for i in range(1,96):
            rho=i/100;w.writerow([rho,cs2,rho*(1+cs2)/(2*(1-rho))])
print(json.dumps(result,ensure_ascii=False,indent=2))
