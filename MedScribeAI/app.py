"""MedScribeAI - AI-assisted clinical documentation (Streamlit interface).

Pages: Dashboard, New Clinical Note, Saved Reports, Session Insights, Safety & Privacy.
Everything is kept in this browser session (st.session_state). Nothing is written to disk.

Main objects kept in session state:
  workspace  the note being worked on: input fingerprint, original text, versions, additions
  reports    notes the user saved (this session only)
  history    short list of notes created this session (for the dashboard)
  stats      counters for the dashboard and Session Insights
"""

import hashlib
from datetime import datetime

import streamlit as st

from prompts.prompts import DEFAULT_STRATEGY, build_prompt, expects_json
from sample_data.sample_cases import EMPTY_CASE, SAMPLES
from utils.case import (
    SEX_OPTIONS, SYMPTOM_OPTIONS, case_content, case_text, compare_information, differential_changes,
    effective_note, lines_to_list, list_to_lines, provided_summary, with_additions,
)
from utils.export import ExportError, report_to_pdf
from utils.formatting import ParseError, parse_json_response
from utils.llm_client import LLMError, generate_text, is_api_key_configured, transcribe_audio
from utils.reports import (
    DISCLAIMER, all_reports_json, auto_title, generate_button_label, input_fingerprint, make_report,
    next_report_id, note_to_json, note_to_text, report_rows, report_status,
)
from utils.ui import (
    bar_rows, bullets, card, card_marker, detected_tiles, empty_state, hero, how_it_works, inject_css, note_list,
    page_header, render_differentials, render_missing_card, render_note, render_safety, render_soap, render_summary,
    section_label, show, side_section, sidebar_brand, stat_card, status_pill, table_card,
)
from utils.validation import validate_additions, validate_dictation

st.set_page_config(page_title="MedScribeAI", page_icon="🩺", layout="wide")
inject_css()
S = st.session_state

PAGES = ["Dashboard", "New Clinical Note", "Saved Reports", "Session Insights", "Safety & Privacy"]
ICONS = {"Dashboard": "🏠", "New Clinical Note": "➕", "Saved Reports": "📋", "Session Insights": "📊", "Safety & Privacy": "🛡️"}
INPUT_MODES = ["⌨️ Type Manually", "🎙️ Voice Input", "📝 Sample Case"]
MANUAL, VOICE, SAMPLE = INPUT_MODES
STRATEGIES = ["Safety-Constrained", "Structured"]
PLACEHOLDER = (
    "Describe the available symptoms, duration, relevant history, medications, examination findings, "
    "and other clinical information.\n\nMissing information will be identified rather than guessed."
)
PARSE_MESSAGE = "The AI reply could not be read as a structured note. Please try again."

# Input widgets: case field -> session-state key
TEXT_KEYS = {
    "age": "f_age", "chief_complaint": "f_complaint", "duration": "f_duration", "other_symptoms": "f_other_symptoms",
    "history": "f_history", "medications": "f_medications", "allergies": "f_allergies",
    "exam": "f_exam", "vitals": "f_vitals", "other": "f_other",
}


def init_state() -> None:
    defaults = {
        "page": "Dashboard", "reports": [], "history": [], "activity": [], "workspace": None, "job": None,
        "gen_message": None, "editing": False, "input_mode": MANUAL, "strategy": DEFAULT_STRATEGY,
        "ws_counter": 0, "dictation": "", "pending_dictation": None, "clear_additions": False,
        "additions_input": "", "report_label": "", "transcribed_hash": None, "f_sex": None,
    }
    for key, value in defaults.items():
        S.setdefault(key, value)
    S.setdefault("stats", {"created": 0, "updated": 0, "checks": 0})
    for key in TEXT_KEYS.values():
        S.setdefault(key, "")
    for name in SYMPTOM_OPTIONS:
        S.setdefault(f"sym_{name}", False)


init_state()


