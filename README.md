# CodeAmplifier

**Verification-driven capability amplification for coding agents.**

CodeAmplifier is an Agent Skill plus automation harness designed to make smaller, cheaper, or local coding models more reliable without replacing the coding tool they already run inside.

The core loop is:

> execute → observe → hard verify → soft verify → diagnose → repair/replan → verify again

The project does **not** treat model confidence as proof. Deterministic evidence has final veto power.

## V2 automation core

V2 adds a fully automated evaluation and adaptive-verification layer:

- Agent Skills-compatible `SKILL.md`
- deterministic project detection and hard verification
- task-specific soft verification
- optional `llm-verifier` integration for trajectory progress scoring
- adaptive `CONTINUE / REPAIR / REPLAN / RESAMPLE / DONE` policy
- automatic eval generation from real Git history
- isolated Direct vs Amplified A/B benchmark worktrees
- automatic JSON + Markdown benchmark reports

## Runtime flow

```text
DISCOVER
  ↓
ACCEPTANCE
  ↓
PLAN
  ↓
IMPLEMENT
  ↓
HARD VERIFY ── FAIL ──> CLASSIFY ──> REPAIR / REPLAN
  │                                      │
  PASS/UNKNOWN                           └────> VERIFY
  ↓
SOFT VERIFY
  ↓
PROGRESS POLICY
  ├─ CONTINUE
  ├─ GATHER_EVIDENCE
  ├─ REPAIR
  ├─ REPLAN
  ├─ RESAMPLE
  └─ DONE
```

### Evidence precedence

```text
Hard FAIL  >  Soft score
```

A high LLM/verifier score can never convert a failing build/test/typecheck into success.

## Install the Skill

Copy the repository into an Agent Skills-compatible directory, for example:

```text
.agents/skills/coding-amplifier/
```

The folder containing `SKILL.md` is the skill root.

## Hard verification

```bash
python scripts/detect_project.py --root /path/to/repo
python scripts/verify.py --root /path/to/repo --output verification.json
python scripts/inspect_diff.py --root /path/to/repo --output diff.json
python scripts/evidence.py \
  --verification verification.json \
  --diff diff.json \
  --requirements requirements.json \
  --output evidence.json
```

Supported project detection currently includes Maven, Gradle, Node, Python, Go, and Rust. Node commands are only used when the corresponding `package.json` script actually exists.

Project-specific commands can be pinned in `.coding-amplifier.json`:

```json
{
  "commands": {
    "compile": ["./gradlew", "classes"],
    "test": ["./gradlew", "test"],
    "lint": null,
    "typecheck": null
  }
}
```

## Soft verification

Zero-dependency fallback:

```bash
python scripts/soft_verifier.py \
  --task-file task.txt \
  --trajectory trajectory.txt \
  --verification verification.json \
  --backend heuristic \
  --output soft.json
```

Optional `llm-as-a-verifier` adapter:

```bash
pip install llm-verifier
python scripts/soft_verifier.py \
  --task-file task.txt \
  --trajectory trajectory.txt \
  --verification verification.json \
  --backend llm-verifier
```

An OpenAI-compatible JSON verifier backend is also available with `--backend openai-json`.

## Adaptive progress policy

```bash
python scripts/progress.py \
  --scores 0.31,0.55,0.79 \
  --hard-status PASS \
  --budget-fraction 0.60
```

The policy can return `CONTINUE`, `GATHER_EVIDENCE`, `REPAIR`, `REPLAN`, `RESAMPLE`, `DONE`, or `STOP`.

## Fully automated eval generation

Mine real historical coding tasks from any Git repository:

```bash
python scripts/generate_evals.py \
  --root /path/to/target-repo \
  --limit 50 \
  --output evals/generated.json
```

Each eval contains a public task prompt plus a hidden oracle section. The future commit SHA and expected changed files are not passed to the agent.

## Fully automated Direct vs Amplified benchmark

Configure one generic coding-agent command. CodeAmplifier runs it in two isolated worktrees from the same base commit:

```bash
python scripts/benchmark.py \
  --repo /path/to/target-repo \
  --evals evals/generated.json \
  --agent-command 'my-coding-agent --workspace {workspace} --task-file {task_file}' \
  --output results/benchmark.json \
  --report results/report.md
```

Placeholders:

- `{workspace}` — isolated task worktree
- `{task_file}` — task prompt file
- `{prompt}` — raw task prompt
- `{mode}` — `direct` or `amplified`

In Amplified mode, the benchmark runner automatically installs CodeAmplifier into:

```text
.agents/skills/coding-amplifier/
```

Direct mode receives no Skill.

The benchmark records hard status, soft score, elapsed time, changed files, hidden-oracle file overlap, and captured trajectory output. Provider token/cost metrics can be added when the coding host exposes them.

## Design principles

1. **No evidence, no completion.**
2. **Hard verification has final veto power.**
3. **Repair root causes from observed failures, not self-reflection.**
4. **Same model, same task, same base revision for A/B measurement.**
5. **Hidden grader/oracle information is never exposed to the agent.**
6. **Do not require a proxy or a specific model provider.**
7. **Use more test-time compute only when evidence says it is useful.**

## Tests

```bash
python -m unittest discover -s tests -v
python -m compileall -q scripts
```

## Status

V2 is an automation baseline. Git-history eval generation is intentionally conservative and is not yet a substitute for SWE-bench-grade hidden tests. Planned generators include mutation-validated tasks and issue/PR reconstruction.

## License

MIT
