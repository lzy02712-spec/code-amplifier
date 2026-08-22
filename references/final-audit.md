# Final audit

Before completion, inspect the final diff and answer:

- Does every changed file contribute to a requirement or necessary test/support work?
- Did the change accidentally alter public APIs, schemas, migrations, configuration, or dependencies?
- Were tests disabled, loosened, deleted, skipped, or converted into weaker assertions?
- Are there debug prints, temporary files, TODO placeholders, generated artifacts, or secrets?
- Are untracked files part of the user's pre-existing work?
- Does every requirement have direct evidence?
- Did the final regression command run after the final repair?

If any material answer is unknown, do not report fully verified completion.
