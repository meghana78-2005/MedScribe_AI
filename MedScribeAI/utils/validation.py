"""Simple input checks for the clinical dictation text."""

import re

MIN_WORDS = 8          # shorter than this is too little to build a useful note
MAX_CHARACTERS = 5000  # keeps requests small and fast

# Simple patterns that suggest personal identifiers. This is a basic safety
# net for a demo, NOT a complete privacy filter.
PII_PATTERNS = {
    "an email address": r"[\w.+-]+@[\w-]+\.[\w.-]+",
    "a phone number": r"(?<!\d)(?:\+?\d{1,3}[\s-]?)?\d{10}(?!\d)|\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b",
    "an ID-like number": r"\b\d{4}\s\d{4}\s\d{4}\b|\b(?:mrn|uhid|aadhaar|ssn)\b",
    "a name label": r"\b(?:patient name|name)\s*:",
}


def find_possible_pii(text: str) -> list[str]:
    """Return a list of the kinds of personal identifiers that look present."""
    return [
        label
        for label, pattern in PII_PATTERNS.items()
        if re.search(pattern, text, flags=re.IGNORECASE)
    ]


def validate_dictation(text: str) -> tuple[bool, str]:
    """Check the dictation before sending it to the LLM.

    Returns:
        (True, "") if the text is acceptable,
        (False, "<friendly message>") otherwise.
    """
    cleaned = (text or "").strip()

    if not cleaned:
        return False, "Please enter some clinical dictation first."

    if len(cleaned.split()) < MIN_WORDS:
        return False, (
            f"The input is too short. Please enter at least {MIN_WORDS} words "
            "so there is enough information to work with."
        )

    if len(cleaned) > MAX_CHARACTERS:
        return False, (
            f"The input is too long. Please keep it under {MAX_CHARACTERS} characters."
        )

    pii_found = find_possible_pii(cleaned)
    if pii_found:
        return False, (
            "The text may contain personal identifiers (" + ", ".join(pii_found) + "). "
            "Please remove them and use synthetic or de-identified text."
        )

    return True, ""
