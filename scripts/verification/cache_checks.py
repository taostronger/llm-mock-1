from pathlib import Path
(Path(__file__).resolve().parents[2]/"results/verification").mkdir(parents=True,exist_ok=True)
import json,math

def moments(h,hit=.2,miss=1):
    return h*hit+(1-h)*miss,h*hit**2+(1-h)*miss**2
def queue(lam,m,b):
    assert lam*m<1
    w=lam*b/(2*(1-lam*m))
    return {'mean':m,'second_moment':b,'rho':lam*m,'waiting':w,'response':m+w}
results={'description':'教学参数数值核验，不是线上实验','two_state':[]}
for h in [.2,.5,.8]:results['two_state'].append({'hit_probability':h,**queue(.6,*moments(h))})
assert [round(r['response'],4) for r in results['two_state']]==[1.3287,.8438,.4488]
results['same_token_ratio']=[queue(.6,.6,b) for b in [.36,.52]]
assert all(abs(r['waiting']-v)<1e-12 for r,v in zip(results['same_token_ratio'],[.16875,.24375]))
old=.25+moments(.9)[0];new=.05+moments(.1)[0]
assert abs(old-.53)<1e-12 and abs(new-.97)<1e-12
old2=.90+moments(.9)[0]
lower=old2-new-.05-2*.02
assert abs(lower-.12)<1e-12 and lower>.02
results['routing']={'old':old,'new':new,'congested_old':old2,'gain_lower_bound':lower}
# Check valid moments and the monotonic special case over the full hit-probability interval.
values=[]
for j in range(1001):
    m,b=moments(j/1000)
    assert b+1e-12>=m*m and 0<m<=1
    values.append(queue(.6,m,b)['response'])
assert all(a>=b for a,b in zip(values,values[1:]))
# Same request hit probability, different positive prefix coverage produces different mean work.
partial=.5*.1
full=.5*1
assert partial!=full
# Check the derivative including cache-rate feedback against a finite difference.
def hfun(x):return .2+.4*x/(1+x)
def objective(x):
    m,b=moments(hfun(x));return x*m+b*x*x/(2*(1-m*x))
derivative_errors=[]
for x in [.1,.3,.6]:
    m,b=moments(hfun(x));hp=.4/(1+x)**2;mp=-.8*hp;bp=-.96*hp
    base=m+b*x*(2-m*x)/(2*(1-m*x)**2)
    analytic=base+(x+b*x**3/(2*(1-m*x)**2))*mp+x*x/(2*(1-m*x))*bp
    numeric=(objective(x+1e-6)-objective(x-1e-6))/(2e-6)
    derivative_errors.append(abs(analytic-numeric));assert abs(analytic-numeric)<1e-8
results['checks']={'grid_points':1001,'feedback_derivative_max_error':max(derivative_errors),'passed':True}
(Path(__file__).resolve().parents[2]/'results/verification/cache_results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(results,ensure_ascii=False))


