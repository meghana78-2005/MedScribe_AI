"""Building the clinical input from the guided fields and the free-text dictation,
and comparing two versions of a note. No Streamlit code here, so it is easy to test.

Rule used everywhere: an empty field means "Not provided". It never means "No".
"""

import re

from prompts.prompts import DETECTED_KEYS, DETECTED_LABELS

SYMPTOM_OPTIONS = [
    "Fever", "Cough", "Headache", "Fatigue", "Pain",
    "Nausea", "Vomiting", "Shortness of breath", "Dizziness",
]
SEX_OPTIONS = ["Female", "Male", "Other"]

# (case key, label used in the text sent to the AI). "symptoms" is built separately.
TEXT_FIELDS = [
    ("age", "Age"),
    ("sex", "Sex"),
    ("chief_complaint", "Chief complaint"),
    ("duration", "Duration / onset"),
    ("symptoms", "Symptoms reported"),
    ("history", "Relevant history"),
    ("medications", "Current medications"),
    ("allergies", "Allergies"),
    ("exam", "Examination findings"),
    ("vitals", "Vital signs"),
    ("other", "Other information"),
]


def symptom_list(case: dict) -> list[str]:
    """Ticked symptoms plus any typed ones, without duplicates."""
    typed = [part.strip() for part in re.split(r"[,;\n]", case.get("other_symptoms") or "")]
    seen, result = set(), []
    for name in list(case.get("symptoms") or []) + typed:
        if name and name.lower() not in seen:
            seen.add(name.lower())
            result.append(name)
    return result


def _value(case: dict, key: str) -> str:
    if key == "symptoms":
        return ", ".join(symptom_list(case))
    return " ".join(str(case.get(key) or "").split())


def case_content(case: dict) -> str:
    """Only what the user provided (no labels). Used for the length and privacy checks."""
    parts = [_value(case, key) for key, _ in TEXT_FIELDS]
    parts.append((case.get("dictation") or "").strip())
    return " ".join(part for part in parts if part)


def has_structured_input(case: dict) -> bool:
    return any(_value(case, key) for key, _ in TEXT_FIELDS)


def case_text(case: dict) -> str:
    """The text sent to the AI. Plain dictation stays exactly as typed."""
    dictation = (case.get("dictation") or "").strip()
    lines = [f"{label}: {_value(case, key)}" for key, label in TEXT_FIELDS if _value(case, key)]
    if not lines:
        return dictation
    text = "\n".join(lines)
    return f"{text}\n\nClinical dictation:\n{dictation}" if dictation else text


def provided_summary(case: dict) -> str:
    """One short line telling the user what has been provided so far."""
    labels = {"age": "age", "sex": "sex", "chief_complaint": "chief complaint", "duration": "duration",
              "history": "history", "medications": "medications", "allergies": "allergies",
              "exam": "examination findings", "vitals": "vital signs", "other": "other information"}
    items = [name for key, name in labels.items() if _value(case, key)]
    symptoms = symptom_list(case)
    if symptoms:
        items.insert(0, f"{len(symptoms)} symptom{'s' if len(symptoms) != 1 else ''}")
    words = len((case.get("dictation") or "").split())
    if words:
        items.append(f"dictation ({words} words)")
    return ", ".join(items) if items else "nothing yet"


def with_additions(base_text: str, additions: list[str]) -> str:
    """Original text plus everything the user added later."""
    cleaned = [" ".join(a.split()) for a in additions if a and a.strip()]
    if not cleaned:
        return base_text
    extra = "\n".join(f"- {item}" for item in cleaned)
    return f"{base_text}\n\nAdditional information added later by the user:\n{extra}"


# ---------- editing ----------
def lines_to_list(text: str) -> list[str]:
    """Text area content -> list (one item per line, bullets removed)."""
    return [re.sub(r"^[\-\u2022*]\s*", "", line.strip()) for line in (text or "").splitlines() if line.strip()]


def list_to_lines(items: list[str]) -> str:
    return "\n".join(items)


def effective_note(version: dict) -> dict:
    """The note to show and export: the AI version, with the user's edits applied on top."""
    note = dict(version["note"])
    edited = version.get("edited")
    if edited:
        note.update({key: edited[key] for key in ("subjective", "objective", "assessment", "plan") if key in edited})
    return note


# ---------- comparing versions ----------
def is_provided(value: str) -> bool:
    text = (value or "").strip().lower()
    return bool(text) and not text.startswith("not provided")


def compare_information(old_note: dict, new_note: dict) -> list[dict]:
    """What information was newly added or changed between two versions (documentation only)."""
    changes = []
    for key in DETECTED_KEYS:
        old = (old_note.get("information_detected") or {}).get(key, "Not provided")
        new = (new_note.get("information_detected") or {}).get(key, "Not provided")
        if is_provided(new) and not is_provided(old):
            changes.append({"kind": "Added", "label": DETECTED_LABELS[key], "old": "", "new": new})
        elif is_provided(new) and is_provided(old) and " ".join(new.split()).lower() != " ".join(old.split()).lower():
            changes.append({"kind": "Updated", "label": DETECTED_LABELS[key], "old": old, "new": new})
    return changes


def differential_changes(old_note: dict, new_note: dict) -> tuple[list[str], list[str]]:
    """Possible conditions listed only in the new version, and only in the old version."""
    names = lambda note: [row["condition"] for row in note.get("differential_diagnosis", [])]
    old_names, new_names = names(old_note), names(new_note)
    lower_old, lower_new = {n.lower() for n in old_names}, {n.lower() for n in new_names}
    return ([n for n in new_names if n.lower() not in lower_old],
            [n for n in old_names if n.lower() not in lower_new])
