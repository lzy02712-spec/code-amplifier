# CodeAmplifier

A verification-driven Agent Skill for making coding agents behave more reliably, especially when using smaller, cheaper, or local models.

The core idea is simple:

> structured execution + deterministic verification + failure classification + repair loop > self-confidence

## What it does

The skill forces repository-changing tasks through:

`DISCOVER -> ACCEPTANCE -> PLAN -> IMPLEMENT -> VERIFY -> REPAIR -> AUDIT -> DONE`

It includes deterministic helper scripts for project detection, verification, diff inspection, and evidence aggregation.

## Install

Copy this directory into an Agent Skills-compatible skills directory, for example:

```text
.agents/skills/coding-amplifier/
```

The folder containing `SKILL.md` is the skill root.

## Helper scripts

```bash
python scripts/detect_project.py --root /path/to/repo
python scripts/verify.py --root /path/to/repo --output verification.json
python scripts/inspect_diff.py --root /path/to/repo --output diff.json
python scripts/evidence.py --verification verification.json --diff diff.json --requirements requirements.json
```

### Optional project-specific command config

Create `.coding-amplifier.json` in the target repository when automatic discovery is not sufficient. Explicit configured commands override discovered commands.

```json
{
  "commands": {
    "test": ["npm", "test"],
    "lint": ["npm", "run", "lint"]
  }
}
```

Commands must be JSON arrays. `null` means the category is intentionally not configured.

## Safety properties

- Never treats model confidence as test evidence.
- Never silently converts missing checks to PASS.
- Does not invent package scripts that are absent from the repository.
- Keeps verification commands non-interactive.
- Does not modify repository files unless the coding agent itself chooses to do so for the user's task.

## Evaluation

`evals/evals.json` contains initial realistic prompts for with-skill vs baseline evaluation. The intended headline metric is repository task success rate, supplemented by token/cost, repair rounds, and verification completeness.

## License

MIT.
