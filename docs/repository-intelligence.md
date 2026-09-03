# Repository Intelligence

TermAgent includes a lightweight repository-intelligence layer for Python, JavaScript, and TypeScript projects. Python files are indexed with the standard library `ast` module. JavaScript and TypeScript files use a conservative scanner for common function, class, import, and reference patterns.

## Tools

- `code_map`: lists classes, functions, methods, imports, languages, and Python parse errors
- `find_references`: lists name references for a requested symbol across Python, JavaScript, and TypeScript files

Example:

```bash
termagent tools --repo .
```

Live providers can call these tools through the same structured tool interface as search, file reads, patch planning, and shell execution.

## Patch Safety

Patch planning validates Python syntax for `.py` files before approving a plan. This means malformed Python cannot be promoted into a planned write through `plan_patch` or `plan_patch_set`.

## Scope

The current implementation intentionally avoids a heavy parser dependency. It gives the agent useful cross-language symbol search today while leaving room for a later tree-sitter milestone with full syntax trees, richer call graphs, and broader language support.
