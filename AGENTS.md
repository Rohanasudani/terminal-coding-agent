# Working On TermAgent

Read PROJECT_SCOPE.md before choosing or implementing the next milestone.
The core deliverable includes real agent comparisons and measured improvements,
not just a working terminal interface or passing deterministic fixtures.

- Keep runtime changes general. Task-specific answers belong only in labeled test
  or baseline code and must not be used by the live controller.
- Preserve failed experiment results and identify dataset, model, agent version,
  settings, and budget differences when making comparisons.
- Do not describe exported tasks, mocked tests, or deterministic demos as a live
  external benchmark result.
- Preserve existing uncommitted work. Use the existing structured tools and
  provider interfaces before adding dependencies or new layers.
- Run focused regression tests for behavior changes and the full suite for shared
  runtime or evaluation changes. Harbor is optional and requires Python 3.12+.
- Keep API credentials and raw traces out of committed artifacts. Paid experiments
  must stay within the user's authorized budget.
