"""Expert placement reproduction and per-MoE-layer synthetic timing."""
from collections import deque
import numpy as np
from .vendor.omni_eplb_static import allocate_expert_deployments_improved, distribute_experts_to_ranks

def legal(x, replicas, capacity):
    x = np.asarray(x)
    return bool(np.all((x == 0)|(x == 1)) and
                np.all(x.sum(axis=0) == replicas) and
                np.all(x.sum(axis=1) <= capacity))

def flow_placement(replicas, ranks, capacity):
    """Feasibility fallback, not a load optimizer; complete bipartite max flow."""
    e = len(replicas); sink = 1+e+ranks
    residual = np.zeros((sink+1,sink+1),dtype=int)
    for i,r in enumerate(replicas):
        residual[0,1+i] = r
        residual[1+i,1+e:1+e+ranks] = 1
    for j in range(ranks):
        residual[1+e+j,sink] = capacity
    value = 0
    while True:
        parent = [-1]*(sink+1); parent[0] = 0; queue = deque([0])
        while queue and parent[sink] == -1:
            u = queue.popleft()
            for v in np.flatnonzero(residual[u]):
                if parent[v] == -1:
                    parent[v] = u; queue.append(int(v))
        if parent[sink] == -1:
            break
        v = sink
        while v:
            u = parent[v]; residual[u,v] -= 1; residual[v,u] += 1; v = u
        value += 1
    if value != sum(replicas):
        raise ValueError("infeasible placement constraints")
    x = np.zeros((ranks,e),dtype=int)
    for j in range(ranks):
        for i in range(e):
            x[j,i] = residual[1+e+j,1+i]
    assert legal(x,replicas,capacity)
    return x

def placement(loads, ranks, capacity):
    e = len(loads); budget = ranks*capacity-e
    if budget < 0:
        raise ValueError("insufficient slots")
    replicas = allocate_expert_deployments_improved(list(loads), ranks-1, budget,
                                                    is_redundant=True)
    fallback = False
    try:
        _, x = distribute_experts_to_ranks(list(loads), replicas, ranks)
    except RuntimeError:
        x = flow_placement(replicas,ranks,capacity)
        fallback = True
    assert legal(x,replicas,capacity)
    return x, fallback

def uniform_placement(experts, ranks, capacity):
    replicas = [1]*experts
    for k in range(ranks*capacity-experts):
        replicas[k%experts] += 1
    return flow_placement(replicas,ranks,capacity)

def predicted_load(x, counts):
    return np.asarray(x) @ (np.asarray(counts)/np.asarray(x).sum(axis=0))

def execute_load(x, counts, step):
    """Integer tokens, round-robin among physical replicas; conservation is exact."""
    loads = np.zeros(len(x),dtype=int)
    for e,c in enumerate(counts):
        loc = np.flatnonzero(x[:,e]); q, rem = divmod(int(c),len(loc))
        loads[loc] += q
        for k in range(rem):
            loads[loc[(step+k)%len(loc)]] += 1
    assert loads.sum() == sum(counts)
    return loads

def make_activation_trace(experts=32, steps=360, seed=31, scenario="shift", tokens=1024):
    rng = np.random.default_rng(seed)
    weights = np.asarray([(i+1)**-1.3 for i in range(experts)]); weights /= weights.sum()
    if scenario == "uniform":
        weights = np.ones(experts)/experts
    training = rng.multinomial(tokens, weights, size=80).mean(axis=0)
    trace = []
    for t in range(steps):
        if scenario == "uniform":
            p = np.ones(experts)/experts
        elif scenario == "shift" and t >= steps//2:
            p = np.roll(weights,experts//2)
        elif scenario == "oscillate":
            p = np.roll(weights,(t//12 % 2)*(experts//2))
        else:
            p = weights
        trace.append(rng.multinomial(tokens,p))
    return training,np.asarray(trace)

def simulate_eplb(experts=32, ranks=8, capacity=6, steps=360, seed=31,
                  scenario="shift", mode="dynamic", copy_ms=0.15,
                  compute_tokens_per_ms=96.0, update_interval=16, window=32):
    if min(experts, ranks, capacity, steps, update_interval, window) < 1:
        raise ValueError("positive dimensions and update windows required")
    if capacity > experts or ranks*capacity < experts:
        raise ValueError("infeasible slot count")
    if copy_ms < 0 or compute_tokens_per_ms <= 0:
        raise ValueError("invalid timing parameters")
    if mode not in ("uniform", "static", "dynamic"):
        raise ValueError("unknown placement mode")
    train, trace = make_activation_trace(experts,steps,seed,scenario)
    fallback_count = 0
    if mode == "uniform":
        x = uniform_placement(experts,ranks,capacity)
    else:
        x,f = placement(train,ranks,capacity); fallback_count += int(f)
    history = deque(maxlen=window); rows=[]; switches=0; copies=0
    for step, counts in enumerate(trace):
        transfer = 0.
        if mode == "dynamic" and history and step % update_interval == 0:
            forecast = np.mean(history,axis=0)
            old = predicted_load(x,forecast)
            if max(old)/np.mean(old) > 1.10:
                candidate,f = placement(forecast,ranks,capacity); fallback_count += int(f)
                new = predicted_load(candidate,forecast)
                added = int(np.sum((candidate == 1)&(x == 0)))
                cost = added*copy_ms
                saving = (max(old)-max(new))/compute_tokens_per_ms
                # Explicit finite-horizon model, evaluated only on past observations.
                if max(new) < .97*max(old) and window*saving > cost:
                    x = candidate; transfer = cost; switches += 1; copies += added
        loads = execute_load(x,counts,step)
        compute = .08 + max(loads)/compute_tokens_per_ms
        rows.append({"step":step,"compute_ms":float(compute),"migration_ms":transfer,
          "layer_ms":float(compute+transfer),"imbalance":float(max(loads)/np.mean(loads)),
          "tokens":int(sum(counts)),"max_device_tokens":int(max(loads))})
        history.append(counts)
        assert legal(x,x.sum(axis=0),capacity)
    vals=np.asarray([r["layer_ms"] for r in rows])
    summary={"scenario":scenario,"seed":seed,"mode":mode,"experts":experts,
      "ranks":ranks,"capacity":capacity,"steps":steps,
      "mean_layer_ms":float(vals.mean()),"p95_layer_ms":float(np.sort(vals)[int(np.ceil(.95*len(vals)))-1]),
      "mean_imbalance":float(np.mean([r["imbalance"] for r in rows])),
      "layout_switches":switches,"weight_copies":copies,"flow_fallbacks":fallback_count,
      "migration_total_ms":copies*copy_ms,"activation_total":int(trace.sum())}
    return summary,rows
