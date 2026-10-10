"""Automated offline tests for MedScribeAI. They do NOT call the real Gemini API.

Run from the project folder (the one containing app.py):
    python -m unittest tests.test_app -v
"""

import json
import os
import unittest
from types import SimpleNamespace
from unittest import mock

from prompts import prompts
from sample_data.sample_cases import SAMPLE_CASES
from utils import llm_client
from utils.formatting import ParseError, parse_json_response
from utils import case as case_mod
from utils import reports as reports_mod
from utils.export import ExportError, report_to_pdf
from utils import ui as ui_mod
from utils.ui import esc
from utils.validation import find_possible_pii, validate_additions, validate_dictation

CASE = SAMPLE_CASES["Headache"]
VALID_NOTE = {
    "clinical_summary": "s", "information_detected": {}, "subjective": ["a"], "objective": [], "assessment": "a",
    "plan": ["p"], "differential_diagnosis": [], "information_needing_clarification": [],
    "safety_note": "n",
}


class ValidationTests(unittest.TestCase):
    def test_empty_and_whitespace_rejected(self):
        self.assertFalse(validate_dictation("")[0])
        self.assertFalse(validate_dictation("     ")[0])

    def test_very_short_rejected(self):
        self.assertFalse(validate_dictation("fever")[0])
        self.assertFalse(validate_dictation("cough fever")[0])

    def test_short_symptom_list_reaches_the_model(self):
        self.assertTrue(validate_dictation("cough and fever")[0])

    def test_too_long_rejected(self):
        self.assertFalse(validate_dictation("word " * 2000)[0])

    def test_all_sample_cases_accepted(self):
        for name, text in SAMPLE_CASES.items():
            self.assertTrue(validate_dictation(text)[0], name)

    def test_personal_identifiers_rejected(self):
        base = "28-year-old female with headache for two days and nausea. "
        for extra in ["Email a.b@example.com", "Phone 9876543210", "Name: Priya", "MRN 4455"]:
            self.assertTrue(find_possible_pii(base + extra), extra)

    def test_normal_numbers_not_flagged(self):
        text = "BP 120/80, pulse 88, temperature 38.1, SpO2 97 percent, weight 72 kg."
        self.assertEqual(find_possible_pii(text), [])


class PromptTests(unittest.TestCase):
    def test_every_strategy_has_a_builder_and_description(self):
        self.assertEqual(set(prompts.PROMPT_BUILDERS), set(prompts.STRATEGY_INFO))

    def test_dictation_is_inside_every_prompt(self):
        for name in prompts.STRATEGY_INFO:
            self.assertIn(CASE, prompts.build_prompt(name, CASE), name)

    def test_each_technique_adds_its_own_part(self):
        basic = prompts.build_prompt("Basic / Zero-Shot", CASE)
        role = prompts.build_prompt("Role-Based", CASE)
        few = prompts.build_prompt("Few-Shot", CASE)
        structured = prompts.build_prompt("Structured", CASE)
        safety = prompts.build_prompt("Safety-Constrained", CASE)
        self.assertNotIn("clinical documentation assistant", basic)
        for text in (role, few, structured, safety):
            self.assertIn("AI clinical documentation assistant", text)
            self.assertNotIn("You are a doctor", text)
        self.assertIn("Example 1", few)
        self.assertNotIn("Example 1", structured)
        self.assertIn("Follow these rules strictly", safety)
        self.assertNotIn("Follow these rules strictly", structured)

    def test_json_strategies(self):
        self.assertTrue(prompts.expects_json("Structured"))
        self.assertTrue(prompts.expects_json("Safety-Constrained"))
        self.assertFalse(prompts.expects_json("Basic / Zero-Shot"))

    def test_worked_examples_follow_the_schema(self):
        for example in prompts.EXAMPLES:
            self.assertEqual(set(example["output"]), set(VALID_NOTE))