# ---------- reading and filling the input form ----------
def collect_case() -> dict:
    """The input as the user sees it right now."""
    case = {field: S.get(key, "") or "" for field, key in TEXT_KEYS.items()}
    case["sex"] = S.get("f_sex") or ""
    case["symptoms"] = [name for name in SYMPTOM_OPTIONS if S.get(f"sym_{name}")]
    case["dictation"] = S.get("dictation", "")
    return case


def fill_case(case: dict) -> None:
    """Put a sample (or an empty case) into the form widgets."""
    for field, key in TEXT_KEYS.items():
        S[key] = case.get(field, "")
    S["f_sex"] = case.get("sex")
    for name in SYMPTOM_OPTIONS:
        S[f"sym_{name}"] = name in case.get("symptoms", [])
    S["dictation"] = case.get("dictation", "")


def now_text() -> str:
    return datetime.now().strftime("%d %b %Y, %H:%M")


def log_activity(event: str, title: str) -> None:
    S["activity"].insert(0, {"Time": now_text(), "Event": event, "Note": title})
    del S["activity"][50:]


def latest_version() -> dict:
    return S["workspace"]["versions"][-1]


def sync_history(ws: dict) -> None:
    saved = next((r for r in S["reports"] if r["id"] == ws["saved_id"]), None)
    title = saved["title"] if saved else auto_title(effective_note(ws["versions"][-1]))
    entry = next((h for h in S["history"] if h["ws_id"] == ws["id"]), None)
    values = {"title": title, "updates": ws["update_count"], "saved": ws["saved_id"] is not None}
    if entry:
        entry.update(values)
    else:
        S["history"].insert(0, {"ws_id": ws["id"], "created": ws["created"], **values})


# ---------- callbacks (run before the page re-draws) ----------
def reset_workspace() -> None:
    """New Clinical Note / Clear all: empty the input and drop the current note and temporary state.
    Saved reports, statistics and API-key detection are not touched."""
    fill_case(EMPTY_CASE)
    S["sample_choice"] = None
    S["input_mode"] = MANUAL
    S["workspace"] = None
    S["job"] = None
    S["gen_message"] = None
    S["editing"] = False
    S["additions_input"] = ""
    S["pending_dictation"] = None
    S["report_label"] = ""


def go_to(page: str) -> None:
    if page == "New Clinical Note":
        reset_workspace()
    S["page"] = page


def apply_sample() -> None:
    choice = S.get("sample_choice")
    if choice:
        fill_case(SAMPLES[choice])
        S["gen_message"] = None


def start_job(kind: str) -> None:
    S["job"] = kind
    S["gen_message"] = None


def start_edit() -> None:
    note = effective_note(latest_version())
    S["edit_s"], S["edit_o"] = list_to_lines(note["subjective"]), list_to_lines(note["objective"])
    S["edit_a"], S["edit_p"] = note["assessment"], list_to_lines(note["plan"])
    S["editing"] = True


def cancel_edit() -> None:
    S["editing"] = False


def save_edits() -> None:
    version = latest_version()
    version["edited"] = {
        "subjective": lines_to_list(S["edit_s"]), "objective": lines_to_list(S["edit_o"]),
        "assessment": S["edit_a"].strip(), "plan": lines_to_list(S["edit_p"]),
    }
    S["editing"] = False
    sync_history(S["workspace"])
    log_activity("Note edited", auto_title(effective_note(version)))


def restore_ai_version() -> None:
    latest_version()["edited"] = None
    sync_history(S["workspace"])


def build_report(ws: dict, label: str) -> dict:
    note = effective_note(ws["versions"][-1])
    return make_report(ws["saved_id"] or "DRAFT", label, ws["created"], ws["base_text"], note, ws["update_count"], ws["additions"])


