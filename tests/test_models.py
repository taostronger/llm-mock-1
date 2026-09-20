"""Analytic checks and invariants, independent of claimed performance benefits."""
from pathlib import Path
import sys,unittest,math
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from llm_repro.routing import Config,Request,PrefixCache,simulate,make_trace,choose_backend
from llm_repro.eplb import placement,flow_placement,legal,execute_load,predicted_load,simulate_eplb
import numpy as np
class ServingTests(unittest.TestCase):
    def request(self,i=0,t=0.,session=0,n=320,out=2):
        return Request(i,t,session,n,out,tuple(("s",session,k) for k in range(n//32)))
    def config(self,**kw):
        return Config(requests=1,clusters=1,warmup_fraction=0,decode_context_seconds=0,**kw)
    def test_single_request_time_identity(self):
        c=self.config();s,rows=simulate(c,"algorithm_one",[self.request()])
        p=c.prefill_fixed+320/c.prefill_tps+320*c.context_seconds_per_token
        x=c.kv_fixed+320/c.kv_tps;dt=max(c.decode_min_step,1/c.decode_tps)
        self.assertAlmostEqual(rows[0]["ttft"],p+x+dt)
        self.assertAlmostEqual(rows[0]["e2e"],p+x+2*dt)
    def test_cache_reuse_requires_execution_and_residence(self):
        c=self.config()
        _,r=simulate(c,"algorithm_one",[self.request(),self.request(1,10.)])
        self.assertEqual(r[0]["hit_tokens"],0);self.assertEqual(r[1]["hit_tokens"],320)
        self.assertLess(r[1]["p_service"],r[0]["p_service"])
    def test_same_session_cache_disabled(self):
        c=self.config(cache_enabled=False)
        _,r=simulate(c,"algorithm_one",[self.request(),self.request(1,10.)])
        self.assertEqual(r[1]["hit_tokens"],0)
    def test_other_backend_does_not_inherit_cache(self):
        c=Config(requests=2,clusters=2,warmup_fraction=0)
        _,r=simulate(c,"round_robin",[self.request(),self.request(1,10.)])
        self.assertEqual([a["hit_tokens"] for a in r],[0,0])
    def test_lru_eviction(self):
        c=PrefixCache(2);c.insert([("a",0),("a",1)]);c.insert([("b",0)])
        self.assertEqual(c.lookup([("a",0),("a",1)]),0)
    def test_prefix_mismatch_stops_reuse(self):
        c=PrefixCache(5);c.insert([("a",0),("a",1)])
        self.assertEqual(c.lookup([("x",0),("a",1)]),0)
    def test_switch_threshold_and_missing_signals(self):
        c=Config(clusters=2,prefill_tps=1000,alpha=.2)
        r=self.request();binding={0:0}
        snap=[dict(wait=2.,hit=.5,avg_prompt=1000,inflight=4),
              dict(wait=0.,hit=.1,avg_prompt=1000,inflight=0)]
        self.assertEqual(choose_backend("algorithm_one",r,c,binding,snap,[0,0]),(0,False))
        self.assertEqual(choose_backend("algorithm_two",r,c,binding,snap,[0,0]),(1,True))
        snap[0]["wait"]=.6
        self.assertEqual(choose_backend("algorithm_two",r,c,binding,snap,[0,0]),(0,False))
        snap[0]["wait"]=2.;snap[0]["hit"]=None
        self.assertEqual(choose_backend("algorithm_two",r,c,binding,snap,[0,0]),(0,False))
    def test_batch_capacity_causality_and_determinism(self):
        c=Config(requests=70,clusters=2,arrival_rate=8,decode_slots=3,seed=7)
        trace=make_trace(c);s,r=simulate(c,"algorithm_two",trace);s2,r2=simulate(c,"algorithm_two",trace)
        self.assertEqual(s,s2);self.assertEqual(r,r2)
        self.assertLessEqual(s["max_decode_batch"],3)
        self.assertEqual(len(r),70)
        self.assertTrue(all(x["ttft"]<=x["e2e"] for x in r))
    def test_candidate_count_rounds_up_as_equation_5_1(self):
        c=Config(clusters=11)
        snap=[dict(wait=i,hit=0,avg_prompt=1000,inflight=i) for i in range(11)]
        selected={choose_backend("algorithm_one",self.request(i),c,{},snap,[0]*11)[0]
                  for i in range(100)}
        self.assertEqual(selected,{0,1})
    def test_invalid_rates(self):
        with self.assertRaises(ValueError):simulate(self.config(prefill_tps=0),"algorithm_one")
    def test_invalid_steps_and_warmup(self):
        for kw in [dict(observation_period=0), dict(warmup_fraction=1), dict(cache_blocks=-1)]:
            c=Config(requests=1, **kw)
            with self.assertRaises(ValueError): simulate(c,"algorithm_one")
    def test_empty_trace(self):
        with self.assertRaises(ValueError): simulate(self.config(),"algorithm_one",[])
class PlacementTests(unittest.TestCase):
    def test_capacity_and_token_conservation(self):
        x,_=placement([12.,8.,4.,2.],2,3)
        self.assertTrue(legal(x,x.sum(axis=0),3))
        loads=execute_load(x,[13,7,3,2],0);self.assertEqual(int(loads.sum()),25)
    def test_flow_feasibility(self):
        x=flow_placement([3,2,2,1],4,2)
        self.assertTrue(legal(x,[3,2,2,1],2))
    def test_infeasible(self):
        with self.assertRaises(ValueError):flow_placement([3],2,1)
    def test_proxy_load_sum(self):
        x=flow_placement([2,1,1],2,2)
        self.assertAlmostEqual(sum(predicted_load(x,[9,5,3])),17.)
    def test_invalid_eplb_configuration(self):
        with self.assertRaises(ValueError):simulate_eplb(capacity=33)
        with self.assertRaises(ValueError):simulate_eplb(mode="typo")
    def test_positive_timing_and_reproducibility(self):
        a,rows=simulate_eplb(steps=50,seed=3);b,rows2=simulate_eplb(steps=50,seed=3)
        self.assertEqual(a,b);self.assertEqual(rows,rows2)
        self.assertTrue(all(x["layer_ms"]>=x["compute_ms"]>0 for x in rows))
if __name__=="__main__":unittest.main()
