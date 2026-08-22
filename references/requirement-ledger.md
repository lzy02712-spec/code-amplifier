# Requirement ledger

The ledger prevents "tests passed but the user request was only partially implemented" failures.

Each entry should contain:

- `id`: stable short identifier such as `R1`.
- `criterion`: observable behavior or constraint.
- `status`: `PENDING`, `PASS`, `FAIL`, or `UNKNOWN`.
- `evidence`: exact test, command, diff location, or direct inspection that supports the status.

Example JSON:

```json
{
  "requirements": [
    {
      "id": "R1",
      "criterion": "Duplicate email returns HTTP 409",
      "status": "PASS",
      "evidence": "UserApiTest.testDuplicateEmail"
    },
    {
      "id": "R2",
      "criterion": "Tenant isolation is preserved",
      "status": "UNKNOWN",
      "evidence": "Integration environment unavailable"
    }
  ]
}
```

A requirement is not `PASS` merely because related code exists. Prefer behavior-level evidence.