def save_workspace() -> None:
    ws = S["workspace"]
    if not ws:
        return
    if ws["saved_id"]:
        report = build_report(ws, S.get("report_label", ""))
        S["reports"] = [report if r["id"] == ws["saved_id"] else r for r in S["reports"]]
        log_activity("Report updated", report["title"])
    else:
        report = build_report(ws, S.get("report_label", ""))
        report["id"] = next_report_id(S["reports"])
        S["reports"].append(report)
        ws["saved_id"] = report["id"]
        log_activity("Report saved", report["title"])
    sync_history(ws)


def delete_report(report_id: str) -> None:
    S["reports"] = [r for r in S["reports"] if r["id"] != report_id]
    ws = S["workspace"]
    if ws and ws["saved_id"] == report_id:
        ws["saved_id"] = None
        sync_history(ws)


def delete_all_reports() -> None:
    S["reports"] = []
    if S["workspace"]:
        S["workspace"]["saved_id"] = None
        sync_history(S["workspace"])


# ---------- the AI jobs ----------
def analyse(text: str) -> dict:
    """Run one analysis. The status box shows the real steps, not a fake animation."""
    with st.status("🔄 Analyzing clinical information...", expanded=True) as status:
        try:
            st.write("✓ Structuring provided information")
            strategy = S["strategy"] if S["strategy"] in STRATEGIES else DEFAULT_STRATEGY
            prompt = build_prompt(strategy, text)
            st.write("⏳ Gemini is preparing the summary, SOAP note, possible differentials and missing-information check...")
            raw = generate_text(prompt, json_output=expects_json(strategy))
            st.write("✓ Response received")
            note = parse_json_response(raw)
            st.write("✓ Response checked and structured")
        except Exception:
            status.update(label="Analysis stopped", state="error", expanded=False)
            raise
        status.update(label="✓ Analysis complete", state="complete", expanded=False)
    return note


def job_analyze(case: dict, fingerprint: str):
    is_valid, text = validate_dictation(case_content(case))
    if not is_valid:
        return ("warning", text, fingerprint)
    base_text = case_text(case)
    try:
        note = analyse(base_text)
    except LLMError as err:
        return ("error", str(err), fingerprint)
    except ParseError:
        return ("warning", PARSE_MESSAGE, fingerprint)
    S["ws_counter"] += 1
    ws = {
        "id": S["ws_counter"], "input_hash": fingerprint, "base_text": base_text, "created": now_text(),
        "versions": [{"note": note, "edited": None, "created": now_text(), "additions": []}],
        "additions": [], "update_count": 0, "saved_id": None,
    }
    S["workspace"], S["editing"] = ws, False
    S["stats"]["created"] += 1
    S["stats"]["checks"] += 1
    sync_history(ws)
    log_activity("Note created", auto_title(note))
    return None


def job_update(fingerprint: str):
    ws = S["workspace"]
    if not ws:
        return None
    extra = S.get("additions_input", "")
    is_valid, text = validate_additions(extra)
    if not is_valid:
        return ("warning", text, fingerprint)
    additions = ws["additions"] + [extra.strip()]
    try:
        note = analyse(with_additions(ws["base_text"], additions))
    except LLMError as err:
        return ("error", str(err), fingerprint)
    except ParseError:
        return ("warning", PARSE_MESSAGE, fingerprint)
    ws["additions"] = additions
    ws["versions"].append({"note": note, "edited": None, "created": now_text(), "additions": list(additions)})
    ws["update_count"] += 1
    S["stats"]["updated"] += 1
    S["stats"]["checks"] += 1
    S["clear_additions"], S["editing"] = True, False
    sync_history(ws)
    log_activity("Note updated", auto_title(note))
    return ("success", "🔄 Note updated using your additional information. The earlier version is kept for comparison.", fingerprint)