class ParsingTests(unittest.TestCase):
    def test_valid_json(self):
        self.assertEqual(parse_json_response(json.dumps(VALID_NOTE))["assessment"], "a")

    def test_fenced_json_and_surrounding_text(self):
        raw = json.dumps(VALID_NOTE)
        parse_json_response("```json\n" + raw + "\n```")
        parse_json_response("Here is the note:\n" + raw + "\nThanks")

    def test_malformed_output_rejected(self):
        for bad in ["not json", '{"clinical_summary": "x",', '{"clinical_summary": "x"}', "[1, 2]"]:
            with self.assertRaises(ParseError, msg=bad):
                parse_json_response(bad)

    def test_wrong_types_are_repaired(self):
        note = dict(VALID_NOTE, objective="one string", differential_diagnosis="oops")
        parsed = parse_json_response(json.dumps(note))
        self.assertEqual(parsed["objective"], ["one string"])
        self.assertEqual(parsed["differential_diagnosis"], [])


class FakeApiError(Exception):
    def __init__(self, code, message=""):
        super().__init__(message)
        self.code = code


class LlmClientTests(unittest.TestCase):
    def test_missing_key(self):
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            with self.assertRaisesRegex(llm_client.LLMError, "No API key"):
                llm_client.generate_text("hi")

    def test_placeholder_key_counts_as_missing(self):
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "your_api_key_here"}):
            self.assertFalse(llm_client.is_api_key_configured())

    def test_network_failure_and_timeout(self):
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "fake"}):
            with mock.patch("utils.llm_client.genai.Client", side_effect=ConnectionError("dns")):
                with self.assertRaisesRegex(llm_client.LLMError, "Could not reach"):
                    llm_client.generate_text("hi")
            with mock.patch("utils.llm_client.genai.Client", side_effect=TimeoutError("timed out")):
                with self.assertRaisesRegex(llm_client.LLMError, "timed out"):
                    llm_client.generate_text("hi")

    def test_empty_reply(self):
        client = mock.MagicMock()
        client.models.generate_content.return_value = SimpleNamespace(text="")
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "fake"}):
            with mock.patch("utils.llm_client.genai.Client", return_value=client):
                with self.assertRaisesRegex(llm_client.LLMError, "empty response"):
                    llm_client.generate_text("hi")

    def test_api_error_messages(self):
        explain = llm_client._explain_api_error
        self.assertIn("rejected", explain(FakeApiError(401)))
        self.assertIn("not found", explain(FakeApiError(404)))
        self.assertIn("quota", explain(FakeApiError(429)))
        self.assertIn("problems", explain(FakeApiError(503)))


NOTE = {
    "clinical_summary": "28-year-old with headache for two days and nausea.",
    "information_detected": {"age_and_sex": "28-year-old female", "symptoms": "Headache, nausea", "duration": "Two days"},
    "subjective": ["Headache"],
    "objective": ["Not provided in the clinical dictation."], "assessment": "May suggest a primary headache.",
    "plan": ["Clinician review"],
    "differential_diagnosis": [{"condition": "Migraine", "supporting_information": "Throbbing", "missing_helpful_information": "Aura"}],
    "information_needing_clarification": ["Vital signs"], "safety_note": "Possibilities only.",
}


