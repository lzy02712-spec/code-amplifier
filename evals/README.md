# Evaluation protocol

V2 supports fully automated paired benchmarks.

## Generate evals automatically

```bash
python scripts/generate_evals.py \
  --root /path/to/target-repo \
  --limit 20 \
  --output evals/generated.json
```

The generator mines real non-merge Git history. Prompts are derived from commit subjects; future commit metadata is retained under `oracle` and is never passed to the coding agent.

## Run Direct vs Amplified automatically

```bash
python scripts/benchmark.py \
  --repo /path/to/target-repo \
  --evals evals/generated.json \
  --agent-command 'my-coding-agent --workspace {workspace} --task-file {task_file}' \
  --output results/benchmark.json \
  --report results/report.md
```

The same agent command runs in two isolated worktrees. Amplified mode receives the Agent Skill automatically; Direct mode does not.

## Primary metric

Task success rate under the configured acceptance gate:

- hard verification must pass;
- soft score must meet threshold;
- the agent must have produced a real non-skill change.

## Secondary metrics

Record hard status, soft score, elapsed time, changed files, oracle file overlap, captured trajectory tail, and optional provider-side token/cost data when the host exposes it.

## Fairness

Keep model, agent host, repository revision, task prompt, permissions, timeout, and provider configuration fixed between Direct and Amplified. The intended treatment variable is the CodeAmplifier Skill.
