"""Turns the model's JSON reply into a checked Python dict and shows it nicely.

parse_json_response() -> reads and validates the JSON text
render_soap_note()    -> draws the SOAP note, table and safety text in Streamlit
"""

import json

import streamlit as st

from prompts.prompts import NOT_PROVIDED

REQUIRED_KEYS = [
    "clinical_summary", "subjective", "objective", "assessment", "plan",
    "differential_diagnosis", "information_needing_clarification", "safety_note",
]
DDX_KEYS = ["condition", "supporting_information", "missing_helpful_information"]


class ParseError(Exception):
    """The model reply was not valid or complete JSON."""


def _as_list(value) -> list[str]:
    """Make sure a field is a list of strings (the model sometimes sends one string)."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    return [str(item) for item in value]


def parse_json_response(text: str) -> dict:
    """Convert the model's reply into a validated dict, or raise ParseError."""
    cleaned = text.strip()

    # Remove ```json ... ``` fences if the model added them anyway.
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        # Last attempt: keep only the part between the first { and the last }.
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1 or end <= start:
            raise ParseError("The reply did not contain JSON.")
        try:
            data = json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError as err:
            raise ParseError("The reply contained broken JSON.") from err

    if not isinstance(data, dict):
        raise ParseError("The reply JSON was not an object.")

    missing = [key for key in REQUIRED_KEYS if key not in data]
    if missing:
        raise ParseError("The reply is missing fields: " + ", ".join(missing))

    # Normalise the fields so the display code can rely on their types.
    for key in ("subjective", "objective", "plan", "information_needing_clarification"):
        data[key] = _as_list(data[key])
    ddx = data["differential_diagnosis"]
    data["differential_diagnosis"] = [
        {k: str(item.get(k, "Not stated")) for k in DDX_KEYS}
        for item in (ddx if isinstance(ddx, list) else [])
        if isinstance(item, dict)
    ]
    return data


def _safe(text: str) -> str:
    """Stop Streamlit from treating $...$ as math."""
    return str(text).replace("$", "\\$")


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {_safe(item)}" for item in items)


def render_soap_note(note: dict) -> None:
    """Show the parsed note in the Streamlit page."""
    st.markdown("### Clinical Summary")
    st.write(_safe(note["clinical_summary"]))

    st.markdown("### S — Subjective")
    st.markdown(_bullets(note["subjective"]) or NOT_PROVIDED)

    st.markdown("### O — Objective")
    st.markdown(_bullets(note["objective"]) or NOT_PROVIDED)

    st.markdown("### A — Assessment")
    st.write(_safe(note["assessment"]))

    st.markdown("### P — Plan (considerations for clinician review)")
    st.markdown(_bullets(note["plan"]) or "No plan considerations provided.")

    st.markdown("### Differential Diagnosis (possibilities, not confirmed diagnoses)")
    if note["differential_diagnosis"]:
        st.table(
            [
                {
                    "Possible Condition": _safe(row["condition"]),
                    "Supporting Information": _safe(row["supporting_information"]),
                    "Missing / Helpful Information": _safe(row["missing_helpful_information"]),
                }
                for row in note["differential_diagnosis"]
            ]
        )
    else:
        st.info("Not enough information in the dictation to suggest differential diagnoses.")

    st.markdown("### Information That May Need Clarification")
    st.markdown(_bullets(note["information_needing_clarification"]) or "None identified.")

    st.warning(_safe(note["safety_note"]))
