import re

from .skills import SKILLS


def _contains(text_lower: str, alias: str) -> bool:
    # word-boundary-ish match that also works for aliases like "c++" or "ci/cd"
    pattern = r"(?<![a-z0-9.])" + re.escape(alias) + r"(?![a-z0-9])"
    return re.search(pattern, text_lower) is not None


def extract_skills(text: str) -> list[str]:
    """Keyword baseline: return canonical skill names found in the text."""
    lower = text.lower()
    found = [name for name, aliases in SKILLS.items() if any(_contains(lower, a) for a in aliases)]
    return sorted(found)
