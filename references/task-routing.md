# Adaptive Task Routing

## Purpose

Adaptive routing reduces unnecessary execution overhead while preserving the full verification workflow for complex coding tasks.

## FAST_PATH

Use FAST_PATH for low-risk tasks:

- single-file changes
- explicit small edits
- documentation updates
- configuration changes
- trivial accessors or formatting changes
- changes with no architecture, API, security, or data-model impact

Workflow:

```
QUICK_DISCOVER
  -> MINIMAL_ACCEPTANCE
  -> IMPLEMENT
  -> LIGHT_VERIFY
  -> DONE
```

FAST_PATH still requires evidence. It never skips verification completely.

## FULL_PATH

Use FULL_PATH for:

- multi-file changes
- unclear bugs
- security-sensitive changes
- refactoring
- architecture changes
- migrations
- legacy systems
- changes requiring root-cause investigation

Workflow:

```
DISCOVER
 -> UNDERSTAND
 -> ACCEPTANCE
 -> PLAN
 -> IMPLEMENT
 -> HARD_VERIFY
 -> SOFT_VERIFY
 -> AUDIT
 -> DONE
```

## Routing principles

1. Optimize for evidence per unit cost.
2. Prefer FAST_PATH only when risk is low.
3. Unknown risk defaults to FULL_PATH.
4. Verification remains mandatory in both paths.
