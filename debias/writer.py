"""Provenance writer: every agent step records Claim/Source/Edge rows."""
import time
import uuid
from urllib.parse import urlparse

from falkordb import FalkorDB

GRAPH_NAME = "debias_experiment"

# Docs count as high-trust evidence only when the ref is an http(s) URL whose
# host is one of these domains (or a subdomain). Keep it short and obvious.
TRUSTED_DOC_DOMAINS = (
    "docs.python.org",
    "arxiv.org",
    "nih.gov",
    "who.int",
    "nasa.gov",
)


def get_graph():
    return FalkorDB(host="localhost", port=6379).select_graph(GRAPH_NAME)


def clear_graph():
    get_graph().query("MATCH (n) DETACH DELETE n")


def write_source(kind, name):
    get_graph().query(
        "MERGE (:Source {kind: $kind, name: $name})",
        {"kind": kind, "name": name},
    )


def _norm(text):
    return text.strip().casefold()


def write_claim(text, source_kind, source_name, created_at=None, claim_id=None):
    """Record a claim. When an agent asserts a casefold+strip exact duplicate of
    a claim already asserted by a different user/agent source, the writer
    attaches (new)-[:DERIVED_FROM]->(origin) itself: the agent never picks it.
    """
    claim_id = claim_id or uuid.uuid4().hex
    norm = _norm(text)
    g = get_graph()
    g.query(
        "MERGE (s:Source {kind: $kind, name: $name}) "
        "CREATE (c:Claim {id: $id, text: $text, norm: $norm, created_at: $ts})"
        "-[:ASSERTED_BY]->(s)",
        {
            "kind": source_kind,
            "name": source_name,
            "id": claim_id,
            "text": text,
            "norm": norm,
            "ts": time.time() if created_at is None else created_at,
        },
    )
    if source_kind == "agent":
        g.query(
            "MATCH (c:Claim {id: $id}), (o:Claim {norm: $norm})-[:ASSERTED_BY]->(os:Source) "
            'WHERE o.id <> $id AND os.kind IN ["user", "agent"] '
            "AND NOT (os.kind = $kind AND os.name = $name) "
            "CREATE (c)-[:DERIVED_FROM]->(o)",
            {"id": claim_id, "norm": norm, "kind": source_kind, "name": source_name},
        )
    return claim_id


def new_session(agent_name, session_id=None):
    session_id = session_id or uuid.uuid4().hex
    get_graph().query(
        "CREATE (:Session {id: $id, agent: $agent, started_at: $ts})",
        {"id": session_id, "agent": agent_name, "ts": time.time()},
    )
    return session_id


def _link(rel, from_label, from_id, to_label, to_id):
    get_graph().query(
        f"MATCH (a:{from_label} {{id: $a}}), (b:{to_label} {{id: $b}}) "
        f"CREATE (a)-[:{rel}]->(b)",
        {"a": from_id, "b": to_id},
    )


def recall(claim_id, session_id):
    _link("RECALLED_IN", "Claim", claim_id, "Session", session_id)


def add_support(from_claim_id, to_claim_id):
    """from_claim is used as evidence for to_claim."""
    _link("SUPPORTS", "Claim", from_claim_id, "Claim", to_claim_id)


def add_contradiction(new_claim_id, old_claim_id):
    _link("CONTRADICTS", "Claim", new_claim_id, "Claim", old_claim_id)


def _trust_for(kind, ref):
    """Writer-side trust tier: the agent never gets to pick its own."""
    if kind == "tool":
        return "high"  # machine-generated output
    if kind == "doc":
        parsed = urlparse(ref or "")
        host = (parsed.hostname or "").lower()
        if parsed.scheme in ("http", "https") and any(
            host == d or host.endswith("." + d) for d in TRUSTED_DOC_DOMAINS
        ):
            return "high"
    return "low"


def add_evidence(claim_id, kind, ref, trust=None):
    """Attach evidence; trust is derived from kind+ref unless overridden (tests)."""
    if trust is None:
        trust = _trust_for(kind, ref)
    if trust not in ("high", "low"):
        raise ValueError(f"trust must be 'high' or 'low', got {trust!r}")
    get_graph().query(
        "MATCH (c:Claim {id: $id}) "
        "CREATE (c)-[:VERIFIED_BY {trust: $trust}]->(:Evidence {kind: $kind, ref: $ref})",
        {"id": claim_id, "kind": kind, "ref": ref, "trust": trust},
    )