def job_transcribe():
    clip = S.get("voice_clip")
    if clip is None:
        return ("warning", "Please record something first.", None)
    audio = clip.getvalue()
    digest = hashlib.sha256(audio).hexdigest()
    if digest == S.get("transcribed_hash"):
        return ("info", "This recording was already transcribed. Record a new one to add more.", None)
    try:
        with st.spinner("Transcribing the recording..."):
            transcript = transcribe_audio(audio, "audio/wav")
    except LLMError as err:
        return ("error", "Transcription failed: " + str(err), None)
    if not transcript.strip():
        return ("warning", "No clear speech was found in the recording.", None)
    S["transcribed_hash"] = digest
    S["pending_dictation"] = (S.get("dictation", "").strip() + "\n" + transcript.strip()).strip()
    return ("success", "Transcript added to the clinical dictation box. Please read it and correct any mistakes before analyzing.", None)


def run_job(kind: str, case: dict, fingerprint: str) -> None:
    message = None
    try:
        if kind == "analyze":
            message = job_analyze(case, fingerprint)
        elif kind == "update":
            message = job_update(fingerprint)
        elif kind == "transcribe":
            message = job_transcribe()
    finally:
        S["job"] = None
    S["gen_message"] = {"kind": message[0], "text": message[1], "fingerprint": message[2]} if message else None
    st.rerun()


# ---------- Page: Dashboard ----------
def dashboard_page() -> None:
    show(hero(
        "MedScribeAI",
        "AI-assisted clinical documentation for structuring clinical dictation into summaries, SOAP notes, "
        "possible differential diagnoses, and missing-information checks.",
        eyebrow="Clinical Documentation Assistant",
        pills=["Summary", "SOAP note", "Possible differentials", "Missing-information check"],
    ))
    stats = S["stats"]
    values = [("Notes Created", stats["created"], "📝"), ("Notes Updated", stats["updated"], "🔄"),
              ("Missing-Information Checks", stats["checks"], "⚠️"), ("Saved Reports", len(S["reports"]), "📋")]
    for column, (label, value, icon) in zip(st.columns(4, gap="medium"), values):
        with column:
            show(stat_card(label, value, "this session", icon))
    st.button("➕ Start a New Clinical Note", type="primary", on_click=go_to, args=("New Clinical Note",))

    show(section_label("Recent Clinical Notes"))
    show(note_list(
        S["history"][:5],
        empty="Notes you create in this session will be listed here. Start with a sample case or type your own clinical information.",
    ))
    st.caption("Session data only. These numbers and notes are kept in memory for this browser session and are cleared when you close or refresh the page.")
    show(how_it_works([
        "Provide clinical information by typing, speaking or loading a synthetic sample.",
        "Analyze it for a summary, SOAP note, possible differentials and missing information.",
        "Review and edit the draft, add missing information and update the note.",
        "Save the report for this session and download it as PDF, text or JSON.",
    ]))


# ---------- Page: New Clinical Note ----------
def voice_panel(busy: bool) -> None:
    st.caption(
        "Records audio in your browser. When you click Transcribe, the recording is sent to Gemini and turned into "
        "text that is added to the dictation box. This is not real-time transcription and it has not been checked "
        "for medical terms, so read and correct the text before analyzing. Use synthetic or de-identified speech only."
    )
    if not hasattr(st, "audio_input"):
        st.info("Voice recording needs a newer Streamlit version. Run: pip install -U streamlit")
        return
    clip = st.audio_input("Record clinical dictation", key="voice_clip", disabled=busy)
    if clip is not None:
        st.button("📝 Transcribe recording", on_click=start_job, args=("transcribe",), disabled=busy)


