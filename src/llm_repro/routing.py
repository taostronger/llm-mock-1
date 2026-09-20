"""Discrete-event network of N independent 1P1D serving backends.

P: one non-preemptive FCFS effective prefill server with a finite APC block LRU.
KV: one serial link per backend. D: iteration-level continuous batches.
This is an explicit performance model, not a vLLM engine emulator.
"""
from dataclasses import dataclass, field, asdict
from collections import deque, OrderedDict
import heapq, math, random, hashlib, json

@dataclass(frozen=True)
class Request:
    id: int
    arrival: float
    session: int
    prompt: int
    output: int
    prefix: tuple
    affinity: bool = True
    shape: str = "A"

@dataclass
class Config:
    clusters: int = 8
    requests: int = 1800
    seed: int = 31
    arrival_rate: float = 14.0
    sessions: int = 160
    prefill_tps: float = 3600.0
    prefill_fixed: float = 0.008
    context_seconds_per_token: float = 0.000003
    decode_tps: float = 900.0
    decode_min_step: float = 0.025
    decode_context_seconds: float = 0.001
    decode_slots: int = 16
    kv_tps: float = 180000.0
    kv_fixed: float = 0.003
    block_size: int = 32
    cache_blocks: int = 8192
    observation_period: float = 0.25
    observation_delay: float = 0.0
    hit_window: int = 120
    alpha: float = 0.2
    mean_output_estimate: float = 112.0
    long_output: bool = False
    scenario: str = "steady"
    cache_enabled: bool = True
    warmup_fraction: float = 0.20

class PrefixCache:
    """Block keys contain the complete abstract prefix path, not only session IDs."""
    def __init__(self, capacity, block_size=32):
        self.capacity, self.block_size = capacity, block_size
        self.data = OrderedDict()
    def lookup(self, keys, touch=True):
        hit = 0
        for key in keys:
            if key not in self.data:
                break
            hit += self.block_size
            if touch:
                self.data.move_to_end(key)
        return hit
    def insert(self, keys):
        if not self.capacity:
            return
        for key in keys:
            self.data[key] = None
            self.data.move_to_end(key)
            while len(self.data) > self.capacity:
                self.data.popitem(last=False)

@dataclass
class Backend:
    cache: PrefixCache
    p_queue: deque = field(default_factory=deque)
    p_active: int | None = None
    p_finish: float = 0.0
    link_free: float = 0.0
    d_queue: deque = field(default_factory=deque)
    d_active: list = field(default_factory=list)
    d_scheduled: bool = False
    history: deque = field(default_factory=deque)
    p_busy: float = 0.0
    d_busy: float = 0.0
    max_decode_batch: int = 0

def uniform_for(seed, request_id, salt=0):
    raw = f"{seed}:{request_id}:{salt}".encode()
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big") / 2**64

