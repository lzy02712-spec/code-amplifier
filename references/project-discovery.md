# Project discovery

Use this reference when build/test commands are ambiguous or the repository is a monorepo.

## Evidence priority

Prefer command sources in this order:

1. Explicit user instruction.
2. Repository agent/contribution instructions.
3. CI workflow commands.
4. Build/package scripts committed to the repository.
5. Tool configuration that clearly establishes a standard command.
6. Safe ecosystem defaults only when project markers make them unambiguous.

Do not invent commands solely from file extensions.

## Common markers

- Maven: `pom.xml`, preferably `./mvnw` when present.
- Gradle: `build.gradle`, `build.gradle.kts`, preferably `./gradlew` when present.
- Node: `package.json`; use only scripts actually declared for lint/typecheck/test/build categories.
- Python: `pyproject.toml`, `setup.cfg`, `tox.ini`, `pytest.ini`; prefer configured tools/dependencies.
- Go: `go.mod`.
- Rust: `Cargo.toml`.

## Monorepos

Do not run every expensive workspace check by default. Determine which package owns the changed code, run focused checks first, then run the repository's normal regression gate when feasible.

If multiple project markers are present, report all detected project types rather than picking one arbitrarily.