def guided_fields(busy: bool) -> None:
    with st.expander("➕ Guided clinical information (optional)"):
        st.caption("Fill in only what you have. A field left empty means Not provided, never No.")
        age_col, sex_col = st.columns(2)
        with age_col:
            st.text_input("Age", key="f_age", placeholder="e.g. 34", max_chars=20, disabled=busy)
        with sex_col:
            st.selectbox("Sex", SEX_OPTIONS, index=None, placeholder="Not provided", key="f_sex", disabled=busy)
        complaint_col, duration_col = st.columns(2)
        with complaint_col:
            st.text_input("Chief complaint", key="f_complaint", disabled=busy)
        with duration_col:
            st.text_input("Duration / onset", key="f_duration", disabled=busy)
        st.markdown("**Symptoms** (tick what applies)")
        for index, column in enumerate(st.columns(3)):
            with column:
                for name in SYMPTOM_OPTIONS[index::3]:
                    st.checkbox(name, key=f"sym_{name}", disabled=busy)
        st.text_input("Other symptoms (comma-separated)", key="f_other_symptoms", disabled=busy)
        st.caption("Unticked symptoms are not assumed to be absent.")
        left, right = st.columns(2)
        with left:
            st.text_area("Relevant history", key="f_history", height=80, disabled=busy)
            st.text_area("Allergies", key="f_allergies", height=80, disabled=busy)
            st.text_area("Examination findings", key="f_exam", height=80, disabled=busy)
        with right:
            st.text_area("Current medications", key="f_medications", height=80, disabled=busy)
            st.text_area("Vital signs", key="f_vitals", height=80, disabled=busy)
            st.text_area("Other information", key="f_other", height=80, disabled=busy)


def new_note_page() -> None:
    if S["pending_dictation"] is not None:        # set by the voice transcription job
        S["dictation"], S["pending_dictation"] = S["pending_dictation"], None
    if S["clear_additions"]:                       # set after a note update
        S["additions_input"], S["clear_additions"] = "", False

    page_header("New Clinical Note", "Choose how to provide the clinical information, then analyze it. Fill in as much or as little as you have.", "➕")
    busy = S["job"] is not None
    main, _spacer = st.columns([5, 1])             # keeps the input at a comfortable line length
    with main:
        st.radio("Input method", INPUT_MODES, key="input_mode", horizontal=True, label_visibility="collapsed", disabled=busy)
        with st.container(border=True):
            show(card_marker())
            if S["input_mode"] == SAMPLE:
                st.selectbox(
                    "Synthetic sample case", list(SAMPLES), index=None, placeholder="Choose a sample case...",
                    key="sample_choice", on_change=apply_sample, disabled=busy,
                )
                st.caption("Sample cases are fictional. You can edit any field after loading one.")
            elif S["input_mode"] == VOICE:
                voice_panel(busy)
            guided_fields(busy)
            st.markdown("**Clinical dictation**")
            st.text_area("Clinical dictation", key="dictation", height=240, placeholder=PLACEHOLDER,
                         label_visibility="collapsed", disabled=busy)
            case = collect_case()
            fingerprint = input_fingerprint(case_text(case))
            status = report_status(S["workspace"], fingerprint)
            st.caption(
                f"Provided so far: {provided_summary(case)}. Missing clinical information will be identified rather than guessed. "
                "Use synthetic or de-identified text only. Do not enter personally identifiable patient information."
            )
            analyze_col, clear_col = st.columns([3, 1])
            with analyze_col:
                st.button(generate_button_label(status, S["job"] == "analyze"), type="primary",
                          on_click=start_job, args=("analyze",), disabled=busy)
            with clear_col:
                st.button("Clear all", on_click=reset_workspace, disabled=busy)
            with st.expander("⚙️ Advanced options"):
                st.selectbox("AI prompt style", STRATEGIES, key="strategy", disabled=busy)
                st.caption("Safety-constrained is recommended: it adds the strictest rules against inventing information.")

        job_area = st.container()                   # progress of a running job is shown here

        message = S["gen_message"]
        if message and message["fingerprint"] in (None, fingerprint):
            {"error": st.error, "warning": st.warning, "success": st.success, "info": st.info}[message["kind"]](message["text"])
        elif status == "stale":
            st.info("Clinical information changed. Generate a new clinical note to update the report.")

    # A note is shown only when it was generated from exactly the information on screen.
    if status == "fresh":
        show_workspace()

    # The AI job runs last, after every widget has been drawn, so no typed text can be lost.
    if S["job"]:
        with job_area:
            run_job(S["job"], case, fingerprint)   # ends with st.rerun()


