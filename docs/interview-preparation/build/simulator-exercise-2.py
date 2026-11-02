import math
xs = list(range(1, 21))
sim_p95 = xs[min(int(len(xs) * .95), len(xs) - 1)]
nearest_rank_p95 = xs[math.ceil(len(xs) * .95) - 1]
equal_cv = (.1 + .9 + .1) / 3
time_cv = (.1 * 1 + .9 * 8 + .1 * 1) / 10
assert (sim_p95, nearest_rank_p95) == (20, 19)
assert abs(time_cv - .74) < 1e-12
print(sim_p95, nearest_rank_p95, equal_cv, time_cv)
