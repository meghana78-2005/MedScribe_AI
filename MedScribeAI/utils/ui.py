"""Visual helpers: page styling and HTML cards for the MedScribeAI interface."""

import html

import streamlit as st

from prompts.prompts import DETECTED_KEYS, DETECTED_LABELS, NOT_PROVIDED
from utils.case import is_provided

# One palette for the whole interface. .streamlit/config.toml uses the same values, and
# tests/test_app.py checks that the text colours stay readable (WCAG contrast).
PALETTE = {
    "navy": "#243B53", "teal": "#167D8D", "teal-dark": "#0F5F6C", "teal-soft": "#E3F2F5", "tint": "#EAF4F7",
    "bg": "#F1F6FB", "card": "#FFFFFF", "border": "#D9E2EC", "muted": "#52667A",
    "amber-bg": "#FFF6DD", "amber-border": "#F2D58A", "amber-text": "#7A4B00",
    "green-bg": "#E3F6EF", "green-text": "#0B6B4B", "red-bg": "#FDECEC", "red-text": "#9B1C1C",
    "side-bg": "#243B53", "side-text": "#FFFFFF", "side-muted": "#B7C6D6", "side-focus": "#8FD8E3",
}
_ROOT = ":root {" + "".join(f"--{name}: {value};" for name, value in PALETTE.items()) + "}"

