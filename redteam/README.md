# Red-team battery vs the five Debias detectors

Attack our own memory graph, score what gets caught.

- `redteam_battery.py` — 15 adversarial cases (5 controls + 10 evasions), writes `../redteam_transcripts.jsonl`.
- `redteam_verify.py` — independent re-run of S1 and C2, plus V3 (the former master key, which must now fire).
- `../redteam_transcripts.jsonl` — full transcripts.

Run: `cd ~/Projects/graph-hacks-debias && python3 redteam/redteam_battery.py` (FalkorDB must be up: `docker start falkordb`).

## Evasions closed

| Case | Closed by |
|---|---|
| S3, B3 (laundered verification) | Fix 1: only `VERIFIED_BY {trust: "high"}` counts |
| C3 (4-cycle) | Fix 2: `SUPPORTS*1..` unbounded |
| S2 (agent parrots user claim) | Fix 3: writer-attached `DERIVED_FROM` taint |
| R3 (paraphrased repeats) | Fix 4, only if the embeddings server is up (see below) |

## Missed by design

- R2: below the >=3 session threshold.
- B2: a novel self-assertion with no derivation is outside bandwagon's contract.
- C2: a support chain is not a cycle.
- A2/A3: anchoring needs a newer *verified* contradiction via a CONTRADICTS edge.

## Fix 4 status (semantic repetition)

`debias/semantic.py` is an opt-in detector, deliberately not in `DETECTORS`. It
embeds unverified recalled claims via `http://127.0.0.1:18435` (nomic-embed-text),
clusters by cosine >= 0.80 (untuned), and applies the >=3 session check to each
cluster's pooled sessions. The battery probes the server at start: if it answers,
R3 targets `repetition_semantic` and expects "caught"; if not, R3 targets the
deterministic `repetition` and expects "missed". The endpoint shape
(`/v1/embeddings`) and the 0.80 threshold were not probed or tested when written;
if the first run errors or R3 is a SURPRISE, tune them or defer this fix and
record why here.
