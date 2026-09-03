## Summary

- 

## Verification

- [ ] `ruff check .`
- [ ] `pytest -q`
- [ ] `termagent bench --repo-root .`

## Safety

- [ ] File writes stay inside the repository root.
- [ ] New shell commands go through the safety classifier.
- [ ] No secrets, tokens, or private traces are committed.
