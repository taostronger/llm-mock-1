import heapq

def closed(n, k, service):
    q, started, finished, t = [], 0, 0, 0.0
    while started < min(k, n):
        heapq.heappush(q, (service, started))
        started += 1
    while q:
        t, rid = heapq.heappop(q)
        finished += 1
        if started < n:
            heapq.heappush(q, (t + service, started))
            started += 1
        assert started - finished == len(q)
    return t, finished / t

assert closed(8, 2, 2.0) == (8.0, 1.0)
print(closed(8, 2, 2.0), closed(8, 4, 2.0))
