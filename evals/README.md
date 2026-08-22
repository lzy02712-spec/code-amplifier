# Evaluation protocol

The initial eval set is designed for paired comparison:

- Baseline: same coding model and host, no `coding-amplifier` skill.
- Treatment: same coding model and host, `coding-amplifier` enabled.

Keep model, temperature, repository revision, task prompt, tool permissions, and time/token budget as similar as the host allows.

## Primary metric

**Task success rate**: all material acceptance criteria are satisfied and the repository's relevant deterministic gates pass.

## Secondary metrics

Record for each run:

- model and host;
- success/failure;
- requirement pass count;
- deterministic verification completeness;
- repair rounds;
- tokens;
- estimated cost;
- elapsed time;
- files changed;
- whether tests were weakened/disabled;
- whether the agent falsely claimed completion before verification.

## Suggested ablation

Compare:

1. baseline model;
2. model + planning only;
3. model + planning + verification;
4. model + planning + verification + repair;
5. full skill including requirement ledger and final audit.

This shows which parts create the improvement instead of attributing every gain to a large prompt.
