"""MedScribeAI - AI-assisted clinical documentation (Streamlit interface).

Pages: New Note, Saved Reports, Safety & Privacy.
Reports are kept in this browser session only (st.session_state); nothing is written to disk.
"""

from datetime import datetime

import streamlit as st

from prompts.prompts import DEFAULT_STRATEGY, build_prompt, expects_json
from sample_data.sample_cases import SAMPLE_CASES
from utils.formatting import ParseError, parse_json_response
from utils.llm_client import LLMError, generate_text, is_api_key_configured
from utils.reports import (
    DISCLAIMER, all_reports_json, make_report, next_report_id,
    note_to_json, note_to_text, report_rows,
)
from utils.ui import bullets, card, inject_css, page_header, render_note
from utils.validation import validate_dictation

st.set_page_config(page_title="MedScribeAI", page_icon="🩺", layout="wide")
inject_css()

st.session_state.setdefault("reports", [])
st.session_state.setdefault("current", None)   # the note on screen: {note, dictation, created, saved_id}
st.session_state.setdefault("dictation", "")


# ---------- Button callbacks (run before the page re-draws) ----------
def load_sample() -> None:
    choice = st.session_state.get("sample_choice")
    if choice:
        st.session_state["dictation"] = SAMPLE_CASES[choice]


def clear_input() -> None:
    st.session_state["dictation"] = ""
    st.session_state["sample_choice"] = None
    st.session_state["current"] = None
    st.session_state["report_label"] = ""


def save_current() -> None:
    current = st.session_state["current"]
    if current and current["saved_id"] is None:
        report = make_report(
            next_report_id(st.session_state["reports"]),
            st.session_state.get("report_label", ""),
            current["created"], current["dictation"], current["note"],
        )
        st.session_state["reports"].append(report)
        current["saved_id"] = report["id"]


def delete_report(report_id: str) -> None:
    st.session_state["reports"] = [r for r in st.session_state["reports"] if r["id"] != report_id]


def delete_all_reports() -> None:
    st.session_state["reports"] = []


# ---------- Page: New Note ----------
def new_note_page() -> None:
    page_header(
        "New Clinical Note",
        "Dictate or paste clinical text and get a structured SOAP note with a cautious differential diagnosis.",
    )
    left, right = st.columns([3, 2], gap="large")
    with left:
        with st.container(border=True):
            st.markdown("**Clinical dictation**")
            pick_col, clear_col = st.columns([3, 1], vertical_alignment="bottom")
            with pick_col:
                st.selectbox(
                    "Load a synthetic sample case", list(SAMPLE_CASES), index=None,
                    placeholder="Choose a sample case...", key="sample_choice", on_change=load_sample,
                )
            with clear_col:
                st.button("Clear", on_click=clear_input)
            dictation = st.text_area(
                "Clinical dictation", key="dictation", height=260,
                placeholder="Paste or type synthetic clinical dictation here...",
                label_visibility="collapsed",
            )
            st.caption(
                f"{len(dictation.split())} words. Use synthetic or de-identified text only. "
                "Do not enter personally identifiable patient information."
            )
            generate = st.button("Generate Clinical Note", type="primary")
    with right:
        tips = bullets([
            "Age and sex",
            "Main symptoms and how long they have lasted",
            "Relevant history, medications and allergies",
            "Vital signs and examination findings",
            "Any tests or imaging results",
        ])
        st.markdown(
            card("What to include", tips + "<p class='muted'>Anything you leave out is reported as missing information, not guessed.</p>"),
            unsafe_allow_html=True,
        )
        st.markdown(
            card("What you will get", bullets([
                "Clinical summary", "SOAP note", "Possible differential diagnoses",
                "Information that may need clarification", "Save and download options",
            ])),
            unsafe_allow_html=True,
        )

    if generate:
        is_valid, message = validate_dictation(dictation)
        if not is_valid:
            st.warning(message)
        else:
            try:
                with st.spinner("Analysing the dictation..."):
                    raw = generate_text(build_prompt(DEFAULT_STRATEGY, dictation), json_output=expects_json(DEFAULT_STRATEGY))
                    note = parse_json_response(raw)
            except LLMError as err:
                st.error(str(err))
            except ParseError:
                st.warning("The AI reply could not be read as a structured note. Please click Generate again.")
            else:
                st.session_state["current"] = {
                    "note": note, "dictation": dictation.strip(),
                    "created": datetime.now().strftime("%d %b %Y, %H:%M"), "saved_id": None,
                }
                st.session_state["report_label"] = ""

    if st.session_state["current"]:
        show_current_note()


def show_current_note() -> None:
    current = st.session_state["current"]
    st.markdown(
        "<div class='section-head'><span class='section-title'>Generated note</span>"
        "<span class='badge badge-draft'>AI-generated draft - clinician review required</span></div>",
        unsafe_allow_html=True,
    )
    render_note(current["note"])

    st.markdown("**Save or export**")
    st.text_input("Report label (optional - do not use patient names)", key="report_label", max_chars=60)
    report = make_report(
        current["saved_id"] or "DRAFT", st.session_state.get("report_label", ""),
        current["created"], current["dictation"], current["note"],
    )
    save_col, text_col, json_col = st.columns(3)
    with save_col:
        if current["saved_id"]:
            st.success(f"Saved as {current['saved_id']} (see Saved Reports)")
        else:
            st.button("Save to Reports", type="primary", on_click=save_current)
    with text_col:
        st.download_button("Download as text", note_to_text(report), file_name=f"MedScribeAI_{report['id']}.txt", mime="text/plain")
    with json_col:
        st.download_button("Download as JSON", note_to_json(report), file_name=f"MedScribeAI_{report['id']}.json", mime="application/json")


