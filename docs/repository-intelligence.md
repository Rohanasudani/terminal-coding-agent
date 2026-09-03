# Repository Intelligence

TermAgent now includes a lightweight Python code-intelligence layer built on the standard library `ast` module.

## Tools

- `code_map`: lists Python classes, functions, async functions, imports, and parse errors
- `find_references`: lists Python name references for a requested symbol

Example:

```bash
termagent tools --repo .
```

Live providers can call these tools through the same structured tool interface as search, file reads, patch planning, and shell execution.

## Patch Safety

Patch planning validates Python syntax for `.py` files before approving a plan. This means malformed Python cannot be promoted into a planned write through `plan_patch` or `plan_patch_set`.

## Scope

The current implementation intentionally avoids a heavy parser dependency. It gives the project useful repository intelligence today while leaving room for a later tree-sitter milestone that adds TypeScript, JavaScript, and broader language support.