_STYLE = """
/* ---- page: these rules repeat what the theme file sets, so the look survives a missing or ignored theme ---- */
.stApp {background-color: var(--bg) !important; color: var(--navy);}
[data-testid="stHeader"] {background: transparent !important;}
.block-container {padding-top: 1.5rem; padding-bottom: 3rem; max-width: 1180px;}
#MainMenu, footer {visibility: hidden;}
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {color: var(--muted) !important;}

/* ---- headings ---- */
.page-head {display: flex; align-items: center; gap: .85rem; margin: 0 0 1.1rem 0;}
.head-icon {display: inline-flex; align-items: center; justify-content: center; width: 42px; height: 42px; flex: none;
            border-radius: 12px; background: var(--teal-soft); font-size: 1.25rem;}
.page-title {font-size: 1.55rem; font-weight: 700; color: var(--navy); line-height: 1.2;}
.page-sub {color: var(--muted); font-size: 1rem; margin-top: .15rem; max-width: 760px; line-height: 1.5;}
.section-title {font-size: 1.2rem; font-weight: 700; color: var(--navy);}
.section-head {display: flex; align-items: center; gap: .6rem; margin: 1.3rem 0 .7rem 0; flex-wrap: wrap;}
.section-label {font-size: 1.1rem; font-weight: 700; color: var(--navy); margin: 1.5rem 0 .6rem 0;}

/* ---- dashboard header ---- */
.hero {display: flex; gap: 1rem; align-items: flex-start; background: var(--tint); border: 1px solid #CFE3E9;
       border-left: 5px solid var(--teal); border-radius: 14px; padding: 1.2rem 1.4rem; margin-bottom: 1.1rem;}
.hero-logo {display: inline-flex; align-items: center; justify-content: center; width: 48px; height: 48px; flex: none;
            border-radius: 14px; background: var(--teal); font-size: 1.5rem;}
.hero-eyebrow {font-size: .78rem; font-weight: 700; letter-spacing: .07em; text-transform: uppercase; color: var(--teal-dark);}
.hero-title {font-size: 1.8rem; font-weight: 700; color: var(--navy); margin: .1rem 0 .3rem 0; line-height: 1.15;}
.hero-text {color: var(--muted); font-size: 1rem; line-height: 1.55; max-width: 720px;}
.pills {display: flex; gap: .45rem; flex-wrap: wrap; margin-top: .75rem;}
.pill {background: var(--card); border: 1px solid #CFE3E9; color: var(--teal-dark); border-radius: 999px;
       padding: .18rem .7rem; font-size: .8rem; font-weight: 600;}

/* ---- cards ---- */
.card {background: var(--card); border: 1px solid var(--border); border-radius: 14px; padding: 1rem 1.25rem;
       box-shadow: 0 1px 2px rgba(36,59,83,.06), 0 4px 12px rgba(36,59,83,.04); margin-bottom: 1rem;}
.card-title {font-size: 1.02rem; font-weight: 700; color: var(--navy); margin-bottom: .5rem; display: flex; align-items: center;}
.card p {margin: 0 0 .4rem 0; line-height: 1.55;}
.card ul {margin: .1rem 0 0 1.1rem; padding: 0;}
.card li {margin-bottom: .3rem; line-height: 1.5;}
.card-warn {background: var(--amber-bg); border-color: var(--amber-border);}
.card-warn .card-title {color: var(--amber-text);}
.card-ok {background: var(--green-bg); border-color: #B5E3CF;}
.card-ok .card-title {color: var(--green-text);}
.card-safe {background: #E8F0F8; border-color: #C9D8E8;}
.chip {display: inline-flex; align-items: center; justify-content: center; width: 28px; height: 28px; border-radius: 50%;
       background: var(--teal); color: #FFFFFF; font-weight: 700; font-size: .85rem; margin-right: .6rem; flex: none;}
.muted {color: var(--muted);}
.grid-2 {display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1rem; align-items: stretch;}
.grid-2 .card {margin-bottom: 0; height: 100%; box-sizing: border-box;}
.notice {background: #E8F0F8; border: 1px solid #C9D8E8; color: var(--navy); border-radius: 12px;
         padding: .8rem 1rem; margin: .2rem 0 1rem 0; line-height: 1.5;}

/* ---- badges ---- */
.badge {display: inline-block; padding: .2rem .65rem; border-radius: 999px; font-size: .78rem; font-weight: 600; white-space: nowrap;}
.badge-draft {background: var(--amber-bg); color: var(--amber-text); border: 1px solid var(--amber-border);}
.badge-ok {background: var(--green-bg); color: var(--green-text);}
.badge-info {background: var(--teal-soft); color: var(--teal-dark);}
.badge-neutral {background: #E6EDF4; color: var(--muted);}

/* ---- statistic cards ---- */
.stat {display: flex; align-items: center; gap: .9rem; background: var(--card); border: 1px solid var(--border);
       border-radius: 14px; padding: 1rem 1.1rem; box-shadow: 0 1px 2px rgba(36,59,83,.06), 0 4px 12px rgba(36,59,83,.04);
       transition: border-color .15s ease, box-shadow .15s ease;}
.stat:hover {border-color: var(--teal); box-shadow: 0 2px 10px rgba(22,125,141,.16);}
.stat-icon {display: inline-flex; align-items: center; justify-content: center; width: 44px; height: 44px; flex: none;
            border-radius: 12px; background: var(--teal-soft); font-size: 1.15rem;}
.stat-value {font-size: 1.9rem; font-weight: 700; color: var(--navy); line-height: 1.05;}
.stat-label {font-size: .86rem; font-weight: 600; color: var(--navy); margin-top: .1rem;}
.stat-hint {font-size: .8rem; color: var(--muted);}

/* ---- recent notes and empty states ---- */
.list-card {padding: .3rem 1.1rem;}
.note-row {display: flex; align-items: center; gap: .85rem; padding: .75rem 0; border-top: 1px solid #E5EDF3;}
.note-row:first-child {border-top: none;}
.note-icon {display: inline-flex; align-items: center; justify-content: center; width: 38px; height: 38px; flex: none;
            border-radius: 10px; background: var(--teal-soft);}
.note-main {flex: 1; min-width: 0;}
.note-title {font-weight: 600; color: var(--navy); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;}
.note-meta {font-size: .84rem; color: var(--muted);}
.empty {text-align: center; padding: 1.7rem 1rem;}
.empty-icon {display: flex; align-items: center; justify-content: center; width: 54px; height: 54px; margin: 0 auto;
             border-radius: 14px; background: var(--teal-soft); font-size: 1.5rem;}
.empty-title {font-weight: 700; color: var(--navy); font-size: 1.05rem; margin: .75rem 0 .25rem 0;}
.empty-text {color: var(--muted); max-width: 440px; margin: 0 auto; line-height: 1.5; font-size: .95rem;}

/* ---- how it works (kept light on purpose) ---- */
.how {background: rgba(255,255,255,.6); border: 1px solid var(--border); border-radius: 14px; padding: .9rem 1.1rem; margin-top: 1rem;}
.how-title {display: flex; align-items: center; gap: .5rem; font-weight: 700; font-size: .98rem; color: var(--navy);}
.steps {display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: .8rem; margin-top: .7rem;}
.step {display: flex; gap: .6rem; align-items: flex-start; font-size: .9rem; color: var(--muted); line-height: 1.45;}
.step-num {display: inline-flex; align-items: center; justify-content: center; width: 24px; height: 24px; flex: none;
           border-radius: 50%; background: var(--teal-soft); color: var(--teal-dark); font-weight: 700; font-size: .8rem;}

/* ---- information tiles ---- */
.tiles {display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: .7rem; margin-bottom: 1rem;}
.tile {border-radius: 12px; padding: .65rem .85rem; border: 1px solid var(--border); background: var(--card); line-height: 1.4;}
.tile-label {font-size: .76rem; font-weight: 700; letter-spacing: .03em; text-transform: uppercase; color: var(--muted);}
.tile-value {font-size: .95rem; color: var(--navy); margin-top: .15rem;}
.tile-ok {border-left: 4px solid var(--teal);}
.tile-missing {background: var(--amber-bg); border-color: var(--amber-border); border-left: 4px solid #E0A030;}
.tile-missing .tile-value {color: var(--amber-text); font-style: italic;}

/* ---- tables and bars ---- */
.table-wrap {overflow-x: auto;}
table.ddx {width: 100%; border-collapse: collapse; font-size: .93rem;}
table.ddx th {text-align: left; background: var(--teal-soft); color: var(--navy); padding: .55rem .75rem; font-weight: 700;}
table.ddx td {padding: .6rem .75rem; border-top: 1px solid #E5EDF3; vertical-align: top; line-height: 1.45; color: var(--navy);}
table.ddx tr:hover td {background: #F7FAFC;}
.bar-row {display: flex; align-items: center; gap: .7rem; margin: .45rem 0;}
.bar-label {width: 190px; font-size: .9rem; color: var(--navy);}
.bar-track {flex: 1; background: var(--teal-soft); border-radius: 999px; height: 12px; overflow: hidden;}
.bar-fill {background: var(--teal); height: 12px; border-radius: 999px;}
.bar-num {width: 36px; text-align: right; font-weight: 700; color: var(--navy);}

/* ---- buttons: teal primary, neutral secondary (both attribute styles Streamlit has used) ---- */
button[kind^="primary"], button[data-testid^="stBaseButton-primary"] {background-color: var(--teal); border: 1px solid var(--teal); color: #FFFFFF;}
button[kind^="primary"] p, button[data-testid^="stBaseButton-primary"] p {color: #FFFFFF;}
button[kind^="primary"]:hover, button[data-testid^="stBaseButton-primary"]:hover {background-color: var(--teal-dark); border-color: var(--teal-dark);}
button[kind^="secondary"], button[data-testid^="stBaseButton-secondary"] {background-color: var(--card); border: 1px solid var(--border); color: var(--navy);}
button[kind^="secondary"]:hover, button[data-testid^="stBaseButton-secondary"]:hover {border-color: var(--teal); color: var(--teal-dark);}
.stButton > button, [data-testid="stDownloadButton"] > button {border-radius: 10px; font-weight: 600;
       transition: box-shadow .15s ease, border-color .15s ease, background-color .15s ease;}
.stButton > button:hover, [data-testid="stDownloadButton"] > button:hover {box-shadow: 0 2px 8px rgba(22,125,141,.22);}
.stButton > button:focus-visible, [data-testid="stDownloadButton"] > button:focus-visible {outline: 2px solid var(--teal); outline-offset: 2px;}
button:disabled {opacity: .55; cursor: not-allowed;}

/* ---- tabs, inputs, containers ---- */
button[data-baseweb="tab"] {color: var(--muted); font-weight: 600;}
button[data-baseweb="tab"][aria-selected="true"] {color: var(--teal-dark);}
[data-baseweb="tab-highlight"] {background-color: var(--teal) !important;}
[data-baseweb="input"]:focus-within, [data-baseweb="textarea"]:focus-within {border-color: var(--teal) !important;}
[data-testid="stExpander"] {background: var(--card); border-radius: 12px;}
[data-testid="stVerticalBlockBorderWrapper"]:has(.card-marker) {background: var(--card); border-radius: 14px;
       box-shadow: 0 1px 2px rgba(36,59,83,.06), 0 4px 12px rgba(36,59,83,.04);}
.card-marker {display: none;}

/* ---- sidebar: deep navy, white text, teal for the active page ---- */
[data-testid="stSidebar"], [data-testid="stSidebarContent"] {background-color: var(--side-bg) !important;}
[data-testid="stSidebar"] hr {border-color: rgba(255,255,255,.16) !important;}
.side-brand {display: flex; align-items: center; gap: .7rem; padding: .2rem 0 .9rem 0;}
.side-logo {display: inline-flex; align-items: center; justify-content: center; width: 42px; height: 42px; flex: none;
            border-radius: 12px; background: var(--teal); font-size: 1.3rem;}
.side-name {color: var(--side-text); font-weight: 700; font-size: 1.2rem; line-height: 1.2;}
.side-tag {color: var(--side-muted); font-size: .8rem;}
.side-section {color: var(--side-muted); font-size: .76rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; margin: .3rem 0 .35rem 0;}
.side-note {color: var(--side-muted); font-size: .82rem; line-height: 1.45; margin-top: .6rem;}
.status {display: inline-block; border-radius: 999px; padding: .25rem .75rem; font-size: .82rem; font-weight: 600; margin-top: .4rem;}
.status-ok {background: rgba(110,231,183,.14); color: #8CF0C4;}
.status-bad {background: rgba(252,165,165,.14); color: #FCB4B4;}
[data-testid="stSidebar"] .stButton > button {width: 100%; justify-content: flex-start; text-align: left; background-color: transparent;
       border: 1px solid transparent; color: var(--side-text);}
[data-testid="stSidebar"] .stButton > button p {color: var(--side-text);}
[data-testid="stSidebar"] .stButton > button:hover {background-color: rgba(255,255,255,.09); border-color: rgba(255,255,255,.2); color: var(--side-text);}
[data-testid="stSidebar"] .stButton > button[kind^="primary"], [data-testid="stSidebar"] .stButton > button[data-testid^="stBaseButton-primary"] {
       background-color: var(--teal); border-color: var(--teal);}
[data-testid="stSidebar"] .stButton > button[kind^="primary"]:hover, [data-testid="stSidebar"] .stButton > button[data-testid^="stBaseButton-primary"]:hover {
       background-color: var(--teal); border-color: rgba(255,255,255,.45);}
[data-testid="stSidebar"] .stButton > button:focus-visible {outline: 2px solid var(--side-focus); outline-offset: 2px;}

@media (max-width: 800px) {
  .grid-2 {grid-template-columns: 1fr;} .bar-label {width: 120px;} .hero-title {font-size: 1.5rem;} .page-title {font-size: 1.4rem;}
  .hero {flex-direction: column;}
}
@media (prefers-reduced-motion: reduce) {* {transition: none !important;}}
"""
_STYLE = "\n".join(line for line in _STYLE.splitlines() if line.strip())   # no blank lines inside the HTML block
CSS = "<style>" + _ROOT + _STYLE + "</style>"


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def esc(text) -> str:
    """Make text safe to place inside HTML (also stops $...$ being read as maths)."""
    return html.escape(" ".join(str(text).split())).replace("$", "&#36;")


