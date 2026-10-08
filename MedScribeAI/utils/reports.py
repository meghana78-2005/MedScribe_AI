"""Helpers for saving (in this browser session only) and exporting clinical notes.

Nothing here writes to disk. A "report" is a plain dict kept in st.session_state;
the user downloads it as text or JSON if they want to keep it.
"""

import json

DISCLAIMER = (
    "AI-generated draft for documentation support only. It is not a medical "
    "record or a diagnosis. Review and verify before any clinical use."
)


def next_report_id(reports: list[dict]) -> str:
    """Return the next id (R-001, R-002, ...) even after some reports were deleted."""
    numbers = [int(r["id"].split("-")[1]) for r in reports if r["id"].startswith("R-")]
    return f"R-{max(numbers, default=0) + 1:03d}"


def _auto_title(note: dict) -> str:
    words = str(note.get("clinical_summary", "")).split()
    if not words:
        return "Untitled note"
    return " ".join(words[:8]) + ("..." if len(words) > 8 else "")


def make_report(report_id: str, label: str, created: str, dictation: str, note: dict) -> dict:
    """Bundle a generated note with its metadata."""
    return {
        "id": report_id,
        "title": (label or "").strip() or _auto_title(note),
        "created": created,
        "dictation": dictation,
        "note": note,
    }


def note_to_text(report: dict) -> str:
    """Readable plain-text version of a report (for download)."""
    note = report["note"]
    bullets = lambda items: "\n".join(f"- {item}" for item in items) or "- Not provided."
    ddx_lines = []
    for number, row in enumerate(note["differential_diagnosis"], start=1):
        ddx_lines.append(
            f"{number}. {row['condition']}\n"
            f"   Supporting information: {row['supporting_information']}\n"
            f"   Missing / helpful information: {row['missing_helpful_information']}"
        )
    ddx = "\n".join(ddx_lines) or "Not enough information to suggest differential diagnoses."
    return (
        "MedScribeAI - Clinical Note (AI-generated draft)\n"
        f"Report: {report['id']}\nTitle: {report['title']}\nCreated: {report['created']}\n\n"
        f"CLINICAL SUMMARY\n{note['clinical_summary']}\n\n"
        f"S - SUBJECTIVE\n{bullets(note['subjective'])}\n\n"
        f"O - OBJECTIVE\n{bullets(note['objective'])}\n\n"
        f"A - ASSESSMENT\n{note['assessment']}\n\n"
        f"P - PLAN (considerations for clinician review)\n{bullets(note['plan'])}\n\n"
        f"DIFFERENTIAL DIAGNOSIS (possibilities, not confirmed diagnoses)\n{ddx}\n\n"
        f"INFORMATION THAT MAY NEED CLARIFICATION\n{bullets(note['information_needing_clarification'])}\n\n"
        f"SAFETY NOTE\n{note['safety_note']}\n\n"
        f"ORIGINAL DICTATION\n{report['dictation']}\n\n"
        f"{DISCLAIMER}\n"
    )


def note_to_json(report: dict) -> str:
    """JSON version of one report (for download)."""
    return json.dumps({**report, "disclaimer": DISCLAIMER}, indent=2, ensure_ascii=False)


def all_reports_json(reports: list[dict]) -> str:
    """JSON file containing every saved report."""
    return json.dumps({"disclaimer": DISCLAIMER, "reports": reports}, indent=2, ensure_ascii=False)


def report_rows(reports: list[dict]) -> list[dict]:
    """Rows for the reports table."""
    return [
        {
            "ID": r["id"],
            "Title": r["title"],
            "Created": r["created"],
            "Differentials": len(r["note"]["differential_diagnosis"]),
        }
        for r in reports
    ]
