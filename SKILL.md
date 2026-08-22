---
name: coding-amplifier
description: Verification-driven execution protocol for coding agents. Use this skill whenever the user asks to implement, modify, debug, refactor, review, or repair code in a repository, especially when using smaller, cheaper, local, or less reliable coding models. It forces repository discovery, explicit acceptance criteria, minimal implementation, deterministic verification, failure classification, evidence-driven repair, regression checks, and a final audit before claiming completion.
compatibility: Requires a coding agent that can read repository files and run local commands. Python 3.10+ is recommended for bundled helper scripts; Git is recommended for diff inspection.
---

# Coding Amplifier

Use disciplined execution and external evidence to improve coding-task reliability. The model's confidence is never proof. Fresh repository evidence is proof.

## Core invariants

1. Do not claim completion without fresh verification evidence.
2. Do not invent project commands. Discover them from repository files, project configuration, or explicit user instructions.
3. Do not weaken, delete, skip, or rewrite tests merely to make a failure disappear unless the user explicitly asks for a test change and the change is justified by the requirement.
4. Prefer the smallest change that satisfies the acceptance criteria.
5. Preserve architecture, interfaces, ownership boundaries, security constraints, and repository conventions unless the task explicitly changes them.
6. Distinguish implementation success from verification success. Code can be written while the task remains `NOT_VERIFIED`.
7. Treat command output, exit codes, tests, static analysis, and repository diffs as stronger evidence than self-review.
8. If a required check cannot run, record it as `UNKNOWN` or `NOT_CONFIGURED`; never silently convert it to `PASS`.

## State machine

Follow this sequence for repository-changing tasks:

`DISCOVER -> UNDERSTAND -> ACCEPTANCE -> PLAN -> IMPLEMENT -> VERIFY -> AUDIT -> DONE`

On verification failure:

`VERIFY -> CLASSIFY_FAILURE -> REPAIR -> VERIFY`

Do not transition directly from `IMPLEMENT` to `DONE`.

For tiny tasks, the plan may be one sentence, but the verification and audit gates still apply.

## 1. DISCOVER

Before editing:

- Read the user's request completely.
- Inspect repository-local authority files that can constrain the task: README, contributing instructions, agent instructions, architecture docs, package/build files, test configuration, and nearby code.
- Inspect current Git status before changing anything. Do not overwrite unrelated user work.
- Run `scripts/detect_project.py --root <repo>` when Python is available.
- Prefer explicit repository commands over ecosystem guesses.

Read `references/project-discovery.md` when the repository has multiple languages, nested projects, monorepo tooling, or ambiguous build commands.

## 2. UNDERSTAND

Identify:

- the behavior that must change;
- the code and tests most likely responsible;
- constraints that must remain unchanged;
- relevant public APIs, schemas, migrations, security boundaries, and compatibility requirements;
- uncertainty that requires evidence before editing.

Do not start broad refactoring to "make things cleaner" unless it is necessary for the requested change.

## 3. ACCEPTANCE

Create a short requirement ledger before implementation. Each requirement needs an identifier and a verifiable completion condition.

Example:

```text
R1  Duplicate email returns HTTP 409.        PENDING
R2  Cross-tenant reads remain impossible.    PENDING
R3  Existing create-user API stays compatible.PENDING
```

Statuses are: `PENDING`, `PASS`, `FAIL`, `UNKNOWN`.

Keep the ledger in agent scratch state or a temporary file outside tracked source unless the project explicitly wants it committed.

Read `references/requirement-ledger.md` for complex or multi-part tasks.

## 4. PLAN

Make the smallest credible implementation plan. Include:

- files/components likely to change;
- tests/checks that will prove each requirement;
- risky assumptions that must be validated;
- expected regression surface.

Do not use planning as a substitute for execution.

## 5. IMPLEMENT

During implementation:

- make narrow, reversible changes;
- follow local naming and architecture conventions;
- add or update tests when behavior changes and the repository has a test pattern for it;
- avoid unrelated formatting churn or drive-by refactors;
- re-read affected code after substantial edits;
- preserve user changes already present in the worktree.

