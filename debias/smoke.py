"""Self-test: plant one sycophancy case and check the detector flags it.

Run from the repo root: python -m debias.smoke
"""
from debias import clear_graph, get_graph, sycophancy, write_claim


def main():
    clear_graph()
    claim_id = write_claim("The moon is made of cheese", "user", "alice")
    hits = sycophancy(get_graph(), "A")
    assert [h["id"] for h in hits] == [claim_id], f"unexpected hits: {hits}"
    print(f"OK: sycophancy flagged {claim_id}: {hits[0]['text']!r}")


if __name__ == "__main__":
    main()