class ReportTests(unittest.TestCase):
    def test_ids_keep_increasing_after_deleting(self):
        first = reports_mod.make_report("R-001", "", "now", "text", NOTE)
        third = reports_mod.make_report("R-003", "", "now", "text", NOTE)
        self.assertEqual(reports_mod.next_report_id([]), "R-001")
        self.assertEqual(reports_mod.next_report_id([first, third]), "R-004")

    def test_title_uses_label_or_summary(self):
        self.assertEqual(reports_mod.make_report("R-001", " My label ", "now", "t", NOTE)["title"], "My label")
        auto = reports_mod.make_report("R-001", "", "now", "t", NOTE)["title"]
        self.assertTrue(auto.startswith("28-year-old with headache"))

    def test_text_export_has_every_section_and_disclaimer(self):
        text = reports_mod.note_to_text(reports_mod.make_report("R-001", "x", "now", "orig dictation", NOTE))
        for part in ["CLINICAL SUMMARY", "S - SUBJECTIVE", "O - OBJECTIVE", "A - ASSESSMENT", "P - PLAN",
                     "DIFFERENTIAL DIAGNOSIS", "INFORMATION THAT MAY NEED CLARIFICATION", "SAFETY NOTE",
                     "ORIGINAL DICTATION", "orig dictation", "Migraine", reports_mod.DISCLAIMER]:
            self.assertIn(part, text)

    def test_json_export_round_trip(self):
        report = reports_mod.make_report("R-001", "x", "now", "d", NOTE)
        data = json.loads(reports_mod.note_to_json(report))
        self.assertEqual(data["note"], NOTE)
        self.assertIn("disclaimer", data)
        everything = json.loads(reports_mod.all_reports_json([report]))
        self.assertEqual(len(everything["reports"]), 1)

    def test_report_rows(self):
        rows = reports_mod.report_rows([reports_mod.make_report("R-001", "x", "now", "d", NOTE)])
        self.assertEqual(rows[0]["Differentials"], 1)

    def test_html_escaping(self):
        self.assertNotIn("<script>", esc("<script>alert(1)</script>"))
        self.assertEqual(esc("SpO$_2$ 97"), "SpO&#36;_2&#36; 97")
        self.assertNotIn("\n", esc("line one\n\nline two"))


class StaleReportTests(unittest.TestCase):
    def setUp(self):
        self.abdominal = "severe lower abdominal pain for 15 hours"
        self.current = {"input_hash": reports_mod.input_fingerprint(self.abdominal), "note": NOTE}

    def test_no_note_yet(self):
        self.assertEqual(reports_mod.report_status(None, reports_mod.input_fingerprint("cough and fever")), "none")

    def test_note_is_fresh_for_the_same_text(self):
        fp = reports_mod.input_fingerprint(self.abdominal)
        self.assertEqual(reports_mod.report_status(self.current, fp), "fresh")

    def test_changed_text_makes_the_note_stale(self):
        fp = reports_mod.input_fingerprint("cough and fever")
        self.assertEqual(reports_mod.report_status(self.current, fp), "stale")

    def test_extra_spaces_do_not_make_it_stale_but_real_edits_do(self):
        spaced = reports_mod.input_fingerprint("  severe lower   abdominal pain\nfor 15 hours ")
        self.assertEqual(reports_mod.report_status(self.current, spaced), "fresh")
        edited = reports_mod.input_fingerprint(self.abdominal + " and vomiting")
        self.assertEqual(reports_mod.report_status(self.current, edited), "stale")

    def test_going_back_to_the_original_text_shows_the_note_again(self):
        stale = reports_mod.report_status(self.current, reports_mod.input_fingerprint("cough and fever"))
        back = reports_mod.report_status(self.current, reports_mod.input_fingerprint(self.abdominal))
        self.assertEqual((stale, back), ("stale", "fresh"))

    def test_button_labels(self):
        label = reports_mod.generate_button_label
        self.assertEqual(label("none", False), "\u2728 Analyze Clinical Note")
        self.assertEqual(label("fresh", False), "\U0001F504 Re-analyze Clinical Note")
        self.assertEqual(label("stale", False), "\u2728 Analyze Updated Information")
        self.assertEqual(label("stale", True), "Analyzing...")

    def test_sparse_input_rules_are_in_the_prompt(self):
        prompt = prompts.build_prompt("Safety-Constrained", "cough and fever")
        self.assertIn("Never invent age, sex, duration, severity", prompt)
        self.assertIn("one or two bare symptoms", prompt)


SAMPLE_CASE_FIELDS = {
    "age": "34", "sex": "Male", "chief_complaint": "", "duration": "", "symptoms": ["Fever", "Cough"],
    "other_symptoms": "fever, sore throat", "history": "", "medications": "", "allergies": "",
    "exam": "", "vitals": "", "other": "", "dictation": "",
}


