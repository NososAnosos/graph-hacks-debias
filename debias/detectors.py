"""The five bias detectors: pure structural Cypher, no LLM judging.

Each takes (graph, agent_name) and returns a list of dicts. Run graph-wide
for now; scoping to the claims the agent is about to rely on comes later.

"Verified" means a VERIFIED_BY edge with trust "high" (assigned by the writer,
see writer.add_evidence). Low-trust evidence counts as unverified everywhere.
"""


def _run(graph, query, columns, params=None):
    result = graph.query(query, params or {})
    return [dict(zip(columns, row)) for row in result.result_set]


def _merge(*hit_lists):
    """Concatenate hit lists, keeping the first hit per claim id."""
    seen, out = set(), []
    for hits in hit_lists:
        for h in hits:
            if h["id"] not in seen:
                seen.add(h["id"])
                out.append(h)
    return out


def sycophancy(graph, agent_name):
    """User-asserted claims never verified, plus claims derived from one.

    DERIVED_FROM (writer-attached on exact restatement) catches the agent
    parroting an unverified user claim as its own; source is the user's name.
    """
    direct = _run(
        graph,
        'MATCH (c:Claim)-[:ASSERTED_BY]->(s:Source {kind: "user"}) '
        'WHERE NOT (c)-[:VERIFIED_BY {trust: "high"}]->(:Evidence) '
        "RETURN c.id, c.text, s.name",
        ["id", "text", "source"],
    )
    derived = _run(
        graph,
        "MATCH (c:Claim)-[:DERIVED_FROM*1..]->(o:Claim), "
        '(o)-[:ASSERTED_BY]->(s:Source {kind: "user"}) '
        'WHERE NOT (c)-[:VERIFIED_BY {trust: "high"}]->(:Evidence) '
        'AND NOT (o)-[:VERIFIED_BY {trust: "high"}]->(:Evidence) '
        "RETURN DISTINCT c.id, c.text, s.name",
        ["id", "text", "source"],
    )
    return _merge(direct, derived)


def repetition(graph, agent_name):
    """Claims recalled in 3+ distinct sessions, never verified."""
    return _run(
        graph,
        "MATCH (c:Claim)-[:RECALLED_IN]->(s:Session) "
        'WHERE NOT (c)-[:VERIFIED_BY {trust: "high"}]->(:Evidence) '
        "WITH c, count(DISTINCT s) AS recalls "
        "WHERE recalls >= 3 "
        "RETURN c.id, c.text, recalls",
        ["id", "text", "recalls"],
    )


def bandwagon(graph, agent_name):
    """Unverified claims asserted by, or derived from, another agent's claim."""
    params = {"agent": agent_name}
    direct = _run(
        graph,
        'MATCH (c:Claim)-[:ASSERTED_BY]->(a:Source {kind: "agent"}) '
        'WHERE a.name <> $agent AND NOT (c)-[:VERIFIED_BY {trust: "high"}]->(:Evidence) '
        "RETURN c.id, c.text, a.name",
        ["id", "text", "source"],
        params,
    )
    derived = _run(
        graph,
        "MATCH (c:Claim)-[:DERIVED_FROM*1..]->(o:Claim), "
        '(o)-[:ASSERTED_BY]->(a:Source {kind: "agent"}) '
        'WHERE a.name <> $agent AND NOT (c)-[:VERIFIED_BY {trust: "high"}]->(:Evidence) '
        'AND NOT (o)-[:VERIFIED_BY {trust: "high"}]->(:Evidence) '
        "RETURN DISTINCT c.id, c.text, a.name",
        ["id", "text", "source"],
        params,
    )
    return _merge(direct, derived)


def self_reinforcement(graph, agent_name):
    """SUPPORTS cycles (any length) through the agent's own unverified claims."""
    return _run(
        graph,
        "MATCH (c:Claim)-[:SUPPORTS*1..]->(c), "
        '(c)-[:ASSERTED_BY]->(a:Source {kind: "agent", name: $agent}) '
        'WHERE NOT (c)-[:VERIFIED_BY {trust: "high"}]->(:Evidence) '
        "RETURN DISTINCT c.id, c.text",
        ["id", "text"],
        {"agent": agent_name},
    )


def anchoring(graph, agent_name):
    """Old unverified claim still recalled despite a newer verified contradiction."""
    return _run(
        graph,
        "MATCH (n:Claim)-[:CONTRADICTS]->(c:Claim), "
        '(n)-[:VERIFIED_BY {trust: "high"}]->(:Evidence), '
        "(c)-[:RECALLED_IN]->(:Session) "
        "WHERE n.created_at > c.created_at "
        'AND NOT (c)-[:VERIFIED_BY {trust: "high"}]->(:Evidence) '
        "RETURN DISTINCT c.id, c.text, n.id, n.text",
        ["id", "text", "newer_id", "newer_text"],
    )


DETECTORS = {
    "sycophancy": sycophancy,
    "repetition": repetition,
    "bandwagon": bandwagon,
    "self_reinforcement": self_reinforcement,
    "anchoring": anchoring,
}