# ---------- Page: Saved Reports ----------
def reports_page() -> None:
    page_header(
        "Saved Reports",
        "Reports saved in this browser session. They are kept in memory only and disappear when you "
        "close or refresh the page, so download anything you want to keep.",
    )
    reports = st.session_state["reports"]
    if not reports:
        st.markdown(
            card("No reports yet", "<p class='muted'>Generate a note in <strong>New Note</strong> and choose "
                 "<strong>Save to Reports</strong>. It will appear here.</p>"),
            unsafe_allow_html=True,
        )
        return

    count_col, all_col, delete_col = st.columns([1, 1, 1], vertical_alignment="bottom")
    with count_col:
        st.metric("Reports saved", len(reports))
    with all_col:
        st.download_button("Download all (JSON)", all_reports_json(reports), file_name="MedScribeAI_reports.json", mime="application/json")
    with delete_col:
        with st.popover("Delete all"):
            st.warning("This removes every saved report from this session.")
            st.button("Yes, delete all reports", on_click=delete_all_reports)

    st.table(report_rows(reports))

    titles = {r["id"]: r["title"] for r in reports}
    selected_id = st.selectbox("Open a report", list(titles), format_func=lambda rid: f"{rid} - {titles[rid]}")
    report = next((r for r in reports if r["id"] == selected_id), None)
    if report is None:
        return
    st.markdown(
        f"<div class='section-head'><span class='section-title'>{report['id']}</span>"
        f"<span class='badge badge-draft'>AI-generated draft</span></div>",
        unsafe_allow_html=True,
    )
    st.caption(f"{report['title']} - created {report['created']}")
    render_note(report["note"])
    with st.expander("Original dictation"):
        st.text(report["dictation"])
    text_col, json_col, del_col = st.columns(3)
    with text_col:
        st.download_button("Download as text", note_to_text(report), file_name=f"MedScribeAI_{report['id']}.txt", mime="text/plain", key=f"txt_{report['id']}")
    with json_col:
        st.download_button("Download as JSON", note_to_json(report), file_name=f"MedScribeAI_{report['id']}.json", mime="application/json", key=f"json_{report['id']}")
    with del_col:
        st.button("Delete this report", on_click=delete_report, args=(report["id"],), key=f"del_{report['id']}")


# ---------- Page: Safety & Privacy ----------
def safety_page() -> None:
    page_header("Safety & Privacy", "How MedScribeAI should and should not be used.")
    left, right = st.columns(2, gap="medium")
    with left:
        st.markdown(card("What MedScribeAI is", "<p>An AI clinical documentation assistant. It organises clinical "
                         "dictation into a structured note and lists possible considerations for a clinician to review. "
                         "It is an educational and documentation prototype.</p>"), unsafe_allow_html=True)
        st.markdown(card("Responsible use", bullets([
            "Treat every note as a draft and check it against the original dictation.",
            "Differential diagnoses are possibilities, not confirmed diagnoses.",
            "The plan contains considerations for clinician review, not treatment orders.",
            "Do not rely on the output instead of a professional medical evaluation.",
        ])), unsafe_allow_html=True)
    with right:
        st.markdown(card("Your data", bullets([
            "Use synthetic or de-identified text only. Do not enter personally identifiable patient information.",
            "The text you enter is sent to Google's Gemini service to generate the note. Check Google's current terms for how API data is handled.",
            "MedScribeAI does not write your text to disk or a database.",
            "Saved reports live only in this browser session and disappear when you close or refresh the page.",
            "The API key is read from a private .env file and is never shown in the app.",
        ])), unsafe_allow_html=True)
        st.markdown(card("Known limits", bullets([
            "Not clinically validated.",
            "AI output can change between runs and can contain errors or omissions.",
            "The personal-identifier check only catches obvious patterns such as emails and phone numbers.",
            "English text only.",
        ])), unsafe_allow_html=True)
    st.caption(DISCLAIMER)


# ---------- Sidebar and page routing ----------
PAGES = {"📝 New Note": new_note_page, "📁 Saved Reports": reports_page, "🛡️ Safety & Privacy": safety_page}

with st.sidebar:
    st.markdown("<div class='brand'>🩺 MedScribeAI</div><div class='brand-sub'>Clinical documentation assistant</div>", unsafe_allow_html=True)
    choice = st.radio("Navigate", list(PAGES), label_visibility="collapsed")
    st.divider()
    st.caption(f"Reports saved this session: {len(st.session_state['reports'])}")
    if is_api_key_configured():
        st.success("API key detected")
    else:
        st.error("API key missing. Add GEMINI_API_KEY to your .env file.")
    st.caption("Educational prototype. Not a substitute for professional medical evaluation.")

PAGES[choice]()
