from pathlib import Path

PRIVATE_FILE_NAMES = frozenset({
    ".env", ".npmrc", ".pypirc", ".netrc", "id_rsa", "id_ed25519",
})
PRIVATE_FILE_SUFFIXES = frozenset({".pem", ".p12", ".pfx"})
PUBLIC_ENV_TEMPLATES = frozenset({".env.example", ".env.sample", ".env.template"})


def is_private_path(path: str | Path) -> bool:
    candidate = Path(path)
    name = candidate.name.lower()
    if name in PRIVATE_FILE_NAMES:
        return True
    if name.startswith(".env.") and name not in PUBLIC_ENV_TEMPLATES:
        return True
    return candidate.suffix.lower() in PRIVATE_FILE_SUFFIXES
