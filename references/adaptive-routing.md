# Adaptive Routing

## Purpose

CodeAmplifier should not spend the full verification protocol budget on every task.

The router selects between:

- FAST_PATH: lightweight execution for low-risk changes.
- FULL_PATH: complete verification-driven workflow.

## FAST_PATH criteria

Use when:

- single file change;
- explicit local change;
- no API, schema, security, or architecture impact;
- low regression surface.

FAST_PATH still requires:

- requirement understanding;
- implementation evidence;
- lightweight verification.

## FULL_PATH criteria

Use when:

- multi-file changes;
- debugging root causes;
- security changes;
- refactoring;
- architecture changes;
- uncertain requirements;
- legacy code changes.

FULL_PATH keeps the complete CodeAmplifier lifecycle.

## Safety rule

When classification is uncertain, prefer FULL_PATH.
