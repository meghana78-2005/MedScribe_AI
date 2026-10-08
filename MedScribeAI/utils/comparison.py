"""Runs all five prompt strategies on the same dictation and gathers simple checks.

The checks are only *observations* (word count, parse success, number of
differentials, drug names added by the model). They are NOT accuracy scores and NOT clinical
validation. Judging quality is done by reading the outputs with the rubric.
"""

import re

from prompts.prompts import STRATEGY_INFO, build_prompt, expects_json
from utils.formatting import ParseError, parse_json_response
from utils.llm_client import LLMError, generate_text

# Small fixed word list used only to *flag* drug names in the output.
# It is not complete; it is a simple demonstration check.
COMMON_DRUGS = [
    "acetaminophen", "paracetamol", "ibuprofen", "aspirin", "naproxen",
    "albuterol", "salbutamol", "amoxicillin", "azithromycin", "antibiotics",
    "sumatriptan", "omeprazole", "pantoprazole", "prednisone", "diclofenac",
]


def find_drug_names(text: str) -> list[str]:
    """Return which words from COMMON_DRUGS appear in the text."""
    lowered = text.lower()
    return [drug for drug in COMMON_DRUGS if re.search(rf"\b{drug}\b", lowered)]


def quick_checks(strategy: str, text: str, dictation: str) -> dict[str, str]:
    """Simple, transparent observations about one strategy's output."""
    row = {"Strategy": strategy, "Words": str(len(text.split()))}

    if expects_json(strategy):
        try:
            note = parse_json_response(text)
            row["Format"] = "JSON (parsed OK)"
            row["Differentials listed"] = str(len(note["differential_diagnosis"]))
        except ParseError:
            row["Format"] = "JSON (could not parse)"
            row["Differentials listed"] = "-"
    else:
        row["Format"] = "Free text"
        row["Differentials listed"] = "not counted"

    # Only count drugs the model ADDED: drugs already named in the dictation are fine.
    already_in_dictation = set(find_drug_names(dictation))
    added = [d for d in find_drug_names(text) if d not in already_in_dictation]
    row["Drug names added by model"] = ", ".join(added) or "None"
    return row


def run_all_strategies(dictation: str, on_progress=None) -> dict[str, dict]:
    """Call Gemini once per strategy (one after another).

    Returns {strategy: {"prompt": ..., "text": ... or None, "error": ... or None}}.
    A failure in one strategy does not stop the others.
    """
    results = {}
    names = list(STRATEGY_INFO.keys())
    for index, name in enumerate(names):
        if on_progress:
            on_progress(index, len(names), name)
        prompt = build_prompt(name, dictation)
        try:
            text = generate_text(prompt, json_output=expects_json(name))
            results[name] = {"prompt": prompt, "text": text, "error": None}
        except LLMError as err:
            results[name] = {"prompt": prompt, "text": None, "error": str(err)}
    return results
