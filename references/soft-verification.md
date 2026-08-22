# Soft verification

Use soft verification only for criteria that deterministic repository checks cannot fully prove, such as root-cause quality, requirement coverage, architecture fit, or regression risk.

## Precedence

Hard evidence always wins:

- deterministic `FAIL` => task cannot be accepted;
- deterministic `UNKNOWN` => gather evidence before treating the task as verified;
- soft confidence may help choose repair/replan/resample actions, but never converts a hard failure into success.

## Backends

`soft_verifier.py` supports three backends:

1. `heuristic` — zero-dependency fallback used for local automation and tests;
2. `llm-verifier` — optional adapter to the `llm-verifier` package's trajectory progress scorer;
3. `openai-json` — optional OpenAI-compatible structured reviewer.

Prefer `llm-verifier` or another calibrated verifier when available. Keep the heuristic backend as a fallback signal, not a correctness oracle.

## Criteria

Generate a small number of task-specific criteria. Typical coding criteria are:

- task correctness;
- root cause / implementation quality;
- regression safety;
- empirical verification;
- security/isolation when the task touches sensitive boundaries.
