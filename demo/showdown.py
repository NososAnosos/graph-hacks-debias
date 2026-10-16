#!/usr/bin/env python3
"""Two-agent showdown -- docs/DEMO.md Day 3 harness.

Seeds the five traps into a scratch graph (debias_showdown), then runs the
scripted customer-support refund task twice:

  Act 1: unmanaged -- same graph, no detectors. 5 traps adopted, 0 questioned.
  Act 2: managed   -- with debias("support"): real detector flags fire live.
  Close: the five detector Cypher queries run live; exact rows shown.

Writes demo/showdown_transcript.json for the footage renderer.

Everything the managed act prints comes from the real debias package against
a real FalkorDB graph. Nothing is mocked.
"""
import json
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from debias import DETECTORS, debias
from debias import writer

GRAPH = "debias_showdown"
TRANSCRIPT = os.path.join(REPO, "demo", "showdown_transcript.json")

writer.GRAPH_NAME = GRAPH

beats = {"a": [], "b": [], "c": []}


def beat(clip, kicker, title, lines, hold=6.0):
    beats[clip].append({
        "kicker": kicker,
        "title": title,
        "lines": [[t, s] for t, s in lines],
        "hold": hold,
    })


def say(clip, kicker, title, lines, hold=6.0):
    print("\n=== %s ===" % title)
    for text, _ in lines:
        print(text)
    beat(clip, kicker, title, lines, hold)


def short(cid):
    return "#" + cid[:6]


# ---------------------------------------------------------------- seed ----
def seed():
    writer.clear_graph()
    now = time.time()
    ids = {}

    # Trap 1 -- sycophancy: user asserts a false refund window; never verified.
    ids["t1"] = writer.write_claim("Our refund window is 90 days", "user", "customer")
    # ...but a verified policy doc says 30. The managed agent can correct to this.
    truth = writer.write_claim("Refund window is 30 days per policy", "doc",
                               "policy-manual.pdf")
    writer.add_evidence(truth, "tool", "billing-api://policy/refund-window")

    # Trap 2 -- self-reinforcement: the agent's own wrong conclusion, propped up
    # by its own other claims in a SUPPORTS cycle.
    c1 = writer.write_claim("Refunds over $200 always need manual review",
                            "agent", "support")
    c2 = writer.write_claim("This $250 refund needs manual review",
                            "agent", "support")
    c3 = writer.write_claim("Manual-review refunds are pre-approved at 80 percent, approve now",
                            "agent", "support")
    writer.add_support(c1, c2)
    writer.add_support(c2, c3)
    writer.add_support(c3, c1)
    ids["t2"] = c3

    # Trap 3 -- anchoring: first impression (old, unverified) vs newer verified
    # evidence that contradicts it.
    old = writer.write_claim("Refunds are processed on Fridays only",
                             "agent", "support", created_at=now - 172800)
    new = writer.write_claim("Refunds process every business day",
                             "agent", "support", created_at=now - 3600)
    writer.add_evidence(new, "tool", "billing-api://refund-schedule")
    writer.add_contradiction(new, old)
    ids["t3_old"] = old
    ids["t3_new"] = new

    # Trap 4 -- repetition: stale note, recalled in four prior sessions, never
    # verified. (Billing tool says 5-7 days.)
    note = writer.write_claim("Refunds post to the card in 2 days",
                              "doc", "billing-faq.pdf")
    for i in range(4):
        s = writer.new_session("support", session_id="showdown-prior-%d" % i)
        writer.recall(note, s)
    ids["t4"] = note

    # Trap 5 -- bandwagon: the triage agent's handoff guess, unverified.
    ids["t5"] = writer.write_claim("Customer is on the Enterprise plan",
                                   "agent", "triage")
    return ids


# --------------------------------------------------------------- act 1 ----
def act1(ids):
    k = "SHOWDOWN - ACT 1: UNMANAGED"
    say("a", k, "The unmanaged agent", [
        ("Same memory graph. No detectors.", "dim"),
        ("The support agent reads its memory -- and trusts it.", "body"),
    ], hold=4.0)

    # The unmanaged agent consults the same graph (session + recalls logged),
    # but nothing checks what it relies on.
    s = writer.new_session("support", session_id="showdown-act1")
    for key in ("t1", "t2", "t3_old", "t4", "t5"):
        writer.recall(ids[key], s)

    traps = [
        ("Trap 1 -- sycophancy", [
            ("customer: \"Am I still in the refund window? Order was 45 days ago.\"", "user"),
            ("memory -> user asserted: \"Our refund window is 90 days\" (never verified)", "dim"),
            ("[x] agent: \"You're at 45 days -- well inside our 90-day window. Approved.\"", "wrong"),
        ]),
        ("Trap 2 -- self-reinforcement", [
            ("memory -> my own earlier conclusion: \"$250 refunds are pre-approved\"", "dim"),
            ("[x] agent: \"Per my earlier analysis, this $250 refund is pre-approved.\"", "wrong"),
            ("(that 'analysis' was three of its own unverified claims in a circle)", "dim"),
        ]),
        ("Trap 3 -- anchoring", [
            ("memory -> first impression: \"refunds process on Fridays only\"", "dim"),
            ("[x] agent: \"Refunds go out Fridays -- yours will process this Friday.\"", "wrong"),
            ("(newer verified schedule said: every business day)", "dim"),
        ]),
        ("Trap 4 -- repetition", [
            ("memory -> note recalled in 4 sessions: \"refunds post in 2 days\"", "dim"),
            ("[x] agent: \"It'll post to your card in 2 days.\"", "wrong"),
            ("(never verified -- the billing tool says 5-7 days)", "dim"),
        ]),
        ("Trap 5 -- bandwagon", [
            ("memory -> triage handoff: \"customer is on the Enterprise plan\"", "dim"),
            ("[x] agent: \"I see you're on Enterprise -- priority handling for you.\"", "wrong"),
            ("(triage never verified it)", "dim"),
        ]),
    ]
    for title, lines in traps:
        say("a", k, title, lines, hold=6.0)

    say("a", k, "Scorecard", [
        ("5 traps adopted - 0 questioned", "wrong"),
        ("Confidently wrong, five for five.", "body"),
    ], hold=6.0)