def bullets(items: list[str], empty: str = "Nothing provided.") -> str:
    if not items:
        return f"<p class='muted'>{esc(empty)}</p>"
    return "<ul>" + "".join(f"<li>{esc(item)}</li>" for item in items) + "</ul>"


def card(title: str, body_html: str, chip: str = "", variant: str = "") -> str:
    """One card. body_html must already be safe (built with esc/bullets).
    variant: "" (white), "warn" (amber), "ok" (green) or "safe" (blue-grey)."""
    chip_html = f"<span class='chip'>{esc(chip)}</span>" if chip else ""
    extra = f" card-{variant}" if variant else ""
    return f"<div class='card{extra}'><div class='card-title'>{chip_html}{esc(title)}</div>{body_html}</div>"


def card_row(left_html: str, right_html: str) -> str:
    """Two cards side by side. One grid row, so both cards always have the same height."""
    return f"<div class='grid-2'>{left_html}{right_html}</div>"


def stat_card(label: str, value, hint: str = "", icon: str = "") -> str:
    icon_html = f"<div class='stat-icon'>{esc(icon)}</div>" if icon else ""
    hint_html = f"<div class='stat-hint'>{esc(hint)}</div>" if hint else ""
    return (f"<div class='stat'>{icon_html}<div><div class='stat-value'>{esc(value)}</div>"
            f"<div class='stat-label'>{esc(label)}</div>{hint_html}</div></div>")


