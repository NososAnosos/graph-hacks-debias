# Concept — Debias

## Problem

Give an agent long-term memory and you also give it long-term bad habits. In
practice, agent memory systems accumulate exactly the failure modes LLMs
already have, then compound them across sessions:

- The agent cites its own earlier claims as evidence (self-reinforcement).
- A user's offhand assertion gets stored and later stated as verified fact
  (sycophancy / authority bias).
- The first thing the agent learned about a topic keeps winning over newer,
  better-sourced information (anchoring).
- A claim recalled in session after session starts to feel true, though no one
  ever checked it (repetition).
- One agent's unverified claim gets adopted by another as settled fact
  (bandwagon).

Nobody notices because memory is a pile of text. There is no structure to
audit.

## Insight

Put provenance on every memory and the biases become graph queries. Each claim
node records who asserted it, when, and what verifies it. Then:

- Self-reinforcement is a **cycle**: Claim → SUPPORTS → Claim, where every
  node in the cycle was asserted by the agent itself.
- Sycophancy is a **missing edge**: a Claim ASSERTED_BY the user with no
  VERIFIED_BY edge, stated by the agent as fact.
- Anchoring is a **stale preference**: a Claim the agent keeps recalling
  despite newer CONTRADICTS edges from better-sourced nodes.
- Repetition is a **count**: a Claim RECALLED_IN three or more sessions with no
  VERIFIED_BY edge. Recall frequency is not evidence.
- Bandwagon is sycophancy with a peer: a Claim ASSERTED_BY another agent, with
  no VERIFIED_BY edge, about to be used as fact.

Five detectors, every one a structural query: no model judges bias. Further
candidates (confirmation, recency, halo, ...) are sketched in `ARCHITECTURE.md`
as v2.

## The product

`with debias(agent):` — a Python context manager wrapping the agent loop.
Before each consequential step, it runs the detector queries against the
claims the agent is about to rely on. On a hit it injects a system note
("you are about to cite an unverified self-claim") or escalates to the user.
The agent doesn't get a lecture about bias; it gets a graph that won't let
the bias through quietly.

## Why it can win Track 02

Most entries will demo "my agent remembers things." This demos "my agent
remembers things *and can show you why it believes each one*." Provenance is
the differentiator, and the bias detectors are the demo climax. It also
borrows credibility from an active research conversation (sycophancy and
self-reinforcement in LLM agents) without needing novel science — just
operationalization.
