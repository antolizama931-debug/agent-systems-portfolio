import re


def slugify(value: str) -> str:
    """Convert a title into a URL slug."""
    normalized = value.strip().lower().replace(" ", "-")
    return re.sub(r"[^a-z0-9-]", "", normalized)

