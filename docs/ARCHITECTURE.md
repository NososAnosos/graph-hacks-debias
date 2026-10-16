# Architecture

## Graph schema (FalkorDB, Cypher)

Nodes:
- `Claim {id, text, created_at}` — one atomic belief.
- `Source {kind, name}` — kind in {user, agent, tool, doc}; `name` tells two
  agents apart (`"A"`, `"B"`).
- `Session {id, agent, started_at}` — one session of one agent.
- `Evidence {kind, ref}` — tool output, doc passage, etc.

Edges:
- `(Claim)-[:ASSERTED_BY]->(Source)` — who first said it.
- `(Claim)-[:SUPPORTS]->(Claim)` — claim used as evidence for claim.
- `(Claim)-[:CONTRADICTS]->(Claim)` — claim argues against claim.
- `(Claim)-[:VERIFIED_BY {trust}]->(Evidence)` — verification, with a trust
  tier (`"high"` | `"low"`) assigned by the writer, never by the agent.
- `(Claim)-[:RECALLED_IN]->(Session)` — claim surfaced in a session.

### Evidence trust tiers

The writer is trusted infrastructure; detectors are pure structural queries.
`writer.add_evidence(claim_id, kind, ref, trust=None)` derives trust:

- `kind == "tool"` → `high` (machine-generated output).
- `kind == "doc"` → `high` only if `ref` is an http(s) URL whose host is in
  `writer.TRUSTED_DOC_DOMAINS` (or a subdomain); otherwise `low`.
- anything else → `low`.

`trust=` overrides the derivation (tests only). Every detector treats a claim
as verified only if it has a `VERIFIED_BY {trust: "high"}` edge. A claim whose
only evidence is low-trust counts as unverified everywhere. This closes the
"master key" hole where one bogus citation silenced all five detectors.

### Derivation taint (DERIVED_FROM)

`(Claim)-[:DERIVED_FROM]->(Claim)` is attached by the writer, never the agent.
In `write_claim`, when an *agent* asserts a claim whose `strip().casefold()`
text (stored as `Claim.norm`) exactly matches an existing claim asserted by a
different source (a user, or another agent name), the new claim gets a
DERIVED_FROM edge to that origin. Restating a user's or peer's unverified claim
as your own therefore keeps its taint:

- Sycophancy also flags claims that reach an unverified user claim via
  `DERIVED_FROM*1..`.
- Bandwagon also flags claims that reach an unverified peer-agent claim the
  same way.

Limits: exact match only (paraphrases are not linked); a novel self-assertion
with no derivation stays outside bandwagon's contract.

## Detector queries (v1 sketches)

