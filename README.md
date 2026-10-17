# Debias: memory you can audit

**A bias-aware memory graph for AI agents, built on FalkorDB.**
Graph Hacks (WeMakeDevs × FalkorDB), October 2026. Track: **02 Agent Memory and Coordination**.

Agents remember, but their memories have no immune system. A user's offhand claim gets stored as fact. A conclusion the agent made up three sessions ago gets cited as evidence today. A stale note recalled four times starts to feel true because it's familiar. A peer agent's guess in a handoff gets built on.

Debias writes every memory into FalkorDB with its provenance. Then, before the agent acts, it runs five **pure-Cypher detectors** over the claims the agent is about to rely on. No LLM judges anything. The graph structure itself shows why a memory shouldn't be trusted.

```python
from debias import debias, write_claim

claim = write_claim("Refund window is 90 days", "user", "customer")

with debias("support") as guard:           # opens a session for agent "support"
    check = guard.relies_on([claim])        # logs the recall, runs the detectors
    if check.flags:
        system_prompt += "\n" + check.note  # policy="inject" (default)
# debias("support", policy="escalate") raises DebiasEscalation for a human instead
```

```
[debias] Before you rely on these memories, note the following. ...
- Flag (sycophancy): citing claim #21c060, asserted by user `customer`, never verified.
```

## Demo video

