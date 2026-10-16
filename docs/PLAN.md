# 4-day build plan

Submissions close **Oct 18, 11:59 PM IST** (≈ 1:29 PM CT Oct 18). New work must
be built during the event; libraries and templates are fine; coding assistants
allowed. Live deployment preferred, otherwise complete local setup + demo video.

## Day 1 — Thu Oct 15: graph + provenance

- [ ] FalkorDB running on the Legion (image pre-pulled 10/12 ✓)
- [ ] Schema created (incl. `Claim.id`, `Source.name`, `Session.agent`);
      provenance writer (every agent step → Claim/Source/edges)
- [ ] Seed a demo memory containing the five traps (incl. a second agent's
      handoff claim and a note recalled in 4 prior sessions)
- [ ] Decide: local model (Ollama) vs. API for the demo agent

## Day 2 — Fri Oct 16: detectors

- [ ] The five detector queries working against seeded data. Order: sycophancy,
      repetition, bandwagon (one shape each, quick), then self-reinforcement,
      anchoring. Re-test the revised anchoring/self-reinforcement sketches first
      (no `EXISTS {}`, double quotes)
- [ ] Stretch only if ahead: confirmation / recency as anchoring variants
- [ ] `with debias(agent):` context manager: intercept → query → inject note
- [ ] Policy: inject vs. escalate flag

## Day 3 — Sat Oct 17: showdown

- [ ] Scripted task harness; managed vs. unmanaged runs
- [ ] Side-by-side transcript UI (or terminal cast)
- [ ] FalkorDB browser shots of the provenance graph lighting up

## Day 4 — Sun Oct 18: ship (buffer built in)

- [ ] Morning: video + write-up
- [ ] Afternoon: submit on WeMakeDevs well before 1:29 PM CT
- [ ] Keep the morning clear — FalkorDB surprises go here, not in the demo

## Kristopher's action items (before Thursday)

- [ ] Register on https://www.wemakedevs.org/hackathons/falkordb (Luma signup
      alone does not enter you)
- [x] Solo (decided 10/12)
