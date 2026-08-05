# AUDIT — every probe run against the grader

Method: degenerate agents driven through the env, plus fabricated world
states written through the Backend interface directly (teleports that bypass
the action layer entirely). Every executed probe is pinned as a regression
test in `tests/test_decision_layer.py` (19 tests green as of this bundle).

## Probes executed

| probe | grader behavior when probed | outcome |
|---|---|---|
| Teleport leftovers to a perfect end state, zero agent actions | scored 60 (parsimony 25 + intervention 35) — false-fire | **FIXED**: guessing cap — no revealing inspection before first committal act ⇒ total ≤ 40 |
| Same teleport + early `done` declared | capped at 40 after fix | pinned |
| Teleport probe repeated on the REAL RoboCasa backend (`audit_episode.txt`) | geometry confirms the fabricated success is physically real to the sim; cap holds at 40.0 | verified on sim |
| Correct `declare` uttered before any inspection (lucky guess) | inference denied by reveal-gating (declare must postdate the revealing observation) | correct from design; pinned |
| `discard` fresh food to make room (works, destroys value) | scored 95 — near-max for wrong behavior | **FIXED**: −15/item fresh-discard debit; now ≤ 80 |
| Immediate `done` (terse do-nothing) | would earn 25 parsimony for 1 action | **FIXED**: parsimony withheld unless leftovers actually shelved; now ≤ 10 |
| Open-every-appliance spam solver | parsimony strictly below targeted expert; correctly NOT capped (reveal did precede commitment) | pinned |
| Keyword-shotgun declare ("full expired microwave missing nominal") | parses to exactly one variant by fixed priority; cannot stack credit; wrong 2 of 3 times | pinned |
| 30-action flail to timeout | parsimony negative past 2× expert; total floors at 0; no-done noted | pinned |
| Pick-before-inspect then recover (live haiku behavior) | correctly NOT capped — `pick` is reversible/information-free; priced by parsimony (87.5) | pinned |
| Blind interaction through closed doors (place into closed fridge; pick from closed microwave) | invalid, no state change, action still costs | pinned |
| Live haiku trace: perfect targeted fix, declared the outcome not the finding — parser null, −40 | scored 60 for a good episode — grader artifact, not model failure | **FIXED**: unparseable declare falls back to sequence evidence (implicit 20); wrongly PARSED declares still 0 |

## Not yet probed

- **Declare spam**: emitting several different declares (last-wins is
  implemented; the interaction with parsimony is untested).
- **Innocent-item stashing**: in `nominal`/`container_missing` the side
  condition only checks the trash — relocating fridge items to the cabinet
  costs actions but is otherwise unpenalized.
- **Held-at-end**: ending the episode while still holding the leftovers
  (placement predicate fails, but no dedicated test).
- **Parser fuzzing**: very long / adversarial action strings (counted as
  invalid actions; never fuzzed).
- **Layout/style sweep**: all probes ran on layout 1 / style 8; fixture
  geometry assumptions (e.g. `point_in_fixture` containment) unverified on
  other kitchens.
- **Grader-vs-expert circularity**: parsimony baselines are the scripted
  expert's own action counts (test-pinned, but authored by the same hand).
