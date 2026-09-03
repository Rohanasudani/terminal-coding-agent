# Interactive App

TermAgent can run as an interactive terminal app:

```bash
termagent app --repo /path/to/repo --approval-mode suggest
```

This opens a small task loop:

```text
TermAgent interactive mode
repo: /path/to/repo
provider: repair
approval: suggest
Type a coding task, :doctor, :help, or :quit.
termagent>
```

## Commands

- `:doctor`: checks local prerequisites
- `:help`: shows session commands
- `:quit`: exits the app

Any other input is treated as a coding task and runs through the same agent loop as `termagent run`.

## Example

```text
termagent> Fix the failing tests and show the final diff
termagent> :quit
```

## Why This Exists

The one-shot CLI is good for automation and benchmarks. The interactive app is better for demos, interviews, and repeated local workflows because someone can point the agent at a repository and issue multiple tasks without rebuilding the command each time.

## Safety

Interactive mode uses the same safety controls as one-shot runs:

- repository-root path sandboxing
- planned writes before file edits
- shell command classification
- default network blocking
- cost ceilings for live providers