**[Debias — Run the Line](https://youtu.be/60dPDV3XvsQ)** (2:54) — the demo cut to my song “Run the Line.”


## Why a graph

Every bias here is a relationship problem:

| Bias | What it looks like in the graph |
|---|---|
| Sycophancy | a user-asserted claim with no high-trust `VERIFIED_BY` edge |
| Self-reinforcement | a `SUPPORTS` cycle through the agent's own claims |
| Bandwagon | a peer agent's unverified claim, or a `DERIVED_FROM` path to one |
| Repetition ≠ truth | many `RECALLED_IN` sessions, zero verification |
| Anchoring | a newer, verified claim that `CONTRADICTS` an older one still being recalled |

In a graph, each one is a single query. Take FalkorDB out and there's nothing left to detect.

## Graph data model

```
(:Source {kind, name})            kind: user | agent | tool | doc
(:Claim {id, text, norm, created_at})
(:Session {id, agent, started_at})
(:Evidence {kind, ref})

(Claim)-[:ASSERTED_BY]->(Source)          who first said it
(Claim)-[:RECALLED_IN]->(Session)         it surfaced in this session
(Claim)-[:SUPPORTS]->(Claim)              used as evidence for
(Claim)-[:CONTRADICTS]->(Claim)           argues against (newer -> older)
(Claim)-[:DERIVED_FROM]->(Claim)          restatement of another source's claim (writer-attached)
(Claim)-[:VERIFIED_BY {trust}]->(Evidence) trust: "high" | "low" (writer-assigned)
```

**The writer is trusted infrastructure, and the agent never sets trust.** In `debias/writer.py`:
- `add_evidence(kind="tool")` gets `high` trust.
- `add_evidence(kind="doc")` gets `high` only if the URL's host is in `TRUSTED_DOC_DOMAINS`. Otherwise it gets `low`.
- When an agent asserts a claim whose normalized text (`strip().casefold()`) matches a claim from a different source, the writer adds `DERIVED_FROM`. Restating a user's or peer's unverified claim keeps its taint.

A claim counts as verified **only** if it has a `VERIFIED_BY {trust: "high"}` edge.

## The Cypher the product depends on

These are the five detectors in `debias/detectors.py`. The guard scopes them to the claims the agent is about to rely on.

**Sycophancy** (user-asserted and never verified, plus claims derived from one)
```cypher
MATCH (c:Claim)-[:ASSERTED_BY]->(s:Source {kind: "user"})
WHERE NOT (c)-[:VERIFIED_BY {trust: "high"}]->(:Evidence)
RETURN c.id, c.text, s.name

MATCH (c:Claim)-[:DERIVED_FROM*1..]->(o:Claim), (o)-[:ASSERTED_BY]->(s:Source {kind: "user"})
WHERE NOT (c)-[:VERIFIED_BY {trust: "high"}]->(:Evidence)
  AND NOT (o)-[:VERIFIED_BY {trust: "high"}]->(:Evidence)
RETURN DISTINCT c.id, c.text, s.name
```

**Repetition ≠ truth** (recalled in 3 or more sessions, never verified)
```cypher
MATCH (c:Claim)-[:RECALLED_IN]->(s:Session)
WHERE NOT (c)-[:VERIFIED_BY {trust: "high"}]->(:Evidence)
WITH c, count(DISTINCT s) AS recalls
WHERE recalls >= 3
RETURN c.id, c.text, recalls
```

**Multi-agent bandwagon** (a peer agent's unverified claim; a derived variant mirrors sycophancy's)
```cypher
MATCH (c:Claim)-[:ASSERTED_BY]->(a:Source {kind: "agent"})
WHERE a.name <> $agent AND NOT (c)-[:VERIFIED_BY {trust: "high"}]->(:Evidence)
RETURN c.id, c.text, a.name
```

**Self-reinforcement** (support cycles of any length through the agent's own unverified claims)
```cypher
MATCH (c:Claim)-[:SUPPORTS*1..]->(c), (c)-[:ASSERTED_BY]->(a:Source {kind: "agent", name: $agent})
WHERE NOT (c)-[:VERIFIED_BY {trust: "high"}]->(:Evidence)
RETURN DISTINCT c.id, c.text
```

**Anchoring** (an older unverified claim still recalled after a newer, verified contradiction)
```cypher
MATCH (n:Claim)-[:CONTRADICTS]->(c:Claim),
      (n)-[:VERIFIED_BY {trust: "high"}]->(:Evidence),
      (c)-[:RECALLED_IN]->(:Session)
WHERE n.created_at > c.created_at
  AND NOT (c)-[:VERIFIED_BY {trust: "high"}]->(:Evidence)
RETURN DISTINCT c.id, c.text, n.id, n.text
```

**Optional: semantic repetition** (`debias/semantic.py`). This one is opt-in and isn't part of `DETECTORS`. It embeds unverified recalled claims with a local nomic-embed-text server, clusters paraphrases at cosine ≥ 0.80 (untuned), and applies the ≥3-session rule to each cluster.

FalkorDB dialect notes: string literals must be double-quoted (including inside `NOT()` patterns), and `EXISTS {}` subqueries aren't supported, so we use `WHERE NOT (pattern)`.

## Red-teaming our own detectors

`redteam/redteam_battery.py` attacks the memory graph with 15 cases: 5 obvious controls and 10 structural evasions.

1. **Round one:** all 5 obvious attacks were caught. All 10 evasions got through.
2. **The master key:** one false claim ("FalkorDB was shut down in 2025") with one bogus citation got **0 hits**, because any `VERIFIED_BY` edge counted as verification.
3. **Five hardenings, with still no LLM in the loop:** evidence trust tiers, unbounded `SUPPORTS*1..` cycles, normalized claim matching, writer-attached `DERIVED_FROM` taint, and optional semantic repetition.
4. **Round two:** all 15 cases match their expected outcome. The master key now fires **4** detectors.

The remaining misses are by design and documented in `redteam/README.md`: a support chain that isn't a cycle, a claim recalled fewer than 3 times, a novel self-assertion with no derivation, and anchoring without a verified `CONTRADICTS` edge. Full transcripts are in `redteam_transcripts.jsonl`.

## Local setup

No live deployment. Everything runs locally against FalkorDB in Docker. Tested with Python 3.14 and the `falkordb` client 1.7.1.

```bash
# 1. FalkorDB
docker run -d --name falkordb -p 6379:6379 falkordb/falkordb:latest
#    (later: docker start falkordb)

# 2. Python client
git clone https://github.com/NososAnosos/graph-hacks-debias.git
cd graph-hacks-debias
python3 -m pip install falkordb

# 3. Smoke test: plants one sycophancy case and checks it's flagged
python3 -m debias.smoke

# 4. Context-manager test: all five traps, a clean control, and escalation (scratch graph)
python3 -m debias.test_guard

# 5. Red-team battery: 15 cases, writes redteam_transcripts.jsonl
python3 redteam/redteam_battery.py
```

The package connects to `localhost:6379` and uses the graph `debias_experiment` (`debias/writer.py`). The tests use their own scratch graph.

**Optional semantic repetition:** serve an OpenAI-compatible embeddings endpoint for `nomic-embed-text` at `http://127.0.0.1:18435/v1/embeddings`. The battery checks for it at start. If the endpoint is up, case R3 expects a catch. If not, R3 falls back to the deterministic detector and is expected to miss.

## Layout

```
debias/
  writer.py      provenance writer: claims, sources, sessions, evidence trust, DERIVED_FROM
  detectors.py   the five Cypher detectors
  guard.py       `with debias(agent):` context manager, inject or escalate
  semantic.py    opt-in paraphrase-aware repetition (local embeddings)
  smoke.py, test_guard.py
redteam/         15-case adversarial battery + verification re-runs
docs/            CONCEPT, ARCHITECTURE, DEMO, PLAN
video/           demo video segments (HyperFrames)
```

## AI assistance disclosure

I used AI coding assistants (Claude Code, Kimi Code, and agent tooling) to write parts of the code and the video segments. I designed the concept, the graph model, the detector logic, and the red-team cases, and I ran and verified the battery and the fixes myself.

## License

MIT