# ---------- the interactive clinical workspace ----------
def show_workspace() -> None:
    ws = S["workspace"]
    version = ws["versions"][-1]
    note = effective_note(version)
    badges = "<span class='badge badge-draft'>AI-generated draft - clinician review required</span>"
    badges += f"<span class='badge badge-info'>Version {len(ws['versions'])}</span>"
    if ws["update_count"]:
        badges += "<span class='badge badge-ok'>🔄 Note Updated</span>"
    if version["edited"]:
        badges += "<span class='badge badge-info'>✏️ Edited by you</span>"
    if ws["saved_id"]:
        badges += f"<span class='badge badge-ok'>Saved as {ws['saved_id']}</span>"
    show(f"<div class='section-head'><span class='section-title'>Clinical Workspace</span>{badges}</div>")

    tabs = st.tabs(["🩺 Clinical Summary", "📋 SOAP Note", "🔍 Possible Differentials", "⚠️ Missing Information", "🛡️ Safety"])
    with tabs[0]:
        render_summary(note)
        compare_section(ws)
    with tabs[1]:
        soap_tab(note, version)
    with tabs[2]:
        render_differentials(note)
    with tabs[3]:
        missing_tab(ws, note)
    with tabs[4]:
        render_safety(note)
    export_section(ws)


def compare_section(ws: dict) -> None:
    if not ws["update_count"]:
        return
    first, last = ws["versions"][0]["note"], ws["versions"][-1]["note"]
    with st.expander("🔄 Compare Updates"):
        st.caption("This compares the information documented in each version. It makes no claim about clinical improvement or worsening.")
        before, after = st.columns(2)
        with before:
            st.markdown("**Initial information**")
            show(detected_tiles(first))
        with after:
            st.markdown("**Updated information**")
            show(detected_tiles(last))
        changes = compare_information(first, last)
        st.markdown("**Newly documented**")
        if changes:
            show(bullets([f"{c['kind']} - {c['label']}: {c['new']}" + (f" (was: {c['old']})" if c["old"] else "") for c in changes]))
        else:
            st.caption("No new details were detected in the structured information.")
        st.markdown("**Information you added**")
        show(bullets(ws["additions"]))
        added, removed = differential_changes(first, last)
        if added or removed:
            st.markdown("**Possible differentials listed**")
            if added:
                show(f"<p>Newly listed: {', '.join(a.replace('<', '') for a in added)}</p>")
            if removed:
                show(f"<p>No longer listed: {', '.join(r.replace('<', '') for r in removed)}</p>")


def soap_tab(note: dict, version: dict) -> None:
    if S["editing"]:
        st.caption("You are editing the draft. Your changes are saved separately from the AI version and are used in exports. Editing does not call the AI.")
        with st.form("edit_form"):
            st.text_area("Subjective (one item per line)", key="edit_s", height=130)
            st.text_area("Objective (one item per line)", key="edit_o", height=110)
            st.text_area("Assessment", key="edit_a", height=100)
            st.text_area("Plan - considerations for clinician review (one item per line)", key="edit_p", height=110)
            save_col, cancel_col = st.columns(2)
            with save_col:
                st.form_submit_button("💾 Save Changes", type="primary", on_click=save_edits)
            with cancel_col:
                st.form_submit_button("Cancel", on_click=cancel_edit)
        return
    render_soap(note)
    edit_col, restore_col = st.columns(2)
    with edit_col:
        st.button("✏️ Edit Note", on_click=start_edit)
    if version["edited"]:
        with restore_col:
            st.button("↩️ Restore AI version", on_click=restore_ai_version)
        st.caption("Showing your edited version. The original AI version can be restored.")