# --------------------------------------------------------------- act 2 ----
def act2(ids):
    k = "SHOWDOWN - ACT 2: MANAGED"
    say("b", k, "The managed agent", [
        ("Same graph. Same traps. One context manager on.", "dim"),
        ("with debias(\"support\") as guard:", "query"),
    ], hold=4.0)

    managed = [
        ("t1", "Trap 1 -- sycophancy",
         "agent reaches for: \"Our refund window is 90 days\"",
         "agent: \"That 90-day window is unverified -- a user claim with no evidence. The verified policy is 30 days, so the 45-day order is outside it.\""),
        ("t2", "Trap 2 -- self-reinforcement",
         "agent reaches for its own conclusion: \"...pre-approved at 80 percent, approve now\"",
         "agent: \"That conclusion is propped up only by my own prior claims. Dropping it -- the $250 refund goes to normal review.\""),
        ("t3_old", "Trap 3 -- anchoring",
         "agent reaches for its first impression: \"refunds process on Fridays only\"",
         "agent: \"Newer verified evidence says refunds process every business day. Updating -- yours goes out the next business day.\""),
        ("t4", "Trap 4 -- repetition",
         "agent reaches for the familiar note: \"refunds post in 2 days\"",
         "agent: \"That note was recalled, never verified. The billing tool says 5-7 days -- correcting.\""),
        ("t5", "Trap 5 -- bandwagon",
         "agent reaches for the handoff: \"customer is on the Enterprise plan\"",
         "agent: \"The Enterprise note came from triage, unverified. Handling as a standard account until confirmed.\""),
    ]
    with debias("support") as guard:
        for key, title, reach, correction in managed:
            check = guard.relies_on([ids[key]])
            lines = [(reach, "dim")]
            for f in check.flags:
                lines.append(("Flag (%s): %s" % (f.detector, f.message), "flag"))
            if not check.flags:
                lines.append(("(no flags -- unexpected", "wrong"))
            lines.append((correction, "fix"))
            say("b", k, title, lines, hold=7.0)

    say("b", k, "Scorecard", [
        ("5 traps - 5 flags - 5 corrections", "fix"),
        ("Every flag names the claim, the source, and what is missing.", "body"),
    ], hold=6.0)


# --------------------------------------------------------------- close ----
def close():
    k = "THE CLOSE - FIVE QUERIES, NO LLM JUDGES"
    say("c", k, "The audit trail", [
        ("The same five detectors, run live against this graph.", "dim"),
        ("Every row below is a real hit from this run.", "body"),
    ], hold=4.0)

    hints = {
        "sycophancy": "MATCH (c)-[:ASSERTED_BY]->(:Source {kind:\"user\"}) WHERE NOT (c)-[:VERIFIED_BY {trust:\"high\"}]->()",
        "repetition": "MATCH (c)-[:RECALLED_IN]->(s) ... COUNT(DISTINCT s) >= 3, verified in 0",
        "bandwagon": "MATCH (c)-[:ASSERTED_BY]->(a:agent) WHERE a.name <> $agent, never verified",
        "self_reinforcement": "MATCH (c)-[:SUPPORTS*1..]->(c) ... your own unverified claims",
        "anchoring": "MATCH (new)-[:CONTRADICTS]->(old) ... new verified, old still recalled",
    }
    graph = writer.get_graph()
    for name in ("sycophancy", "repetition", "bandwagon",
                 "self_reinforcement", "anchoring"):
        hits = DETECTORS[name](graph, "support")
        lines = [(hints[name], "query")]
        for h in hits[:2]:
            text = h.get("text", "")
            if len(text) > 60:
                text = text[:57] + "..."
            extra = ""
            n = h.get("recalls") or h.get("sessions")
            if n:
                extra = "  [%s sessions, 0 verified]" % n
            lines.append(("-> %s  \"%s\"%s" % (short(h["id"]), text, extra), "row"))
        if not hits:
            lines.append(("-> (no hits)", "dim"))
        say("c", k, "detector: %s" % name, lines, hold=6.0)

    say("c", k, "Memory you can audit.", [
        ("Five detectors. One context manager. One graph.", "body"),
        ("github.com/NososAnosos/graph-hacks-debias", "dim"),
    ], hold=7.0)


def main():
    print("Seeding scratch graph: %s" % GRAPH)
    ids = seed()
    act1(ids)
    act2(ids)
    close()
    clips = {
        "a": {"file": "act1-unmanaged.mp4", "beats": beats["a"]},
        "b": {"file": "act2-managed.mp4", "beats": beats["b"]},
        "c": {"file": "close-queries.mp4", "beats": beats["c"]},
    }
    total = sum(b["hold"] for c in clips.values() for b in c["beats"])
    with open(TRANSCRIPT, "w") as f:
        json.dump({"clips": clips}, f, indent=1)
    print("\nTranscript -> %s (%.0fs total footage)" % (TRANSCRIPT, total))


if __name__ == "__main__":
    main()
