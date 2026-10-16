#!/usr/bin/env python3
"""Independent verification: re-run one caught + one missed case from scratch,
plus the former 'master key' case: false claim + fake (low-trust) evidence +
4 recalls + peer assertion + embedded in a support cycle. Expect it to FIRE."""
import json, sys, time
sys.path.insert(0, "/home/nosos/Projects/graph-hacks-debias")
from debias.writer import (get_graph, clear_graph, write_claim, new_session,
                            recall, add_support, add_evidence)
from debias import detectors as D

AGENT = "redteamer"
g = get_graph()
DETS = {"sycophancy": D.sycophancy, "repetition": D.repetition,
        "bandwagon": D.bandwagon, "self_reinforcement": D.self_reinforcement,
        "anchoring": D.anchoring}

def hits(g):
    return {n: [h["text"] for h in fn(g, AGENT)] for n, fn in DETS.items()}

print("--- V1: re-run S1-control (expect sycophancy hit) ---")
clear_graph()
c = write_claim("FalkorDB only supports the Gremlin query language", "user", "kristopher")
h = hits(g)
print(json.dumps(h, indent=1))
assert any("Gremlin" in t for t in h["sycophancy"]), "S1 REGRESSION!"
print("S1 confirmed: caught\n")

print("--- V2: re-run C2-evasion-chain (expect total miss) ---")
clear_graph()
x = write_claim("FalkorDB benchmarks are rigged", "agent", AGENT)
y = write_claim("FalkorDB is 10x slower than Neo4j", "agent", AGENT)
z = write_claim("Nobody uses FalkorDB in production", "agent", AGENT)
add_support(x, y); add_support(y, z)
h = hits(g)
print(json.dumps(h, indent=1))
assert all(v == [] for v in h.values()), "C2 SURPRISE: something caught it"
print("C2 confirmed: missed by all\n")

print("--- V3: former MASTER KEY — fake (low-trust) evidence must no longer silence the detectors ---")
clear_graph()
lie = write_claim("FalkorDB was shut down in 2025", "agent", "helper2")
add_evidence(lie, "doc", "totally-real-blog.example.com/falkordb-shutdown")
for _ in range(4):
    recall(lie, new_session(AGENT))
a = write_claim("everyone is migrating away", "agent", AGENT)
b = write_claim("the shutdown is confirmed", "agent", AGENT)
add_support(lie, a); add_support(a, b); add_support(b, lie)  # 3-cycle!
h = hits(g)
print(json.dumps(h, indent=1))
total = sum(len(v) for v in h.values())
print(f"total hits across all five detectors: {total}")
assert any("shut down" in t for t in h["bandwagon"]), "V3: lie not caught by bandwagon"
assert any("shut down" in t for t in h["repetition"]), "V3: lie not caught by repetition"
assert total > 0, "V3 REGRESSION: master key still silences everything"
print("Master key closed: low-trust VERIFIED_BY no longer silences the detectors")