## 6. VERIFY

Verification is a hard gate.

When available, run:

```bash
python <skill-dir>/scripts/verify.py --root <repo> --output <verification.json>
```

The helper discovers configured checks and records command, exit code, duration, and status. Repository-provided explicit commands take precedence.

Also run targeted checks when they provide stronger evidence than a broad default. Examples include the specific failing test, a focused module test, schema validation, generated-code consistency, or a repository-native CI task.

If a command fails, do not immediately patch random code. Classify the failure first.

Read `references/verification.md` for gate semantics and `references/failure-taxonomy.md` before repair.

### Verification status rules

- `PASS`: the relevant command ran and succeeded.
- `FAIL`: the relevant command ran and failed.
- `NOT_CONFIGURED`: no credible repository check was discovered for that category.
- `UNKNOWN`: the check should exist or matters to the requirement, but could not be executed or interpreted.

A task with a material `FAIL` is not complete. A task with a material `UNKNOWN` is not verified.

## 7. CLASSIFY_FAILURE AND REPAIR

Classify each meaningful failure as one of:

- `COMPILE_FAILURE`
- `TEST_FAILURE`
- `TYPE_FAILURE`
- `LINT_FAILURE`
- `REQUIREMENT_MISS`
- `REGRESSION`
- `ARCHITECTURE_VIOLATION`
- `SECURITY_FAILURE`
- `WRONG_ASSUMPTION`
- `INCOMPLETE_IMPLEMENTATION`
- `ENVIRONMENT_FAILURE`

Then repair the root cause using the evidence that produced the classification.

Default repair loop:

1. Preserve the failing command/output.
2. Locate the smallest relevant implementation surface.
3. State the likely root cause in one concise sentence.
4. Apply the smallest fix consistent with requirements.
5. Re-run the targeted failing check.
6. Re-run relevant regression checks.
7. Update the requirement ledger.

Do not perform more than three blind repair cycles for the same unchanged failure signature. After that, stop guessing, gather new evidence, or report the blocker.

## 8. AUDIT

Before `DONE`:

1. Re-read the original user request.
2. Map every requirement ID to concrete evidence.
3. Inspect the final repository diff.
4. Check for accidental unrelated changes, debug artifacts, disabled tests, TODO placeholders, secret material, generated junk, and compatibility breaks.
5. Ensure material verification checks are `PASS`, or explicitly explain any `UNKNOWN`/`NOT_CONFIGURED` limitations.

When Git is available, run:

```bash
python <skill-dir>/scripts/inspect_diff.py --root <repo> --output <diff.json>
```

Optionally aggregate machine-readable evidence:

```bash
python <skill-dir>/scripts/evidence.py \
  --verification <verification.json> \
  --diff <diff.json> \
  --requirements <requirements.json> \
  --output <evidence.json>
```

Read `references/final-audit.md` for the final gate.

## Completion gate

Use `DONE` only when:

- implementation matches the requested scope;
- every material requirement is `PASS`;
- no material verification check is `FAIL`;
- no material requirement is `UNKNOWN`;
- the final diff has been inspected;
- the final report accurately distinguishes what was verified from what was not run.

Otherwise use `NOT_VERIFIED`, `PARTIALLY_VERIFIED`, or `BLOCKED` as appropriate.

## Final response format

Keep the report compact and evidence-oriented:

```text
Status: VERIFIED | PARTIALLY_VERIFIED | NOT_VERIFIED | BLOCKED

Changed:
- <what changed>

Requirements:
- R1 PASS — <evidence>
- R2 PASS — <evidence>

Verification:
- tests: PASS — <command>
- lint: NOT_CONFIGURED
- typecheck: PASS — <command>

Notes:
- <remaining limitation only if relevant>
```

Do not say "should work", "looks good", or equivalent language when the final gate has not produced evidence.

## Tool fallback

If the host cannot execute the bundled scripts:

- perform the same workflow using native repository tools;
- capture exact commands and outputs;
- preserve the same status semantics;
- never replace unavailable deterministic verification with model confidence alone.
