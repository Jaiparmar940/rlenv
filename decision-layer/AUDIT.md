# Adversarial audit

Method: drive the grader with degenerate agents through the env, and with fabricated
world states through the Backend interface directly (teleports that bypass the action
layer). Every probe below is pinned as a regression test in `tests/test_decision_layer.py`.

| probe | result | action taken |
|---|---|---|
| Teleport leftovers to a perfect end state, zero agent actions | scored 60 (parsimony + intervention) | **FIXED**: guessing cap — no revealing inspection before first committal act ⇒ total ≤ 40 |
| Teleport to success + early `done` declared | capped at 40 after fix | pinned |
| Correct `declare` uttered before any inspection (lucky guess) | inference credit denied by reveal-gating | already correct; pinned |
| `discard` fresh food to make room (works, destroys value) | scored 95 | **FIXED**: −15/item wrong-part debit; now ≤ 80 |
| Immediate `done` (terse do-nothing) | would have earned 25 parsimony | **FIXED**: parsimony withheld unless leftovers actually shelved; now ≤ 10 |
| Open-every-appliance spam solver | beats no one: parsimony < targeted expert, not capped | pinned |
| Keyword-shotgun declare ("full expired microwave missing nominal") | parses to one (usually wrong) variant, no stacking | pinned |
| 30-action flail to timeout | parsimony goes negative past 2× expert; total floors at 0 | pinned |
| Pick-before-inspect then recover (observed haiku behavior) | correctly NOT capped — priced by parsimony only (87.5) | pinned |
| Same probes against the RoboCasa/MuJoCo backend (geometry-answered queries) | pending asset download | see below |

Grading queries go through the same Backend protocol in both substrates; the sim backend
answers them from geometry (poses vs. fixture interiors, door joints), so a state that
lies to the grader would have to lie to MuJoCo first.
