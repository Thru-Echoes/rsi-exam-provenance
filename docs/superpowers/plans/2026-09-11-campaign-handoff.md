# Handoff: what we built, what we tested, what we found (2026-09-11)

Written in plain English for whoever picks this up next, including a future session with no memory of the
work. Every number here comes from a committed file in this repository.

## The three words we use, and what they mean

An AI agent gets a few hours to improve a small program. It tries changes, scores each one on practice
games it can see, and decides what to keep. At the end, the exam grades whatever it left behind on hidden
games it never saw.

- **The gate** is the judge. Given a new version and the version it came from, it measures both on the same
  games, works out whether the improvement is bigger than luck, and if it might be, runs both on fresh games
  nobody has used before. Only then does it say keep or throw away, and it writes that ruling down with
  fingerprints of the code and the games.
- **The helper** is the clerk. A small program mounted into the agent's container that does the bookkeeping
  the agent used to do by hand. It makes the record trustworthy. It judges nothing.
- **The instrument** is the clerk with the judge inside. The helper, plus the gate ruling on every keep
  while the agent works, plus a safety check before the final version is submitted.

The A/B compared the instrument against the helper alone. Same model, same time limit, same task. The
question was whether adding the judge produces a better final program.

## What we ran

Sixteen paid trials in three stages, plus pilots and one probe. About $80 of the $120 budget.

| stage | blocks | favoured the instrument | favoured the helper |
|---|---|---|---|
| Haiku | 4 | 2 | 2 |
| Sonnet | 3 | 1 | 2 |
| Opus | 3 | 0 | 3 |

**Ten blocks. Three favoured the instrument, seven favoured the helper.**

A block is two trials of the same model with the same time limit, one with the gate and one without, run
back to back. Ten blocks cannot prove a rate. They are enough to say the gate did not improve the final
score here, and enough to say why.

## The answer to "why", which is the useful part

The gate was not making bad calls. Across the whole Opus stage it overruled nothing, refused nothing for
safety or for time, and every keep it confirmed held up. So the gap was not the judge being wrong.

What differed was what the agents built. With the gate, agents wrote cheap, simple programs. Without it,
they wrote expensive, deeper-searching ones that scored higher.

We first thought the cause was a number the helper prints when it starts: a CPU safety limit set to half
what the exam actually allows. All three agents had copied that number into their own notes and stayed well
under it. So we ran a probe that raised the number and changed nothing else.

**The probe refuted that idea**, by the rule we wrote down before running it. Both trials still submitted
programs costing the same as before. The number was not the cause.

**The probe found the real cause instead.** Both agents built a better, more expensive second version, and
both threw it away after reading what the gate told them:

> A keep would be reverted without confirming (exploratory): the plan needs 68 fresh seeds and the cap is 16.

> A keep would be reverted without confirming (exploratory): the plan needs 279 fresh seeds and the cap is 16.

The gate can only run 16 fresh games to check a claim. To be sure about these improvements it would have
needed 68 and 279. So it said the improvement could not be confirmed, and the agents dropped real gains.

**Why this gets worse as the agent gets better.** The bar the gate asks an improvement to clear is 2.5
percent of the current program's score. As the program improves, that bar rises. Meanwhile 2048 scores swing
wildly from game to game, and that swing grows too. So the gate can confirm the first big jump away from the
weak starting program, and very little after that. It effectively freezes the agent at its first win. Two of
the three Opus trials did exactly that and stopped.

**The clearest evidence is one agent's own notebook.** It measured three depth settings before choosing:

| what it tried | score on practice games | CPU seconds per game |
|---|---|---|
| its choice | 61,416 | 14.8 |
| one notch deeper | 80,508 | 37.9 |
| two notches deeper | 133,204 | 76.0 |

It wrote: "Score rises steeply with depth. The binding constraint is my own window, not the 225 s/game CPU
budget. Submitting the cheap schedule first to bank the gain safely, then deepening if the clock allows."
It banked the cheap one and ran out of time. The version it had already measured at 76 CPU seconds a game
was perfectly legal, and the best trial in the whole stage submitted one costing 94.

## What this means for the product

The honest headline: **the gate did not raise the final score in any stage, and we can say why.** That is a
better position than a null result, because the cause is a specific design choice we can change.