class CaseTests(unittest.TestCase):
    def test_plain_dictation_is_sent_exactly_as_typed(self):
        self.assertEqual(case_mod.case_text({"dictation": "  cough and fever "}), "cough and fever")

    def test_empty_fields_are_left_out_never_written_as_no(self):
        text = case_mod.case_text(SAMPLE_CASE_FIELDS)
        self.assertIn("Age: 34", text)
        self.assertIn("Symptoms reported: Fever, Cough, sore throat", text)
        for label in ("Allergies", "Vital signs", "Examination findings", "Current medications", "Duration"):
            self.assertNotIn(label, text)
        self.assertNotIn(": No", text)

    def test_unticked_symptoms_are_not_listed_and_duplicates_are_removed(self):
        symptoms = case_mod.symptom_list(SAMPLE_CASE_FIELDS)
        self.assertEqual(symptoms, ["Fever", "Cough", "sore throat"])

    def test_dictation_is_added_under_its_own_heading(self):
        text = case_mod.case_text({"age": "34", "dictation": "cough for three days"})
        self.assertTrue(text.endswith("Clinical dictation:\ncough for three days"))

    def test_content_has_no_labels_and_empty_case_is_empty(self):
        self.assertEqual(case_mod.case_content(SAMPLE_CASE_FIELDS), "34 Male Fever, Cough, sore throat")
        self.assertEqual(case_mod.case_content({}), "")
        self.assertEqual(case_mod.provided_summary({}), "nothing yet")

    def test_additions_are_combined_with_the_original(self):
        text = case_mod.with_additions("cough and fever", ["3 days", "no chest pain"])
        self.assertIn("cough and fever", text)
        self.assertIn("Additional information added later by the user:\n- 3 days\n- no chest pain", text)
        self.assertEqual(case_mod.with_additions("cough", []), "cough")

    def test_edits_are_kept_separate_from_the_ai_note(self):
        version = {"note": NOTE, "edited": None}
        self.assertEqual(case_mod.effective_note(version)["assessment"], NOTE["assessment"])
        version["edited"] = {"subjective": ["Edited item"], "assessment": "Edited assessment"}
        shown = case_mod.effective_note(version)
        self.assertEqual((shown["subjective"], shown["assessment"]), (["Edited item"], "Edited assessment"))
        self.assertEqual(shown["plan"], NOTE["plan"])
        self.assertEqual(NOTE["subjective"], ["Headache"])          # the AI version itself is unchanged

    def test_line_conversion(self):
        self.assertEqual(case_mod.lines_to_list("- one\n\n\u2022 two\n  three  "), ["one", "two", "three"])
        self.assertEqual(case_mod.list_to_lines(["a", "b"]), "a\nb")

    def test_compare_finds_added_and_updated_information(self):
        old = {"information_detected": {"symptoms": "Cough, fever", "duration": "Not provided", "vital_signs": "Temp 38 C"},
               "differential_diagnosis": [{"condition": "Viral infection"}]}
        new = {"information_detected": {"symptoms": "Dry cough, fever", "duration": "3 days", "vital_signs": "temp 38 c"},
               "differential_diagnosis": [{"condition": "Viral infection"}, {"condition": "Bronchitis"}]}
        changes = {c["label"]: c for c in case_mod.compare_information(old, new)}
        self.assertEqual(changes["Duration"]["kind"], "Added")
        self.assertEqual(changes["Symptoms"]["kind"], "Updated")
        self.assertNotIn("Vital signs", changes)               # same text apart from letter case
        self.assertEqual(case_mod.differential_changes(old, new), (["Bronchitis"], []))

    def test_is_provided(self):
        self.assertFalse(case_mod.is_provided("Not provided"))
        self.assertFalse(case_mod.is_provided("not provided (urine tests not recorded)"))
        self.assertFalse(case_mod.is_provided(""))
        self.assertTrue(case_mod.is_provided("3 days"))


