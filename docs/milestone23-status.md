# Milestone 23 Status

Status as of 2026-09-16: complete and superseded by
[milestone23-results.md](milestone23-results.md).

The task subset, wheel, source commit, model, competitor version, budgets, retry policy,
and reporting rules remained frozen. Oracle passed 3/3 and no-op passed 0/3 with no
exceptions. All nine live arms then ran once with no retries. Codex passed 3/3;
TermAgent passed 0/3 in both planning modes, with one setup exception per mode on a
task image that could not install the Python 3.12+ wheel.

The generated report retains rewards, exceptions, token usage, known cost, duration,
controller telemetry, limitations, and failure analysis. Raw trajectories remain in
the gitignored local Harbor jobs directory and are not published.