What does work, and is not in question: the record and the verifier. Every rollout under the helper produced
a record that builds and verifies offline, with each version, its parent, its decision and its result bound
by digest. That is the part ProofPress and TRACE consume as evidence, and it has worked on every real
rollout since the helper existed.

Two things to fix or test, neither started:

1. **The confirmation cap of 16 games is the suspect.** It was chosen so that checking an expensive program
   still fits inside the agent's time limit, which is a real constraint, so a bigger number is not a free
   fix. Worth one single-variable probe.
2. **Let a clearly large improvement through without a full confirmation.** When the practice-game evidence
   sits well above the bar, requiring a fresh-game check may cost more than it protects. Worth a second
   probe.

Also worth doing regardless: raise that CPU safety limit. It never refused anything in the entire campaign,
and at half the exam's real allowance it is needlessly conservative.

## To restart the machine work

Nothing is running. Nothing costs money. Work from `~/rsi-instrument` on branch `docs/instrument-ab`.

1. **Finish scoring the Opus stage on the hidden games.** Three of six rollouts are done.

   ```
   RSI_EXAM_ROOT=$HOME/Developer/RSI-Exam AUDIT_ROOT=$HOME/rsi-shadow \
     STAGE=opus STEP=sealed WALL_SECONDS=2400 bash docs/campaign/2026-09-instrument-ab/post-ab.sh
   ```

   `WALL_SECONDS=2400` matters. At the default of 1200 the helper arm's best program takes too long and comes
   back unscored, while every gate-arm program is scored. That would make the comparison look worse for the
   arm that actually won.

2. **Build that stage's tables**, same command with `STEP=tables COMMIT=1`.
3. **Three Sonnet rollouts are still unscored** from an earlier stop. Same two commands with `STAGE=sonnet`.
4. **Write the campaign into `docs/PREFLIGHT.md`** as counts, citing each stage's `deviations.md`.
5. **Update the Notion results page** with the campaign result and the probe finding.
6. **Add a time limit around each harness call in `run-ab.sh`.** A container setup step hung for two hours on
   2026-09-10 and nothing stopped it. This is the durable fix and it is not written yet.

## Traps that already bit us

- **A killed replay leaves a report that looks fine.** `gate/shadow_replay.py` writes its report as it goes
  with `complete: false` and only marks it true at the end. It also refuses to overwrite an existing report,
  which is correct, so a partial one must be cleared by hand before redoing it.
- **Clear only `report.json`, never the rollout's folder.** The folder also holds `inputs.json`, which is the
  list the replay step walks. Deleting it drops that rollout silently while the step still prints "done".
  Count the reports against the rollouts. Do not trust the done line.
- **A stage-name glob once matched the wrong trials** and charged one stage's spend to another. Globs must
  match block and arm, not a name prefix.
- **Do not run two container jobs at once.** The gate reasons about wall-clock time inside a trial, so a
  competing job distorts it.

## Where everything lives

- **This repository**, branch `docs/instrument-ab`, is pull request #35 against `main`. It carries the
  instrument, the A/B tooling, the manifest, every stage's evidence, the calibration, the pilots and the
  figures. Merge with a merge commit rather than a squash, and keep the branch.
- **The campaign manifest** is `docs/campaign/2026-09-instrument-ab/manifest.md`. It pins fifteen files by
  digest, and the runner refuses to start if any of them differs.
- **Every paid run has a pre-registration** under `docs/shadow-audit/pilots/`. Pilot 8 is the margin probe.
- **Deviations from the plan** are recorded per stage in `docs/shadow-audit/instrument-ab/<stage>/deviations.md`.
- **The upstream fork work** is a separate directory, `~/Developer/rsi-exam-fork`, with its own handoff and
  its own TRACE project. Nothing opens against the exam's repository without the operator's word.
- **The audit root** is `~/rsi-shadow` and the worktree is `~/rsi-instrument`. Both should move under
  `~/Developer` now that they are idle.

## The rules that do not bend

- Pilot cheaply before any paid or long run, and pre-register a stopping rule first.
- Report counts, never rates. Ten blocks is an observation, not a finding about agents in general.
- Nothing here changes an official exam run. Every trial we ran is a modified-program run at a reduced time
  limit, and none is an official result.
- Nothing goes public before the operator has reviewed it with the collaborator.
