"""Visual helpers: page styling and HTML cards for the MedScribeAI interface."""

import html

import streamlit as st

from prompts.prompts import NOT_PROVIDED

CSS = """<style>
.block-container {padding-top: 2.2rem; max-width: 1200px;}
#MainMenu, footer {visibility: hidden;}
.page-title {font-size: 1.9rem; font-weight: 700; color: #12355B; margin: 0;}
.page-sub {color: #5B6770; margin: .2rem 0 1.2rem 0; font-size: 1rem;}
.brand {font-size: 1.35rem; font-weight: 700; color: #12355B;}
.brand-sub {color: #5B6770; font-size: .85rem; margin-bottom: .6rem;}
.card {background: #FFFFFF; border: 1px solid #DCE6EC; border-radius: 14px; padding: 1rem 1.25rem;
       box-shadow: 0 1px 3px rgba(18,53,91,.06); margin-bottom: 1rem;}
.card-title {font-size: 1.05rem; font-weight: 700; color: #12355B; margin-bottom: .55rem;
             display: flex; align-items: center;}
.card p {margin: 0 0 .4rem 0; line-height: 1.55;}
.card ul {margin: .1rem 0 0 1.1rem; padding: 0;}
.card li {margin-bottom: .3rem; line-height: 1.5;}
.chip {display: inline-flex; align-items: center; justify-content: center; width: 28px; height: 28px;
       border-radius: 50%; background: #0F8B8D; color: #FFFFFF; font-weight: 700; font-size: .85rem;
       margin-right: .6rem; flex: none;}
.muted {color: #5B6770;}
.section-head {display: flex; align-items: center; gap: .8rem; margin: 1.4rem 0 .7rem 0; flex-wrap: wrap;}
.section-title {font-size: 1.35rem; font-weight: 700; color: #12355B;}
.badge {display: inline-block; padding: .22rem .7rem; border-radius: 999px; font-size: .75rem; font-weight: 600;}
.badge-draft {background: #FFF3E0; color: #8A5300;}
.notice {background: #FFF8EC; border: 1px solid #F3D9A8; color: #6B4500; border-radius: 12px;
         padding: .8rem 1rem; margin: .2rem 0 1rem 0; line-height: 1.5;}
.table-wrap {overflow-x: auto;}
table.ddx {width: 100%; border-collapse: collapse; font-size: .95rem;}
table.ddx th {text-align: left; background: #E6F4F4; color: #12355B; padding: .6rem .75rem; font-weight: 700;}
table.ddx td {padding: .65rem .75rem; border-top: 1px solid #E5EDF1; vertical-align: top; line-height: 1.45;}
</style>"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def esc(text) -> str:
    """Make text safe to place inside HTML (also stops $...$ being read as maths)."""
    return html.escape(" ".join(str(text).split())).replace("$", "&#36;")


def bullets(items: list[str], empty: str = "Nothing provided.") -> str:
    if not items:
        return f"<p class='muted'>{esc(empty)}</p>"
    return "<ul>" + "".join(f"<li>{esc(item)}</li>" for item in items) + "</ul>"


def card(title: str, body_html: str, chip: str = "") -> str:
    """One white card. body_html must already be safe (built with esc/bullets)."""
    chip_html = f"<span class='chip'>{esc(chip)}</span>" if chip else ""
    return f"<div class='card'><div class='card-title'>{chip_html}{esc(title)}</div>{body_html}</div>"


def page_header(title: str, subtitle: str) -> None:
    st.markdown(
        f"<div class='page-title'>{esc(title)}</div><div class='page-sub'>{esc(subtitle)}</div>",
        unsafe_allow_html=True,
    )


def _differential_table(rows: list[dict]) -> str:
    if not rows:
        return "<p class='muted'>Not enough information in the dictation to suggest differential diagnoses.</p>"
    body = "".join(
        f"<tr><td><strong>{esc(r['condition'])}</strong></td><td>{esc(r['supporting_information'])}</td>"
        f"<td>{esc(r['missing_helpful_information'])}</td></tr>"
        for r in rows
    )
    return (
        "<div class='table-wrap'><table class='ddx'><thead><tr><th>Possible condition</th>"
        "<th>Supporting information</th><th>Missing / helpful information</th></tr></thead>"
        f"<tbody>{body}</tbody></table></div>"
    )


def render_note(note: dict) -> None:
    """Show a parsed note as a set of cards."""
    show = lambda html_text: st.markdown(html_text, unsafe_allow_html=True)

    show(card("Clinical Summary", f"<p>{esc(note['clinical_summary'])}</p>"))

    left, right = st.columns(2, gap="medium")
    with left:
        show(card("Subjective", bullets(note["subjective"]), chip="S"))
    with right:
        show(card("Objective", bullets(note["objective"], empty=NOT_PROVIDED), chip="O"))
    left, right = st.columns(2, gap="medium")
    with left:
        show(card("Assessment", f"<p>{esc(note['assessment'])}</p>", chip="A"))
    with right:
        show(card("Plan (considerations for clinician review)", bullets(note["plan"]), chip="P"))

    show(card(
        "Differential Diagnosis",
        "<p class='muted'>Possibilities to consider, not confirmed diagnoses.</p>" + _differential_table(note["differential_diagnosis"]),
    ))
    show(card(
        "Information That May Need Clarification",
        bullets(note["information_needing_clarification"], empty="No further information identified."),
    ))
    show(f"<div class='notice'>{esc(note['safety_note'])} AI-generated draft: review and verify before any clinical use.</div>")
