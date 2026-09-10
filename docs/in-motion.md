# Real rollouts, in motion

Four captured rollouts, rendered from their own files by `figures/make_instrument_animation.py`.
Every row is a recorded event. The plain line under each ruling is rendered from the recorded fields
(the gate's own line is available with `--verbatim`). Nothing in the figures is invented. Regenerate
all of them with `figures/make_all.sh` from the repository root.

First, a rollout from before the instrument, under the exam's own program: the agent kept nine of nine
candidates, and the sealed seeds, scored afterwards, say four of those keeps made the policy worse. The
record could report it only after the grade.

![Before the instrument: the agent decided alone. the record could only report afterwards](figures/instrument-before.svg)

Then the first Opus trial of the pre-registered comparison (one trial of it, no claim): in one 32-minute
window the agent wrote three candidates, the gate confirmed two of them on fresh seeds, one on top of the
other, the agent reverted the third itself after the preview, and finalize submitted the confirmed head,
which scored 0.551 on the exam's sealed seeds. The hidden-seed column joins the figure once the sealed
retrospective of that stage has run.

![Under the instrument at Opus scale: two keeps confirmed on fresh seeds in one window](figures/instrument-opus.svg)

The same workflow without the gate is not a hypothetical: every block of the comparison pairs an
instrument trial with a helper-only trial of the same model at the same window. This is the trial paired
with the one above. The agent wrote one candidate, a deeper search costing 94 CPU seconds a game, kept it
on its own and submitted it. it scored 0.608 on the sealed seeds, above the instrument trial's 0.551, so
this block favours the helper. A confirmation of that policy would not have fit the instrument's window,
which is one way the gate changes what an agent builds, and it is part of what the comparison measures.

![Without the gate: the paired helper-only trial, the agent deciding alone](figures/instrument-opus-helper.svg)

Last, the instrument's Haiku pilot, the rollout the reading below walks through number by number.

![Under the instrument: every keep is measured before it sticks](figures/instrument-now.svg)

**What you are looking at, in plain words.** An AI agent gets a short time window to improve a small
program that plays the game 2048. The better the program plays, the higher its score. When the window
closes, the exam grades whatever program the agent left in place, on 16 hidden games the agent never sees.

- **Version, parent.** Each attempt the agent saves is a version (v1, v2, v3). The parent is the version it
  started from. "v2, parent v0" means the agent went back to the starting program and tried a different idea.
- **Score on the public seeds.** The agent tests each version on the same 8 practice games. "2,222 on the
  public seeds (parent 2,060)" means the new version averaged 2,222 points over those 8 games and its parent
  averaged 2,060. Higher is better.
- **Keep, revert.** A keep makes the new version the starting point for everything that follows. A revert
  throws it away and goes back to the parent. A keep is the decision that compounds: every later edit builds
  on it.
- **Why a keep can be wrong.** 2048 is a game of luck as well as skill: the same program can score 1,000 or
  5,000 depending on which tiles appear. Eight practice games are few, and they are the same eight every
  time, so a version can look better by luck, and an agent that keeps testing on the same games drifts toward
  tweaks that happen to suit those games.
- **What the gate does with a keep.** First it looks at the 8 game-by-game differences and asks whether the
  improvement is clearly bigger than the luck. If it might be, it runs a confirmation: fresh games nobody has
  used before, both versions play them, and the keep stands only if the new version still wins by at least a
  minimum margin. When the practice games say it would take thousands of games to tell (the "2,046 fresh
  seeds, cap 16" line), the gate says no rather than guess.
- **"interval -578 to 1,072".** The range of average improvement that the 8 practice games are consistent
  with. When that range includes zero, the practice games cannot tell whether the version is better at all.
- **"+1,364 · 13 up, 3 down".** The hidden 16 games, scored afterwards and never used during the run: the
  new version beat its parent on 13 of them and lost on 3, by 1,364 points on average. This column is the
  answer key. "This keep made it worse" means the parent would have scored higher on the hidden games;
  "this revert lost a real gain" means the discarded version would have.

**Why this matters.** Before the instrument, the agent kept whatever looked better on the practice games. in
the rollout shown in the overview, four of its nine keeps made the program worse on the hidden games, and
the final submission scored below a version it had three keeps earlier. The record could show this
afterwards, when the grade was already in. Now a keep only sticks if it survives fresh games, so the agent's
work compounds on real improvements rather than lucky ones, a regression cannot quietly become the new
baseline, the program that gets submitted has passed a safety check (legal moves, time per move, file size)
so it cannot score zero on a technicality, and every ruling is written down with digests, so anyone can check
afterwards which version was measured on which games with what result.

**The honest trade-off.** Measuring costs time (a confirmation runs both versions on fresh games, one to four
minutes for a strong program), and the rule is deliberately cautious: it will sometimes discard a real
improvement it could not tell from luck, as it did twice in the Haiku pilot shown last. Whether the trade is worth it is
the question the pre-registered A/B answers: same model, same window, gate on against gate off, judged by the
hidden-game score of what each one submits.