def bar_rows(items: list[tuple[str, int]]) -> str:
    """Simple horizontal bars (no chart library needed)."""
    top = max([value for _, value in items] + [1])
    rows = "".join(
        f"<div class='bar-row'><div class='bar-label'>{esc(label)}</div>"
        f"<div class='bar-track'><div class='bar-fill' style='width:{100 * value / top:.0f}%'></div></div>"
        f"<div class='bar-num'>{value}</div></div>"
        for label, value in items
    )
    return f"<div class='card'>{rows}</div>"


def page_header(title: str, subtitle: str, icon: str = "") -> None:
    chip = f"<span class='head-icon'>{esc(icon)}</span>" if icon else ""
    st.markdown(
        f"<div class='page-head'>{chip}<div><div class='page-title'>{esc(title)}</div>"
        f"<div class='page-sub'>{esc(subtitle)}</div></div></div>",
        unsafe_allow_html=True,
    )


def hero(title: str, text: str, eyebrow: str = "", pills: list[str] | None = None) -> str:
    """Dashboard header: a light teal-tinted card with a teal accent edge."""
    pills_html = "<div class='pills'>" + "".join(f"<span class='pill'>{esc(p)}</span>" for p in pills) + "</div>" if pills else ""
    return (f"<div class='hero'><div class='hero-logo'>🩺</div><div><div class='hero-eyebrow'>{esc(eyebrow)}</div>"
            f"<div class='hero-title'>{esc(title)}</div><div class='hero-text'>{esc(text)}</div>{pills_html}</div></div>")


