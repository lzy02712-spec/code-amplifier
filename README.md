# CodeAmplifier

**Verification-driven capability amplification for coding agents.**

CodeAmplifier is an Agent Skill plus automation harness designed to make smaller, cheaper, or local coding models more reliable without replacing the coding tool they already run inside.

The core loop is:

> execute → observe → hard verify → soft verify → diagnose → repair/replan → verify again

The project does **not** treat model confidence as proof. Deterministic evidence has final veto power.

## V2.1 automation core

V2.1 adds a strict hidden-grader layer on top of the V2 automation and adaptive-verification stack:

- Agent Skills-compatible `SKILL.md`
- deterministic project detection and hard verification
- task-specific soft verification
- optional `llm-verifier` integration for trajectory progress scoring
- adaptive `CONTINUE / REPAIR / REPLAN / RESAMPLE / DONE` policy
- automatic eval generation from real Git history
- extraction of future test/spec files as hidden graders
- oracle validation: future tests must fail on the base revision and pass on the real target revision
- isolated Direct vs Amplified A/B benchmark worktrees
- strict hidden-test success plus separate provisional soft metrics
- paired win/regression reporting
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
  --require-hidden-tests \
  --output evals/generated.json
```

Each eval contains a public task prompt plus a hidden oracle section. The future commit SHA, expected changed files, and future test files are not passed to the agent. For strict benchmarking, use `--require-hidden-tests` so only commits with future test/spec changes are emitted.

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

## Strict hidden grader

Before either A/B run is counted, CodeAmplifier validates the oracle:

```text
base revision + future hidden tests   -> must FAIL
target revision + same tests         -> must PASS
```

Only tasks satisfying both conditions are **strict gradable**. After the agent finishes, the benchmark overlays only those validated future test files onto the ephemeral agent workspace and runs the repository test command again. The agent never sees the hidden tests before its run.

Strict success requires:

```text
public hard verification PASS
AND
validated hidden grader PASS
AND
agent produced a real code change
```

Soft verification and file-overlap are diagnostic metrics only. They cannot create a strict success. Ungradable tasks are reported separately and excluded from the strict pass-rate denominator.

The benchmark records strict success, provisional success, oracle validation, hidden-test status, hard status, soft score, elapsed time, changed files, oracle-file overlap, and captured trajectory output. Provider token/cost metrics can be added when the coding host exposes them.

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

V2.1 introduces validated future-test grading for Git-history tasks. It is substantially stronger than the V2 soft/hard heuristic score, but it still does not make every historical commit gradable: tasks without discriminative future tests are excluded from strict statistics. Planned generators include mutation-validated tasks and issue/PR reconstruction.

## License

MIT