def missing_tab(ws: dict, note: dict) -> None:
    render_missing_card(note)
    st.markdown("**➕ Add Missing Information**")
    st.caption("Type anything you can add, for example duration, temperature, severity, history or examination findings. It is combined with your original information.")
    if ws["additions"]:
        st.markdown("Added so far:")
        show(bullets(ws["additions"]))
    busy = S["job"] is not None
    st.text_area("Additional information", key="additions_input", height=110, disabled=busy,
                 placeholder="e.g. Cough for 3 days, temperature 38.5 C, no chest pain, no known allergies")
    st.button("🔄 Update Clinical Note", type="primary", on_click=start_job, args=("update",), disabled=busy)


def export_section(ws: dict) -> None:
    st.markdown("---")
    st.markdown("**Save and export**")
    label = st.text_input("Report label (optional - do not use patient names)", key="report_label", max_chars=60)
    report = build_report(ws, label)
    save_col, pdf_col, text_col, json_col = st.columns(4)
    with save_col:
        st.button("💾 Update saved report" if ws["saved_id"] else "💾 Save to Reports", type="primary", on_click=save_workspace)
    with pdf_col:
        try:
            st.download_button("📄 Download Clinical Report", report_to_pdf(report), file_name=f"MedScribeAI_{report['id']}.pdf", mime="application/pdf")
        except ExportError as err:
            st.warning(str(err))
    with text_col:
        st.download_button("Download as text", note_to_text(report), file_name=f"MedScribeAI_{report['id']}.txt", mime="text/plain")
    with json_col:
        st.download_button("Download as JSON", note_to_json(report), file_name=f"MedScribeAI_{report['id']}.json", mime="application/json")
    with st.expander("Copy report text"):
        st.caption("Use the copy icon at the top right of the box.")
        st.code(note_to_text(report), language=None)


# ---------- Page: Saved Reports ----------
def reports_page() -> None:
    page_header("Saved Reports", "Reports are stored only for this session. They are kept in memory and disappear when you close or refresh the page, so download anything you want to keep.", "📋")
    reports = S["reports"]
    if not reports:
        show(empty_state("📋", "No reports yet", "Analyze a note in New Clinical Note and choose Save to Reports. It will appear here."))
        return

    count_col, all_col, delete_col = st.columns(3, vertical_alignment="bottom")
    with count_col:
        st.metric("Reports saved", len(reports))
    with all_col:
        st.download_button("Download all (JSON)", all_reports_json(reports), file_name="MedScribeAI_reports.json", mime="application/json")
    with delete_col:
        with st.popover("Delete all"):
            st.warning("This removes every saved report from this session.")
            st.button("Yes, delete all reports", on_click=delete_all_reports)

    show(table_card(report_rows(reports)))
    titles = {r["id"]: r["title"] for r in reports}
    selected_id = st.selectbox("Open a report", list(titles), format_func=lambda rid: f"{rid} - {titles[rid]}")
    report = next((r for r in reports if r["id"] == selected_id), None)
    if report is None:
        return
    show(f"<div class='section-head'><span class='section-title'>{report['id']}</span>"
         f"<span class='badge badge-draft'>AI-generated draft</span>"
         f"<span class='badge badge-info'>{report.get('update_count', 0)} update(s)</span></div>")
    st.caption(f"{report['title']} - created {report['created']}")
    render_note(report["note"])
    with st.expander("Original clinical input"):
        st.text(report["dictation"])
    if report.get("additions"):
        with st.expander("Additional information added later"):
            show(bullets(report["additions"]))
    pdf_col, text_col, json_col, del_col = st.columns(4)
    with pdf_col:
        try:
            st.download_button("📄 Download Clinical Report", report_to_pdf(report), file_name=f"MedScribeAI_{report['id']}.pdf", mime="application/pdf", key=f"pdf_{report['id']}")
        except ExportError as err:
            st.warning(str(err))
    with text_col:
        st.download_button("Download as text", note_to_text(report), file_name=f"MedScribeAI_{report['id']}.txt", mime="text/plain", key=f"txt_{report['id']}")
    with json_col:
        st.download_button("Download as JSON", note_to_json(report), file_name=f"MedScribeAI_{report['id']}.json", mime="application/json", key=f"json_{report['id']}")
    with del_col:
        st.button("Delete this report", on_click=delete_report, args=(report["id"],), key=f"del_{report['id']}")