def section_label(text: str) -> str:
    return f"<div class='section-label'>{esc(text)}</div>"


_BADGE_VALUES = {"Saved": "badge-ok", "Not saved": "badge-neutral"}


def table_card(rows: list[dict], empty: str = "Nothing to show yet.") -> str:
    """A white card holding a simple table. Every value is escaped."""
    if not rows:
        return empty_state("🗂️", "Nothing here yet", empty)
    head = "".join(f"<th>{esc(name)}</th>" for name in rows[0])
    body = ""
    for row in rows:
        cells = ""
        for value in row.values():
            css = _BADGE_VALUES.get(str(value))
            cells += f"<td><span class='badge {css}'>{esc(value)}</span></td>" if css else f"<td>{esc(value)}</td>"
        body += f"<tr>{cells}</tr>"
    return f"<div class='card'><div class='table-wrap'><table class='ddx'><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div></div>"


def empty_state(icon: str, title: str, text: str) -> str:
    """Friendly placeholder card shown when there is nothing to list yet."""
    return (f"<div class='card empty'><div class='empty-icon'>{esc(icon)}</div>"
            f"<div class='empty-title'>{esc(title)}</div><div class='empty-text'>{esc(text)}</div></div>")


def note_list(rows: list[dict], empty: str) -> str:
    """Recent notes as clean rows: icon, title, small details and a status badge."""
    if not rows:
        return empty_state("🗂️", "No clinical notes yet", empty)
    items = ""
    for row in rows:
        updates = f"{row['updates']} update{'s' if row['updates'] != 1 else ''}"
        badge = ("badge-ok", "Saved") if row["saved"] else ("badge-neutral", "Not saved")
        items += (f"<div class='note-row'><div class='note-icon'>📄</div><div class='note-main'>"
                  f"<div class='note-title'>{esc(row['title'])}</div><div class='note-meta'>{esc(row['created'])} · {esc(updates)}</div></div>"
                  f"<span class='badge {badge[0]}'>{badge[1]}</span></div>")
    return f"<div class='card list-card'>{items}</div>"


def how_it_works(steps: list[str]) -> str:
    """Compact, light numbered steps."""
    items = "".join(f"<div class='step'><span class='step-num'>{i}</span><span>{esc(text)}</span></div>" for i, text in enumerate(steps, 1))
    return f"<div class='how'><div class='how-title'>💡 How MedScribeAI works</div><div class='steps'>{items}</div></div>"


