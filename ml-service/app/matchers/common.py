def numbered_lines(resume_text: str) -> dict[int, str]:
    """1-based line numbers of the ORIGINAL text (same numbering for every matcher); blank lines skipped."""
    return {i: ln.strip() for i, ln in enumerate(resume_text.splitlines(), 1) if ln.strip()}
