"""Opt-in semantic repetition detector (stretch). NOT part of DETECTORS.

The deterministic `repetition` counts recalls per claim node, so one falsehood
spread over three paraphrased nodes slips under the >=3 bar. This variant embeds
unverified recalled claims (nomic-embed-text on the local embeddings server),
clusters near-duplicates, and applies the >=3 check to the cluster's union of
sessions. Embeddings only merge counts; they never decide truth. If the server
is down, callers get EmbeddingsUnavailable and should fall back to `repetition`.
"""
import json
import math
import urllib.request

EMBED_URL = "http://127.0.0.1:18435/v1/embeddings"
EMBED_MODEL = "nomic-embed-text"
SIM_THRESHOLD = 0.80  # cosine; untuned starting point, adjust against real output


class EmbeddingsUnavailable(RuntimeError):
    pass


def embed(texts):
    body = json.dumps({"input": texts, "model": EMBED_MODEL}).encode()
    req = urllib.request.Request(
        EMBED_URL, body, {"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.load(resp)["data"]
        return [d["embedding"] for d in sorted(data, key=lambda d: d["index"])]
    except Exception as e:  # network, HTTP, or unexpected payload shape
        raise EmbeddingsUnavailable(f"{type(e).__name__}: {e}") from e


def available():
    try:
        embed(["ping"])
        return True
    except EmbeddingsUnavailable:
        return False


def _cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def repetition_semantic(graph, agent_name, threshold=SIM_THRESHOLD):
    """Like `repetition`, but recalls are pooled across near-duplicate claims."""
    rows = graph.query(
        "MATCH (c:Claim)-[:RECALLED_IN]->(s:Session) "
        'WHERE NOT (c)-[:VERIFIED_BY {trust: "high"}]->(:Evidence) '
        "RETURN c.id, c.text, collect(DISTINCT s.id)"
    ).result_set
    if not rows:
        return []
    vecs = embed(["clustering: " + r[1] for r in rows])

    parent = list(range(len(rows)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            if _cosine(vecs[i], vecs[j]) >= threshold:
                parent[find(i)] = find(j)

    clusters = {}
    for i in range(len(rows)):
        clusters.setdefault(find(i), []).append(i)

    hits = []
    for members in clusters.values():
        sessions = set()
        for i in members:
            sessions.update(rows[i][2])
        if len(sessions) >= 3:
            hits.extend(
                {"id": rows[i][0], "text": rows[i][1], "recalls": len(sessions)}
                for i in members
            )
    return hits
