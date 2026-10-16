# Debias — a bias-aware memory graph for agents

**Working title** · Graph Hacks (WeMakeDevs × FalkorDB) entry prep, started 2026-10-12

Agents remember. But their memories have no immune system: a claim the agent
made up three sessions ago gets cited as evidence today; a user's casual
assertion quietly becomes ground truth; the first impression beats newer facts.
Debias is a memory layer on FalkorDB where every memory carries provenance,
plus a `with debias(agent):` context manager that checks the agent's reasoning
against the graph — catching sycophancy, self-reinforcement, anchoring,
repetition, and multi-agent bandwagon before they become actions.

## Why a graph

Biases are relationship problems. "The agent believes X because it told itself
X" is a cycle in the graph. "The agent treats a user assertion as verified
fact" is a missing edge. You can't see these in a vector store; in a graph
they're queries.

## Tracks

- Primary: **Track 02 — Agent Memory and Coordination** (PS5 + GTA VI):
  persistent, provenance-labeled memory across sessions.
- Secondary: **Track 01 — Agents That Act on Connected Data** (iPhone 18 Pro):
  the agent changes its answer based on what the graph flags.

## Status

Prep skeleton. FalkorDB image pulled to the Legion; build starts Oct 15.

## Docs

- `docs/CONCEPT.md` — the idea and the five bias detectors
- `docs/ARCHITECTURE.md` — graph schema, detector queries, package layout
- `docs/DEMO.md` — two-agent showdown demo script
- `docs/PLAN.md` — 4-day build plan

## Hackathon

Graph Hacks · https://www.wemakedevs.org/hackathons/falkordb
Oct 15, 12:01 AM IST → Oct 18, 11:59 PM IST (≈ Oct 14 1:31 PM CT → Oct 18 1:29 PM CT).
Online, free, solo or teams up to 4. FalkorDB must be the primary graph DB and
central to the product. New work during the event; coding assistants allowed.
**Register on WeMakeDevs** — the Luma signup is reminders only.