class InformationDetectedTests(unittest.TestCase):
    def test_missing_or_odd_values_become_not_provided(self):
        note = dict(VALID_NOTE, information_detected={"symptoms": ["cough", "fever"], "duration": "", "severity": None})
        parsed = parse_json_response(json.dumps(note))["information_detected"]
        self.assertEqual(parsed["symptoms"], "cough, fever")
        self.assertEqual(parsed["duration"], "Not provided")
        self.assertEqual(parsed["vital_signs"], "Not provided")      # key missing completely
        self.assertEqual(set(parsed), set(prompts.DETECTED_KEYS))

    def test_notes_without_the_key_still_parse(self):
        note = {k: v for k, v in VALID_NOTE.items() if k != "information_detected"}
        self.assertEqual(parse_json_response(json.dumps(note))["information_detected"]["allergies"], "Not provided")

    def test_prompt_asks_for_information_detected_and_treats_unlisted_as_not_provided(self):
        prompt = prompts.build_prompt("Safety-Constrained", "Age: 34\nSymptoms reported: Fever")
        self.assertIn('"information_detected"', prompt)
        self.assertIn("was NOT PROVIDED", prompt)
        self.assertIn("Additional information added later", prompt)


class AdditionsValidationTests(unittest.TestCase):
    def test_short_additions_are_fine(self):
        self.assertTrue(validate_additions("3 days")[0])

    def test_empty_long_and_identifying_additions_are_rejected(self):
        self.assertFalse(validate_additions("   ")[0])
        self.assertFalse(validate_additions("x" * 2001)[0])
        self.assertFalse(validate_additions("call 9876543210")[0])


class ExportTests(unittest.TestCase):
    def report(self, **changes):
        note = dict(NOTE, **changes)
        return reports_mod.make_report("R-001", "Test", "now", "original input", note, update_count=1, additions=["3 days"])

    def test_pdf_is_created(self):
        self.assertEqual(report_to_pdf(self.report())[:4], b"%PDF")

    def test_pdf_handles_unusual_characters_markup_and_empty_sections(self):
        odd = self.report(clinical_summary="Temp 38\u00b0C \u2013 <b>bold</b> & \u201cquote\u201d \u2265 5 \u4e2d", differential_diagnosis=[],
                          objective=[], information_needing_clarification=[])
        self.assertEqual(report_to_pdf(odd)[:4], b"%PDF")

    def test_broken_report_gives_a_friendly_error(self):
        with self.assertRaises(ExportError):
            report_to_pdf({"id": "x"})

    def test_text_export_has_information_detected_and_additions(self):
        text = reports_mod.note_to_text(self.report())
        self.assertIn("INFORMATION DETECTED", text)
        self.assertIn("- Duration: Two days", text)
        self.assertIn("ADDITIONAL INFORMATION ADDED LATER\n- 3 days", text)
        self.assertIn("Updates: 1", text)

    def test_saved_report_rows_include_update_count(self):
        self.assertEqual(reports_mod.report_rows([self.report()])[0]["Updates"], 1)


class TranscriptionTests(unittest.TestCase):
    def test_audio_is_sent_with_an_instruction_and_the_transcript_is_returned(self):
        client = mock.MagicMock()
        client.models.generate_content.return_value = SimpleNamespace(text="  cough and fever  ")
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "fake"}):
            with mock.patch("utils.llm_client.genai.Client", return_value=client):
                with mock.patch.object(llm_client.types, "Part", create=True) as part:
                    text = llm_client.transcribe_audio(b"RIFFdata", "audio/wav")
        self.assertEqual(text, "cough and fever")
        part.from_bytes.assert_called_once_with(data=b"RIFFdata", mime_type="audio/wav")
        sent = client.models.generate_content.call_args.kwargs["contents"]
        self.assertEqual(sent[0], llm_client.TRANSCRIBE_INSTRUCTION)

    def test_transcription_needs_an_api_key(self):
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            with mock.patch.object(llm_client.types, "Part", create=True):
                with self.assertRaises(llm_client.LLMError):
                    llm_client.transcribe_audio(b"x")