def side_section(label: str) -> str:
    return f"<div class='side-section'>{esc(label)}</div>"


def sidebar_brand() -> str:
    return ("<div class='side-brand'><div class='side-logo'>🩺</div><div><div class='side-name'>MedScribeAI</div>"
            "<div class='side-tag'>Clinical Documentation Assistant</div></div></div>")


def status_pill(text: str, ok: bool = True) -> str:
    return f"<span class='status {'status-ok' if ok else 'status-bad'}'>{'●' if ok else '▲'} {esc(text)}</span>"


def card_marker() -> str:
    """Invisible tag that lets the CSS give the input container a white card look."""
    return "<div class='card-marker'></div>"


def show(html_text: str) -> None:
    st.markdown(html_text, unsafe_allow_html=True)


# ---------- pieces of a note ----------
def detected_tiles(note: dict) -> str:
    """What was provided (teal) versus what is missing (amber)."""
    detected = note.get("information_detected") or {}
    tiles = ""
    for key in DETECTED_KEYS:
        value = detected.get(key, "Not provided")
        css = "tile-ok" if is_provided(value) else "tile-missing"
        tiles += f"<div class='tile {css}'><div class='tile-label'>{esc(DETECTED_LABELS[key])}</div><div class='tile-value'>{esc(value)}</div></div>"
    return f"<div class='tiles'>{tiles}</div>"


def render_summary(note: dict) -> None:
    show(card("Clinical Summary", f"<p>{esc(note['clinical_summary'])}</p>"))
    st.markdown("**Information Detected**")
    st.caption("Teal = provided in your input. Amber = not provided (never guessed).")
    show(detected_tiles(note))


def render_soap(note: dict) -> None:
    show(card_row(
        card("Subjective", bullets(note["subjective"], empty=NOT_PROVIDED), chip="S"),
        card("Objective", bullets(note["objective"], empty=NOT_PROVIDED), chip="O"),
    ))
    show(card_row(
        card("Assessment", f"<p>{esc(note['assessment'])}</p>", chip="A"),
        card("Plan (considerations for clinician review)", bullets(note["plan"], empty="No plan considerations provided."), chip="P"),
    ))


def render_differentials(note: dict) -> None:
    st.markdown("**Possible Differential Diagnoses**")
    st.caption("Possibilities to consider, not confirmed diagnoses. Additional information is needed to narrow them down.")
    rows = note["differential_diagnosis"]
    if not rows:
        show(card("Not enough information", "<p class='muted'>The information provided is not enough to suggest meaningful differential diagnoses. Add more clinical information in the Missing Information tab.</p>"))
        return
    for row in rows:
        with st.expander(f"{row['condition'].replace('$', chr(92) + '$')}  -  View details"):
            show(
                f"<p><strong>Supporting information</strong><br>{esc(row['supporting_information'])}</p>"
                f"<p><strong>Information still needed</strong><br>{esc(row['missing_helpful_information'])}</p>"
            )


def render_missing_card(note: dict) -> None:
    items = note["information_needing_clarification"]
    if items:
        show(card("⚠️ Additional Information Needed", bullets(items), variant="warn"))
    else:
        show(card("No further information identified", "<p>The model did not list any additional details for this case.</p>", variant="ok"))


def render_safety(note: dict) -> None:
    show(f"<div class='notice'>{esc(note['safety_note'])}</div>")
    show(card("How to read this note", variant="safe", body_html=bullets([
        "This is an AI-generated draft for documentation support. Review and verify it against the original information.",
        "Differential diagnoses are possibilities, not confirmed diagnoses.",
        "The plan lists considerations for clinician review, not treatment orders.",
        "Information that was not provided is shown as missing. It is not guessed.",
        "This tool does not replace professional clinical judgement and has not been clinically validated.",
    ])))


def render_note(note: dict) -> None:
    """Read-only view of a whole note (used for saved reports)."""
    tabs = st.tabs(["🩺 Clinical Summary", "📋 SOAP Note", "🔍 Possible Differentials", "⚠️ Missing Information", "🛡️ Safety"])
    with tabs[0]:
        render_summary(note)
    with tabs[1]:
        render_soap(note)
    with tabs[2]:
        render_differentials(note)
    with tabs[3]:
        render_missing_card(note)
    with tabs[4]:
        render_safety(note)
