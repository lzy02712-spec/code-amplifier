# Failure taxonomy

Classify before repairing so the next action follows evidence instead of guesswork.

## COMPILE_FAILURE
Build/compile command fails. Read the first causal error, not only the final summary.

## TEST_FAILURE
A test executes and fails. Preserve the failing test name and assertion/stack trace. Do not weaken the test unless the requirement proves the test is obsolete.

## TYPE_FAILURE
Static type checking fails. Prefer fixing the type contract rather than suppressing the checker.

## LINT_FAILURE
Repository-configured static/lint rule fails. Fix the underlying issue unless the rule conflicts with an explicit requirement.

## REQUIREMENT_MISS
The implementation does not satisfy a ledger criterion even if automated tests pass. Add targeted evidence where feasible.

## REGRESSION
Previously working behavior or unrelated tests fail after the change. Inspect scope creep and coupling.

## ARCHITECTURE_VIOLATION
The change crosses a documented boundary or breaks an accepted project pattern.

## SECURITY_FAILURE
Authentication, authorization, isolation, secret handling, validation, or dependency checks reveal a material issue.

## WRONG_ASSUMPTION
Evidence contradicts an implementation assumption. Stop patching the symptom and re-read the relevant source/contract.

## INCOMPLETE_IMPLEMENTATION
Part of the requested behavior is missing, stubbed, TODO, or unconnected.

## ENVIRONMENT_FAILURE
Verification cannot complete because the environment lacks a dependency, service, credential, or supported runtime. Report the limitation exactly.
