# Verification semantics

Verification should be deterministic whenever possible.

## Strong evidence

From strongest to weaker:

1. Repository-native test or executable acceptance check.
2. Compile/build/type checker with a successful exit code.
3. Linter/static analyzer configured by the repository.
4. Focused runtime reproduction of the reported bug.
5. Diff inspection tied directly to an acceptance criterion.
6. Model review or reasoning.

Model review is useful for finding candidate problems, but it does not override failing deterministic evidence.

## Targeted then regression

For a bug fix:

1. Reproduce or run the failing test.
2. Fix the root cause.
3. Re-run the focused test.
4. Run nearby/module regression checks.
5. Run the normal broader gate when practical.

## Timeouts and environment failures

A timeout, missing dependency, unavailable service, credential requirement, or unsupported platform should usually become `UNKNOWN`/`ENVIRONMENT_FAILURE`, not `PASS`.

Never hide a failing command by omitting it from the final report.