def make_trace(cfg):
    """Fixed open-loop synthetic prompts; generated text never changes later inputs."""
    rng = random.Random(cfg.seed)
    time, counts, trace = 0.0, [0] * cfg.sessions, []
    # Zipf sessions, with a hot-set change or a mid-trace arrival burst.
    base = [(i + 1)**-0.9 for i in range(cfg.sessions)]
    for k in range(cfg.requests):
        stage = k / max(1, cfg.requests)
        rate = cfg.arrival_rate
        if cfg.scenario == "burst" and 0.35 <= stage < 0.65:
            rate *= 2.8
        time += rng.expovariate(rate)
        sid = rng.choices(range(cfg.sessions), weights=base, k=1)[0]
        if cfg.scenario in ("hot_shift", "burst") and stage >= 0.4:
            sid = (sid + cfg.sessions//2) % cfg.sessions
        turn = counts[sid]; counts[sid] += 1
        # Stable shared system prefix + session-specific history, growing at most 1K.
        base_len = (512, 1024, 2048, 4096)[sid % 4]
        history = min(1024, 64 * turn)
        prompt = base_len + history + 128
        affinity = rng.random() < 0.9
        output = rng.choice([64, 96, 128, 160])
        if cfg.long_output:
            output *= 4
        if not affinity:
            prompt = rng.choice([256, 512, 2048, 4096])
        blocks = prompt // cfg.block_size
        keys = []
        for j in range(blocks):
            if affinity and j < 8:
                key = ("system", j)
            elif affinity and j < blocks - 4:
                key = ("session", sid, j)
            else:
                key = ("request", k, j)
            keys.append(key)
        trace.append(Request(k, time, sid, prompt, output, tuple(keys), affinity,
                             "A" if prompt >= 1024 else "B"))
    return trace

def trace_digest(trace):
    raw = json.dumps([asdict(x) for x in trace], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()

def choose_backend(policy, req, cfg, binding, snapshot, reservation):
    """No access to future arrivals, true output length, or unobserved cache contents."""
    n = cfg.clusters
    waits = [s["wait"] + reservation[i] for i, s in enumerate(snapshot)]
    loads = [s["inflight"] + reservation[i] * cfg.prefill_tps /
             max(1.0, s["avg_prompt"]) for i, s in enumerate(snapshot)]
    stable_rank = lambda values: sorted(range(n), key=lambda i: (values[i],
                        uniform_for(cfg.seed, req.id, i + 300)))
    previous = binding.get(req.session) if req.affinity else None
    if policy == "round_robin":
        return req.id % n, previous is not None and previous != req.id % n
    if policy == "least_wait":
        chosen = stable_rank(waits)[0]
        return chosen, previous is not None and previous != chosen
    if policy not in ("algorithm_one", "algorithm_two"):
        raise ValueError(policy)
    if previous is not None:
        if policy == "algorithm_one":
            return previous, False
        candidate = stable_rank(waits)[0]
        s = snapshot[previous]
        if candidate == previous or s["hit"] is None:
            return previous, False
        threshold = (1 + cfg.alpha) * s["hit"] * s["avg_prompt"] / cfg.prefill_tps
        if waits[previous] - waits[candidate] > threshold:
            return candidate, True
        return previous, False
    if req.affinity:
        k = max(1, math.ceil(0.1 * n))
        candidates = stable_rank(loads)[:k]
        return candidates[min(k-1, int(uniform_for(cfg.seed, req.id, 42)*k))], False
    if req.shape == "A":
        return stable_rank(loads)[0], False
    return int(uniform_for(cfg.seed, req.session, 95) * n) % n, False

def simulate(cfg, policy, trace=None):
    if cfg.clusters < 1 or cfg.requests < 1 or cfg.decode_slots < 1:
        raise ValueError("positive counts required")
    if cfg.prefill_tps <= 0 or cfg.decode_tps <= 0 or cfg.kv_tps <= 0:
        raise ValueError("positive rates required")
    if cfg.observation_period <= 0 or cfg.decode_min_step <= 0 or cfg.block_size <= 0:
        raise ValueError("positive time steps and block size required")
    if cfg.arrival_rate <= 0 or cfg.sessions < 1 or cfg.hit_window < 1:
        raise ValueError("positive arrival rate, sessions and history window required")
    if cfg.cache_blocks < 0 or cfg.observation_delay < 0 or not 0 <= cfg.warmup_fraction < 1:
        raise ValueError("invalid cache, observation delay or warmup")
    if min(cfg.prefill_fixed, cfg.kv_fixed, cfg.context_seconds_per_token,
           cfg.decode_context_seconds, cfg.alpha) < 0:
        raise ValueError("nonnegative overhead and margin required")
    trace = make_trace(cfg) if trace is None else list(trace)
    if not trace or any(r.prompt < 1 or r.output < 1 or r.arrival < 0 for r in trace):
        raise ValueError("nonempty valid request trace required")
    if any(a.arrival > b.arrival for a,b in zip(trace,trace[1:])):
        raise ValueError("request trace must be sorted by arrival")
    byid = {r.id:r for r in trace}
    assert len(byid) == len(trace)
    backends = [Backend(PrefixCache(cfg.cache_blocks if cfg.cache_enabled else 0,
                                   cfg.block_size)) for _ in range(cfg.clusters)]
    states, events, binding = {}, [], {}
    serial = 0
    def push(time, priority, kind, data):
        nonlocal serial
        serial += 1
        heapq.heappush(events, (time, priority, serial, kind, data))
    for req in trace:
        states[req.id] = {"id":req.id, "arrival":req.arrival, "output":req.output,
                         "prompt":req.prompt, "session":req.session}
        push(req.arrival, 3, "arrival", req.id)
    snapshot = [{"wait":0., "inflight":0, "hit":None, "avg_prompt":2048.}
                for _ in backends]
    reservation = [0.] * cfg.clusters
    sampled = 0
    global_history = deque(maxlen=cfg.hit_window*cfg.clusters)
    remaining = {}
    done = 0
    max_events = max(10000, len(trace)*max(r.output for r in trace)*8)
    event_count = 0

    def decode_dt(b, ids):
        mean_context = sum(states[i]["prompt"] + byid[i].output - remaining[i]
                           for i in ids) / len(ids)
        return max(cfg.decode_min_step, len(ids)/cfg.decode_tps) + \
               cfg.decode_context_seconds * mean_context/2048

    def start_decode(j, now):
        b = backends[j]
        if b.d_scheduled:
            return
        while b.d_queue and len(b.d_active) < cfg.decode_slots:
            i = b.d_queue.popleft()
            states[i]["d_start"] = now
            b.d_active.append(i)
        if b.d_active:
            batch = tuple(b.d_active)
            dt = decode_dt(b, batch)
            b.d_busy += dt
            b.max_decode_batch = max(b.max_decode_batch, len(batch))
            b.d_scheduled = True
            push(now + dt, 0, "decode", (j, batch))

    def start_prefill(j, now):
        b = backends[j]
        if b.p_active is not None or not b.p_queue:
            return
        i = b.p_queue.popleft(); r = byid[i]
        hit = min(r.prompt, b.cache.lookup(r.prefix))
        duration = cfg.prefill_fixed + (r.prompt-hit)/cfg.prefill_tps + \
                   cfg.context_seconds_per_token*r.prompt
        states[i].update(p_start=now, hit_tokens=hit, p_service=duration)
        b.p_active, b.p_finish = i, now + duration
        b.p_busy += duration
        push(b.p_finish, 0, "prefill", (j, i))

    push(0., 1, "observe", None)
    while events:
        now, _, _, kind, data = heapq.heappop(events)
        event_count += 1
        if event_count > max_events:
            raise RuntimeError("event limit exceeded")
        if kind == "arrival":
            r = byid[data]
            j, switched = choose_backend(policy, r, cfg, binding, snapshot, reservation)
            old = binding.get(r.session)
            if r.affinity:
                binding[r.session] = j
            states[data].update(cluster=j, switched=int(switched), old_cluster=old)
            reservation[j] += snapshot[j]["avg_prompt"] * \
                              (1-(snapshot[j]["hit"] or 0.))/cfg.prefill_tps
            backends[j].p_queue.append(data)
            start_prefill(j, now)
        elif kind == "prefill":
            j, i = data; b = backends[j]; r = byid[i]; s = states[i]
            assert b.p_active == i
            s["p_end"] = now
            b.cache.insert(r.prefix)
            b.history.append((s["hit_tokens"], r.prompt))
            while len(b.history) > cfg.hit_window:
                b.history.popleft()
            global_history.append(r.prompt)
            b.p_active = None
            link_start = max(now, b.link_free)
            link_time = cfg.kv_fixed + r.prompt/cfg.kv_tps
            b.link_free = link_start + link_time
            s.update(kv_start=link_start, kv_end=b.link_free)
            push(b.link_free, 0, "kv", (j, i))
            start_prefill(j, now)
        elif kind == "kv":
            j, i = data
            remaining[i] = byid[i].output
            backends[j].d_queue.append(i)
            start_decode(j, now)
        elif kind == "decode":
            j, batch = data; b = backends[j]
            b.d_scheduled = False
            for i in batch:
                if "first" not in states[i]:
                    states[i]["first"] = now
                remaining[i] -= 1
                if remaining[i] == 0:
                    states[i]["end"] = now
                    b.d_active.remove(i); done += 1
            start_decode(j, now)
        elif kind == "observe":
            if done == len(trace):
                continue
            avg = sum(global_history)/len(global_history) if global_history else 2048.
            current = []
            for b in backends:
                total = sum(n for _,n in b.history)
                hit = sum(h for h,_ in b.history)/total if total else None
                p_wait = max(0.,b.p_finish-now) if b.p_active is not None else 0.
                p_wait += len(b.p_queue) * (cfg.prefill_fixed +
                        avg*(1-(hit or 0.))/cfg.prefill_tps +
                        cfg.context_seconds_per_token*avg)
                # D delay proxy uses observed counts and configured output estimate.
                # It does not inspect true remaining output lengths.
                step = max(cfg.decode_min_step, cfg.decode_slots/cfg.decode_tps) + \
                       cfg.decode_context_seconds*avg/2048
                groups = max(0., (len(b.d_queue)+len(b.d_active)-
                                 cfg.decode_slots+1)/cfg.decode_slots)
                d_wait = groups * cfg.mean_output_estimate * step
                current.append({"wait":p_wait + max(0.,b.link_free-now) + d_wait,
                                "inflight":len(b.p_queue)+int(b.p_active is not None)+
                                           len(b.d_queue)+len(b.d_active),
                                "hit":hit, "avg_prompt":avg})
            push(now + cfg.observation_delay, 2, "publish", current)
            push(now + cfg.observation_period, 1, "observe", None)
        elif kind == "publish":
            snapshot = data
            reservation = [0.] * cfg.clusters
            sampled += 1
    assert done == len(trace)
    records = []
    for r in trace:
        s = states[r.id]
        s.update(ttft=s["first"]-r.arrival, e2e=s["end"]-r.arrival,
                 p_wait=s["p_start"]-r.arrival, kv_wait=s["kv_start"]-s["p_end"],
                 d_wait=s["d_start"]-s["kv_end"],
                 decode_first=s["first"]-s["d_start"])
        assert r.arrival <= s["p_start"] <= s["p_end"] <= s["kv_start"] <= \
               s["kv_end"] <= s["d_start"] <= s["first"] <= s["end"]
        assert s["hit_tokens"] <= r.prompt
        assert abs(s["ttft"]-(s["p_wait"]+s["p_service"]+
                    s["kv_end"]-s["p_end"]+s["d_wait"]+s["decode_first"])) < 1e-7
        records.append(s)
    cut = int(len(records)*cfg.warmup_fraction)
    measured = records[cut:]
    percentile = lambda values,p: sorted(values)[max(0,math.ceil(p*len(values))-1)]
    mean = lambda key: sum(s[key] for s in measured)/len(measured)
    span = max(s["end"] for s in records)-min(s["arrival"] for s in records)
    summary = {"policy":policy, "scenario":cfg.scenario, "seed":cfg.seed,
       "clusters":cfg.clusters, "requests":len(records), "measured":len(measured),
       "trace_sha256":trace_digest(trace), "ttft_mean_s":mean("ttft"),
       "ttft_p95_s":percentile([s["ttft"] for s in measured],.95),
       "e2e_mean_s":mean("e2e"), "e2e_p95_s":percentile([s["e2e"] for s in measured],.95),
       "p_wait_mean_s":mean("p_wait"), "prefill_mean_s":mean("p_service"),
       "d_wait_mean_s":mean("d_wait"),
       "token_hit_ratio":sum(s["hit_tokens"] for s in measured)/sum(s["prompt"] for s in measured),
       "switch_ratio":mean("switched"), "completed_rps":len(records)/span,
       "drain_seconds":max(s["end"] for s in records)-max(s["arrival"] for s in records),
       "max_decode_batch":max(b.max_decode_batch for b in backends),
       "observation_samples":sampled}
    return summary, records
