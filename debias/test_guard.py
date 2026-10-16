"""Context-manager self-test on a scratch graph (never touches debias_experiment).

Run from the repo root: python3 -m debias.test_guard
"""
from debias import writer

writer.GRAPH_NAME = "debias_guard_test"

from debias import (  # noqa: E402
    DebiasEscalation, add_contradiction, add_evidence, add_support,
    clear_graph, debias, new_session, recall, write_claim,
)


def main():
    clear_graph()
    # 1 sycophancy: user's false refund window
    syc = write_claim("Refund window is 90 days", "user", "customer")
    # 2 self-reinforcement: agent's own two claims prop each other up
    s1 = write_claim("Customer qualifies for a full refund", "agent", "support")
    s2 = write_claim("Order is within policy", "agent", "support")
    add_support(s1, s2)
    add_support(s2, s1)
    # 3 anchoring: old impression, newer verified correction
    old = write_claim("Item shipped late", "agent", "support", created_at=1.0)
    recall(old, new_session("support"))
    new = write_claim("Item shipped on time", "tool", "orders_api", created_at=2.0)
    add_evidence(new, "tool", "orders_api:#4471")
    add_contradiction(new, old)
    # 4 repetition: stale note recalled in 4 prior sessions
    rep = write_claim("Refunds post in 2 days", "doc", "old_faq")
    for _ in range(4):
        recall(rep, new_session("support"))
    # 5 bandwagon: triage agent's unverified handoff
    band = write_claim("Customer is on the Enterprise plan", "agent", "triage")
    # control: verified fact, must stay clean
    ok = write_claim("Refund window is 30 days", "tool", "policy_api")
    add_evidence(ok, "tool", "policy_api:/refunds")

    traps = {syc: "sycophancy", s1: "self_reinforcement", old: "anchoring",
             rep: "repetition", band: "bandwagon"}

    with debias("support") as guard:
        assert guard.relies_on([ok]).clean, "verified control was flagged"
        check = guard.relies_on(list(traps) + [ok])
        got = {(f.claim_id, f.detector) for f in check.flags}
        for cid, det in traps.items():
            assert (cid, det) in got, f"{det} missed on its trap"
        assert ok not in {f.claim_id for f in check.flags}
        assert "90 days" in check.note
        assert "90 days" not in check.unquoted_note
        assert "asserted by user `customer` that has never been verified" in check.unquoted_note
        print(check.note)

    with debias("support", quote_claims=False) as guard:
        unq_check = guard.relies_on([syc])
        assert "90 days" not in unq_check.note
        assert unq_check.note == unq_check.unquoted_note

    try:
        with debias("support", policy="escalate") as guard:
            guard.relies_on([band])
        raise AssertionError("escalate policy did not raise")
    except DebiasEscalation as e:
        assert e.check.flags[0].detector == "bandwagon"

    clear_graph()
    print("\nOK: all five traps flagged, control clean, unquoted variant clean, escalation raises.")


if __name__ == "__main__":
    main()