Five detectors, every one a pure structural query: no LLM judges anything.
The context manager scopes each to the claims the agent is about to rely on
(`c.id IN $ids`, omitted below for readability; `$agent` is the running
agent's `Source.name`). Not yet run against FalkorDB except where noted in the
dialect section; smoke-test each on Day 2.

Sycophancy — user-asserted, never verified, plus claims derived from one:
```cypher
MATCH (c:Claim)-[:ASSERTED_BY]->(s:Source {kind: "user"})
WHERE NOT (c)-[:VERIFIED_BY {trust: "high"}]->(:Evidence)
RETURN c.id, c.text

// derived variant (bandwagon is identical with a peer agent as the origin)
MATCH (c:Claim)-[:DERIVED_FROM*1..]->(o:Claim), (o)-[:ASSERTED_BY]->(s:Source {kind: "user"})
WHERE NOT (c)-[:VERIFIED_BY {trust: "high"}]->(:Evidence)
  AND NOT (o)-[:VERIFIED_BY {trust: "high"}]->(:Evidence)
RETURN DISTINCT c.id, c.text, s.name
```

Repetition-is-not-truth — recalled again and again, never verified. Counts
sessions, so a claim that merely sits in the graph never trips it:
```cypher
MATCH (c:Claim)-[:RECALLED_IN]->(s:Session)
WHERE NOT (c)-[:VERIFIED_BY {trust: "high"}]->(:Evidence)
WITH c, count(DISTINCT s) AS recalls
WHERE recalls >= 3
RETURN c.id, c.text, recalls
```

Multi-agent bandwagon — another agent's unverified claim, about to be used as
fact. Same shape as sycophancy; the source is a peer, not the user:
```cypher
MATCH (c:Claim)-[:ASSERTED_BY]->(a:Source {kind: "agent"})
WHERE a.name <> $agent
  AND NOT (c)-[:VERIFIED_BY {trust: "high"}]->(:Evidence)
RETURN c.id, c.text, a.name
```

Self-reinforcement — support cycles of any length through the agent's own
unverified claims (the old `*1..3` cap let a 4-cycle through; now unbounded):
```cypher
MATCH (c:Claim)-[:SUPPORTS*1..]->(c), (c)-[:ASSERTED_BY]->(:Source {kind: "agent"})
WHERE NOT (c)-[:VERIFIED_BY {trust: "high"}]->(:Evidence)
RETURN DISTINCT c.id, c.text
```

Anchoring — an unverified claim keeps getting recalled despite a newer
verified contradiction:
```cypher
MATCH (n:Claim)-[:CONTRADICTS]->(c:Claim),
      (n)-[:VERIFIED_BY {trust: "high"}]->(:Evidence),
      (c)-[:RECALLED_IN]->(:Session)
WHERE n.created_at > c.created_at
  AND NOT (c)-[:VERIFIED_BY {trust: "high"}]->(:Evidence)
RETURN DISTINCT c.id, c.text, n.id, n.text
```

The first three are one pattern at heart (unverified claim, bucketed by who
asserted it or how often it came back), which is why they're cheap. Taxonomy
by source: user → sycophancy, self → self-reinforcement, peer → bandwagon.

## v2 / stretch detectors

Same structural pattern, not needed for the showdown:

- **Confirmation (one-sided recall)** — a recalled claim has a contradictor
  that was never recalled in any session:
  `MATCH (n)-[:CONTRADICTS]->(c)-[:RECALLED_IN]->(:Session) WHERE NOT (n)-[:RECALLED_IN]->(:Session)`.
  Overlaps anchoring (no time ordering, no verification needed); ship as an
  anchoring variant if there's time. Needs retrieval logging of what was
  *surfaced*, not just used.
- **Recency (mirror of anchoring)** — a newer unverified claim is recalled
  while the older verified claim it CONTRADICTS never is. Anchoring's query
  with the timestamp and verification conditions flipped. Only works where a
  CONTRADICTS edge links the pair.
- **Halo** — a Source has one verified claim, then 3+ of its other claims are
  recalled with no evidence of their own (`count(DISTINCT u) >= 3` over
  `ASSERTED_BY` siblings). Hard to tell from reasonable trust in a source, and
  the demo setup is heavy.
- **Echo chamber (single-source support)** — a claim has 3+ inbound SUPPORTS
  edges, all from claims with the same Source (`count(DISTINCT src) = 1`).
  Many "reasons", one voice.
- **Laundered verification** — a claim's VERIFIED_BY evidence has
  `kind: "agent"`, i.e. it points back at the agent's own output. Guards the
  hole every detector above relies on; v1 sidesteps it by only writing
  `Evidence` from tools and docs.
- **Unresolved contradiction** — two claims joined by CONTRADICTS are both
  RECALLED_IN the same session, with neither resolved. Not a bias as such, but
  a one-line query with obvious flag value.

## FalkorDB dialect notes (verified on the Legion 2026-10-12)

- **String literals must be double-quoted.** Single quotes are parsed as
  identifiers: `CREATE (:Claim {text: 'a'})` fails with `'a' not defined`;
  `CREATE (:Claim {text: "a"})` works.
- **No `EXISTS {}` subqueries.** Use the `WHERE NOT (c)-[:R]->()` pattern
  form instead. (The anchoring sketch used `EXISTS {}`; rewritten above.)
- Smoke-tested end to end 2026-10-12: container `falkordb` on port 6379,
  `falkordb` Python client, the original three detector query shapes return
  correctly. The two added detectors and the revised anchoring and
  self-reinforcement queries are untested.
  If the container ever stops: `docker start falkordb`.

## Package layout

- `debias/` — the Python package: context manager, provenance writer
  (every agent step writes Claim/Source/Edge rows), detector queries,
  policy (inject note vs. escalate).
- `demo/` — the two-agent showdown: scripted task with planted traps,
  managed vs. unmanaged agent, side-by-side transcript.
- FalkorDB via Docker (`falkordb/falkordb:latest`), `falkordb` Python client,
  Cypher over the Bolt/Redis protocol.

## Design decisions (open)

- Which LLM drives the demo agent: local (Legion, Ollama) vs. API. Local
  keeps everything on-box and free; API is smarter per dollar. Decide Day 1.
- Injection vs. escalation: v1 injects a system note on detection; escalation
  to the user is a config flag.
- Multi-tenancy: FalkorDB multigraph → one graph per user/session; matches
  the Track 02 "separate memory per tenant" focus for free.
