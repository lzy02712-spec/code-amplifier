# Automated benchmark protocol

CodeAmplifier uses paired A/B evaluation.

For every task:

- Direct and Amplified start from the same Git base revision.
- They receive the same task prompt.
- They run the same configured agent command and timeout.
- Amplified gets `.agents/skills/coding-amplifier`; Direct does not.
- Hidden oracle fields remain outside the prompt.
- Deterministic verification runs after the agent exits.
- Soft verification is supplemental and cannot override a hard failure.

## Eval generation

`generate_evals.py` mines non-merge Git history. Each selected historical commit becomes:

- `base_ref`: the parent commit given to the agent;
- `prompt`: derived from the historical commit subject;
- `criteria`: task-specific verification dimensions;
- `oracle.target_ref`: hidden future commit for grader-side metadata;
- `oracle.changed_files`: expected change surface, never exposed to the agent.

This is a bootstrap generator, not a perfect benchmark. Prefer repositories with descriptive commit subjects and meaningful tests. Future generators may add mutation-validated tasks and issue/PR reconstruction.

## Success

A benchmark run is counted as successful only when:

1. deterministic verification reports `PASS`;
2. the soft-verification score clears the configured threshold;
3. the agent produced a non-skill code/worktree change.

The report keeps file-overlap with the hidden historical patch as diagnostic metadata, not as the sole correctness criterion.