# ---------- Page: Session Insights ----------
def insights_page() -> None:
    page_header("Session Insights", "A simple count of your activity in this session.", "📊")
    stats = S["stats"]
    items = [("Notes Created", stats["created"]), ("Notes Updated", stats["updated"]),
             ("Missing-Information Checks", stats["checks"]), ("Reports Saved", len(S["reports"]))]
    show(section_label("Current Session Activity"))
    icons = ["📝", "🔄", "⚠️", "📋"]
    for column, (label, value), icon in zip(st.columns(4), items, icons):
        with column:
            show(stat_card(label, value, icon=icon))
    show(bar_rows(items))
    st.caption("Every analysis includes a missing-information check, so that count equals notes created plus notes updated. Saved reports is the number currently saved.")
    show(section_label("Recent Activity"))
    show(table_card(S["activity"][:15], empty="Your actions in this session will be listed here."))
    st.caption("These numbers describe your use of the app in this session only. They are not medical statistics and are cleared when you close or refresh the page.")


# ---------- Page: Safety & Privacy ----------
def safety_page() -> None:
    page_header("Safety & Privacy", "How MedScribeAI should and should not be used.", "🛡️")
    left, right = st.columns(2, gap="medium")
    with left:
        show(card("What MedScribeAI is", "<p>An AI clinical documentation assistant. It organises clinical information into a "
                  "structured note and lists possible considerations for a clinician to review. It is an educational and "
                  "documentation-assistance prototype.</p>"))
        show(card("Responsible use", bullets([
            "MedScribeAI does not intentionally fill in missing clinical information. Information not provided should be identified as missing rather than assumed.",
            "Treat every note as a draft and check it against the original information.",
            "Differential diagnoses are possibilities, not confirmed diagnoses.",
            "The plan contains considerations for clinician review, not treatment orders.",
            "It does not replace professional clinical judgement and has not been clinically validated.",
        ])))
    with right:
        show(card("Your data", bullets([
            "Do not enter unnecessary real patient identifying information. Use synthetic or de-identified text.",
            "The text you enter is sent to Google's Gemini service to generate the note. Voice recordings are also sent to Gemini when you transcribe them. Check Google's current terms for how API data is handled.",
            "MedScribeAI does not write your text to disk or a database.",
            "Reports are stored only for this session and disappear when you close or refresh the page.",
            "The API key is read from a private .env file and is never shown in the app.",
        ])))
        show(card("Known limits", bullets([
            "AI output can change between runs and can contain errors or omissions.",
            "Voice transcription is not real-time and has not been checked for medical terms.",
            "The personal-identifier check only catches obvious patterns such as emails and phone numbers.",
            "English text only.",
        ])))
    st.caption(DISCLAIMER)


# ---------- Sidebar and routing ----------
with st.sidebar:
    show(sidebar_brand())
    show(side_section("Navigate"))
    for page_name in PAGES:
        st.button(f"{ICONS[page_name]} {page_name}", key=f"nav_{page_name}", on_click=go_to, args=(page_name,),
                  type="primary" if S["page"] == page_name else "secondary")
    st.divider()
    show(f"<div class='side-note'>This session: {S['stats']['created']} note(s) created, {len(S['reports'])} report(s) saved</div>")
    if is_api_key_configured():
        show(status_pill("API key detected", ok=True))
    else:
        show(status_pill("API key missing. Add GEMINI_API_KEY to your .env file.", ok=False))
    show("<div class='side-note'>Educational prototype. Not a substitute for professional medical evaluation.</div>")

{"Dashboard": dashboard_page, "New Clinical Note": new_note_page, "Saved Reports": reports_page,
 "Session Insights": insights_page, "Safety & Privacy": safety_page}[S["page"]]()
