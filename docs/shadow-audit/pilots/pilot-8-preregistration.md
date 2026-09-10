# Pilot 8: does the stated CPU safety margin change what the agent builds?

Written 2026-09-10, before any trial of this probe started.

**Where this comes from.** In the comparison's Opus stage every block favoured the helper-only arm
(instrument 0.551, 0.346, 0.414 against 0.608, 0.602, 0.533). The gate's rulings do not explain it: no keep
was overruled, every confirmed keep held, no keep was refused for safety or for time, and all three
instrument records verified. What differed is what the agents built. Heads under the instrument cost 13.5,
13.6 and 3.5 CPU seconds per game on the public seeds; versions under the helper alone cost 18.3 to 94.4.
All three instrument agents wrote the helper's stated safety margin into their own notes and optimised
against it, in their words keeping the head "far under the 112.5 s helper margin" and "far inside the
112.5 s margin". No helper-arm agent mentions a margin, because the helper never states one.

That margin is half the grader's limit. `init` prints it as `safety margins 112.5 cpu s per game and 2.5 s
per move on the public seeds`, from `PROVENANCE_SAFETY_FRACTION` (default 0.5) times the task's 225 CPU
seconds per game. Nothing in the loop text names a number; the agent learns it from that one line.

**Question.** Does raising the stated margin change what the agent builds? Specifically, do the versions an
Opus agent writes under the instrument cost more CPU per game, and does the head it submits cost more, when
`init` states 202.5 instead of 112.5?

**Why this separates two explanations.** The instrument arm's result could come from the gate's rule (the
statistics rejecting improvements) or from the package's stated constraints (one printed number anchoring
what the agent attempts). The rule is unchanged in this probe. Only the number changes. A change in what
the agent builds is therefore attributable to the stated margin, not to the rule.

**The manipulation.** `PROVENANCE_SAFETY_FRACTION=0.9`, so the margins become 202.5 CPU seconds per game
and 4.5 seconds per move. No change to the loop text, the gate, the rule, the profile, the window, or the
model. The variable reaches the container through a new compose overlay
(`runbook/mount-instrument-margin.yaml`), which is `runbook/mount-instrument.yaml` plus one environment
line; the campaign's own mount file and every other file its manifest pins are untouched.

**Why 0.9 and not 1.0.** The margin exists because the grader's limit is pooled over sixteen sealed games
run by one process, while the helper measures eight public games. A strong policy plays longer sealed games
than public ones, so the sealed cost per game can exceed the public measurement. The one policy that did
exhaust the pooled budget in an earlier campaign was never evaluated on the public seeds, so it cannot
calibrate the margin. What is measured: a policy costing 94.4 public CPU seconds per game completed all
sixteen sealed games with a valid fraction of 1.0. A margin of 202.5 leaves about ten percent of the
grader's limit as headroom for the public-to-sealed ratio while removing the anchor. Whether the production
default moves to 0.9, higher, or to the limit itself is a separate decision this probe informs.

**Trials, in order.**

1. Plumbing, `claude-haiku-4-5-20251001`, effort `low`, multiplier 0.002 (86.4 s; the helper is told 80 s),
   one trial, job `probe-margin-smoke-1`. Haiku policies cost about 0.1 CPU seconds per game, so the margin
   cannot bind. This trial checks one thing: that `init` prints `safety margins 202.5 cpu s per game and 4.5
   s per move`. Ceiling $1.00.
2. The probe, `claude-opus-5`, effort `max`, multiplier 0.045 (1944 s; the helper is told 1900 s), two
   trials, jobs `probe-margin-1` and `probe-margin-2`, otherwise identical to the Opus stage's instrument
   arm at commit `ef82cf2` (floor 8, cap 16, estimate-aware rule, minimum effect 2.5 percent, operator's
   key). Reservation $8.00 per trial, ceiling $20.00. The second trial starts only if the first cost at most
   $12.00.

**Primary measure, per trial.** The CPU seconds per game, on the public seeds, of every version the agent
evaluates, and of the head it submits. These are read from the helper's own log lines.

**Secondary measures.** Gate lines by disposition; confirmations with their sizes and wall time; keeps
refused for safety or for time; versions built; the fraction of the window used; whether the record builds
and verifies; the grader's reward and valid fraction of the submission, as incidental numbers; priced cost.

**Reading it, stated before the trials.** The instrument heads at the stated margin of 112.5 cost 13.5, 13.6
and 3.5 CPU seconds per game; the cheapest helper-arm version at no stated margin cost 18.3.

- If both probe heads cost more than 20 CPU seconds per game, the stated margin is supported as an anchor on
  what the agent builds, and the Opus stage's result is at least partly an artefact of one printed number
  rather than of the gate's rule.
- If both probe heads cost 14 CPU seconds per game or less, the stated margin is not supported as the cause,
  and the preference for cheap policies belongs to the agents or to another part of the package.
- Anything else is inconclusive and is reported as such.

Two trials cannot establish a rate, and this is a comparison against trials that already ran on an earlier
day rather than a fresh randomized pairing. It is a probe of a mechanism, not evidence of an effect on the
score. The grader's reward is reported because it is there, and no claim rests on it.

**Money and stopping.** Campaign spend before this probe is $59.64 of the $120.00 ceiling, so the probe's
$21.00 of ceilings stays inside it. Any harbor non-zero exit, missing job directory, or trial that did not
end normally or by the harness timeout with assistant usage in its session log stops the probe. Every
started trial is reported. If the plumbing trial does not print 202.5, no Opus trial starts.
