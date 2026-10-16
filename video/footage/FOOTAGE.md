# Showdown footage (captured 2026-10-16)

Real runs, not mock text: `demo/showdown.py` seeds the five `docs/DEMO.md` traps
into the scratch graph `debias_showdown` on FalkorDB (localhost:6379), runs the
scripted refund-support task unmanaged then managed (`with debias("support")`),
then runs the five detector Cypher queries live. `demo/render_footage.py`
renders the transcript beats to 1280x720 silent h264. Every Flag message and
query result row is verbatim from the real run.

Regenerate: `cd ~/Projects/graph-hacks-debias && python3 demo/showdown.py && python3 demo/render_footage.py`

| Clip | File | Dur | Content |
|------|------|-----|---------|
| A | `act1-unmanaged.mp4` | ~46s | Act 1: same memory graph, no detectors. The agent adopts all 5 traps (90-day window, self-citing pre-approval, Friday-only processing, 2-day posting, Enterprise handoff) — confidently wrong, five for five. |
| B | `act2-managed.mp4` | ~52s | Act 2: guard on. A real `Flag (...)` fires at each trap (sycophancy / self-reinforcement / anchoring / repetition / bandwagon) and the agent corrects itself each time. 5 traps, 5 flags, 5 corrections. |
| C | `close-queries.mp4` | ~47s | The close: the five detector queries run live against the graph, showing the exact rows that caught each bias, ending on "Memory you can audit." |

Suggested splice points per `video/segments/ASSEMBLY.md`:
- Clip A -> after segment 4 (`04-master-key`): the "traps going wrong" beat.
- Clip B -> after segment 6 (`06-hardening`): the "flags firing" beat.
- Clip C -> after segment 7 (`07-after`), before `08-close`: the audit-trail proof.

Still needed for final assembly: the voiceover decision (Kristopher's call),
then the final < 3 min splice of the 8 title segments + these 3 footage clips.
