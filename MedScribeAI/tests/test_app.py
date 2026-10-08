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
from utils import reports as reports_mod
from utils.ui import esc
from utils.validation import find_possible_pii, validate_dictation

CASE = SAMPLE_CASES["Headache"]
VALID_NOTE = {
    "clinical_summary": "s", "subjective": ["a"], "objective": [], "assessment": "a",
    "plan": ["p"], "differential_diagnosis": [], "information_needing_clarification": [],
    "safety_note": "n",
}


class ValidationTests(unittest.TestCase):
    def test_empty_and_whitespace_rejected(self):
        self.assertFalse(validate_dictation("")[0])
        self.assertFalse(validate_dictation("     ")[0])

    def test_very_short_rejected(self):
        self.assertFalse(validate_dictation("cough and fever")[0])

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
    "clinical_summary": "28-year-old with headache for two days and nausea.", "subjective": ["Headache"],
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


if __name__ == "__main__":
    unittest.main()