def _luminance(hex_colour: str) -> float:
    channels = [int(hex_colour.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(first: str, second: str) -> float:
    lighter, darker = sorted([_luminance(first), _luminance(second)], reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


class DesignTests(unittest.TestCase):
    def test_text_colours_meet_wcag_aa(self):
        p = ui_mod.PALETTE
        pairs = [("navy", "bg"), ("navy", "card"), ("muted", "bg"), ("muted", "card"), ("card", "teal"), ("teal", "card"),
                 ("teal-dark", "teal-soft"), ("amber-text", "amber-bg"), ("green-text", "green-bg"), ("red-text", "red-bg"),
                 ("side-text", "side-bg"), ("side-muted", "side-bg"), ("side-focus", "side-bg"), ("card", "navy"), ("teal-dark", "bg"), ("muted", "tint"), ("navy", "tint"), ("teal-dark", "card")]
        for foreground, background in pairs:
            self.assertGreaterEqual(contrast(p[foreground], p[background]), 4.5, f"{foreground} on {background}")

    def test_theme_file_matches_the_palette(self):
        try:
            import tomllib
        except ImportError:                      # Python 3.10
            self.skipTest("tomllib needs Python 3.11 or newer")
        with open(".streamlit/config.toml", "rb") as handle:
            theme = tomllib.load(handle)["theme"]
        p = ui_mod.PALETTE
        self.assertEqual(theme["primaryColor"].lower(), p["teal"].lower())
        self.assertEqual(theme["backgroundColor"].lower(), p["bg"].lower())
        self.assertEqual(theme["textColor"].lower(), p["navy"].lower())
        self.assertEqual(theme["sidebar"]["backgroundColor"].lower(), p["side-bg"].lower())

    def test_css_uses_the_requested_palette(self):
        for colour in ("#F1F6FB", "#243B53", "#167D8D"):
            self.assertIn(colour.lower(), ui_mod.CSS.lower())

    def test_table_card_escapes_values_and_shows_status_badges(self):
        html_text = ui_mod.table_card([{"Title": "<script>x</script>", "Status": "Saved"}, {"Title": "b", "Status": "Not saved"}])
        self.assertNotIn("<script>", html_text)
        self.assertIn("badge-ok", html_text)
        self.assertIn("badge-neutral", html_text)
        self.assertIn("Nothing here yet", ui_mod.table_card([], empty="Empty list"))

    def test_navy_sidebar_and_teal_primary_are_in_the_stylesheet(self):
        css = ui_mod.CSS
        self.assertIn("--side-bg: #243B53", css)
        self.assertIn('[data-testid="stSidebar"]', css)
        self.assertIn("button[kind^=\"primary\"]", css)
        self.assertIn("stBaseButton-primary", css)

    def test_recent_notes_and_empty_states(self):
        rows = [{"title": "<b>Cough</b>", "created": "02 Oct 2026, 10:00", "updates": 1, "saved": True},
                {"title": "Headache", "created": "02 Oct 2026, 11:00", "updates": 0, "saved": False}]
        html_text = ui_mod.note_list(rows, empty="none")
        self.assertNotIn("<b>Cough", html_text)
        self.assertIn("1 update<", html_text.replace("</div>", "<"))
        self.assertIn("0 updates", html_text)
        self.assertIn("badge-ok", html_text)
        self.assertIn("badge-neutral", html_text)
        self.assertIn("No clinical notes yet", ui_mod.note_list([], empty="Start here"))
        self.assertIn("Start here", ui_mod.empty_state("📋", "No reports yet", "Start here"))

    def test_how_it_works_and_hero(self):
        steps = ui_mod.how_it_works(["one", "two <i>"])
        self.assertEqual(steps.count("step-num"), 2)
        self.assertNotIn("<i>", steps)
        self.assertEqual(ui_mod.hero("T", "text", "eyebrow", ["a", "b"]).count("class='pill'"), 2)

    def test_card_variants_and_stat_icons(self):
        self.assertIn("card-warn", ui_mod.card("t", "<p>x</p>", variant="warn"))
        self.assertNotIn("card-warn", ui_mod.card("t", "<p>x</p>"))
        self.assertIn("stat-icon", ui_mod.stat_card("Notes", 3, "hint", "📝"))
        self.assertIn("status-bad", ui_mod.status_pill("missing", ok=False))


if __name__ == "__main__":
    unittest.main()
