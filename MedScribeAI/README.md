# MedScribeAI: Clinical Dictation-to-SOAP & Differential Diagnosis Assistant

## 1. Project Overview
MedScribeAI is a Streamlit application for AI-assisted clinical documentation. You give it clinical
information (typed, spoken, or from a synthetic sample) and it uses Google Gemini to produce:

- a clinical summary and an "information detected" panel (what was provided and what is missing)
- a SOAP note (Subjective, Objective, Assessment, Plan) that you can edit
- possible differential diagnoses (possibilities, not confirmed diagnoses)
- a list of missing information, with a way to add it and update the note
- a safety note

It is an **educational / documentation-assistance prototype**. It is not a medical device, it has not
been clinically validated, and it does not replace a qualified healthcare professional.

## 2. Problem Statement
Clinical dictation is usually free text, and structuring it takes time. Language models can help but can also
invent symptoms, findings or treatments that were never provided. MedScribeAI structures what is provided,
shows clearly what is missing instead of guessing, and keeps everything easy to check and edit.

## 3. Objectives
1. Turn clinical information into a summary and SOAP note.
2. Suggest cautious differential diagnoses with supporting and missing information.
3. Identify missing information and let the user add it and update the note.
4. Let users edit, save and export notes without storing clinical text on disk.
5. Handle errors gracefully and protect privacy.

## 4. Features
- **Dashboard:** session statistics (notes created, notes updated, missing-information checks, saved reports) and recent notes
- **New Clinical Note:** three input methods (type manually, voice input, sample case), optional guided fields (age, sex, chief complaint, duration, symptom tick-boxes, history, medications, allergies, examination findings, vital signs, other) and a free-text dictation box. Empty fields mean "Not provided", never "No".
- **Analyze:** one click, with a real progress display
- **Clinical workspace tabs:** Clinical Summary, SOAP Note (editable), Possible Differentials (expandable details), Missing Information (add information and update the note), Safety
- **Compare Updates:** shows what information was newly documented between versions (documentation only, no clinical claims)
- **Stale-report protection:** a note is shown only for the exact information it was generated from
- **Saved Reports:** save, reopen, download, delete (this session only)
- **Export:** PDF clinical report, plain text, JSON, and a copy box
- **Session Insights:** counts of your own activity in this session
- **Safety & Privacy page**, input checks and friendly error messages
- Nothing is written to disk. Saved reports exist only in the current browser session.

## 5. How the AI Is Guided
The app sends the combined information to Gemini with a built-in safety-constrained prompt
(`prompts/prompts.py`). It tells the model to act as an AI clinical documentation assistant (not a doctor), to use only
information that was provided, to treat unlisted fields as "not provided", never to invent findings, to avoid presenting
any diagnosis as confirmed, and to return no differentials when information is insufficient. Details are in
`docs/prompt_evaluation.md`. An "Advanced options" panel on the New Clinical Note page lets you switch between the
Safety-Constrained and Structured prompt styles.

## 6. System Workflow
```
Guided fields + dictation (typed, spoken or sample) -> Validation (length, personal identifiers)
  -> Combined text + prompt (prompts/prompts.py) -> Gemini API (utils/llm_client.py)
  -> JSON check (utils/formatting.py) -> Clinical workspace (app.py, utils/ui.py)
  -> Review / edit -> Add missing information -> Update note -> Compare
  -> Save to session reports / export PDF, text or JSON (utils/reports.py, utils/export.py)
```
Diagrams: `docs/architecture.png` and `docs/workflow.png` (they show the earlier, simpler flow).

## 7. Technology Stack
- Python 3.10 or newer
- Streamlit 1.46 or newer (the dark sidebar theme needs 1.46+; voice recording needs `st.audio_input`). The colour theme is in `.streamlit/config.toml` and a small stylesheet in `utils/ui.py`
- `google-genai` (Google Gemini API)
- `python-dotenv` (reads the API key from `.env`)
- `reportlab` (PDF export)

## 8. Folder Structure
```
MedScribeAI/
├── app.py                    # interface, pages, session state
├── requirements.txt
├── README.md
├── .env.example              # template for your API key (placeholders only)
├── .gitignore                # keeps .env out of Git
├── .streamlit/config.toml    # colour theme (soft blue-grey, white, deep navy, teal)
├── prompts/prompts.py        # prompts, safety rules, worked examples, output schema
├── utils/
│   ├── llm_client.py         # Gemini calls (text and audio) and error messages
│   ├── validation.py         # input checks
│   ├── case.py               # builds the input from fields + dictation; edits; comparing versions
│   ├── formatting.py         # JSON parsing and validation
│   ├── ui.py                 # palette, stylesheet and note cards
│   ├── reports.py            # session reports, text/JSON export, stale-report logic
│   ├── export.py             # PDF export
│   └── comparison.py         # optional developer tool, not shown in the interface
├── sample_data/sample_cases.py   # synthetic samples (guided fields + dictation)
├── tests/test_app.py         # automated offline tests
└── docs/                     # prompt documentation, test results, diagrams
```

## 9. Installation
Open the `MedScribeAI` folder in VS Code, open a terminal inside it, then run:

**Windows (PowerShell)**
```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

**Mac / Linux**
```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
You should see `(venv)` at the start of the terminal line.

## 10. API Configuration
1. Create a free API key in [Google AI Studio](https://aistudio.google.com/).
2. Copy `.env.example` to a new file named `.env` (Windows PowerShell: `copy .env.example .env`).
3. Open `.env` and put your key in:
   ```
   GEMINI_API_KEY=your_real_key_here
   GEMINI_MODEL=gemini-3.5-flash-lite
   ```
   No quotes, no spaces around `=`.
4. Never share `.env` or commit it. `.gitignore` already excludes it.

`GEMINI_MODEL` can be changed without editing code. If you see a "model not found" message, check the current
model list in Google AI Studio. Voice transcription also needs a model that accepts audio.

## 11. How to Run
```
streamlit run app.py
```
A browser tab opens at `http://localhost:8501`. After changing `.env`, stop the app (`Ctrl + C`) and start it again.

## 12. Sample Input
In **New Clinical Note**, choose **📝 Sample Case** and pick a case such as "Headache". The guided fields and the
dictation box are filled in and can be edited. For a very short input, clear the form and type only:

> cough and fever

The app should list age, duration, vital signs and the rest as **Not provided** instead of inventing them.

## 13. Expected Output
After **Analyze Clinical Note** you get a clinical workspace with five tabs. The Clinical Summary tab shows a
summary and an "Information Detected" panel (teal = provided, amber = not provided). The SOAP tab shows the four
sections, the Possible Differentials tab shows expandable cards, and the Missing Information tab lists what is
needed and lets you add it. Use **Update Clinical Note** to re-analyze with the added information.

## 14. Reports and Export
Choose **Save to Reports** under the workspace. **Saved Reports** lists reports with their update count. Use
**Download Clinical Report** for a PDF (or text / JSON). Reports are stored only for this session and are lost when
the page is closed or refreshed, so download anything you want to keep. Choosing **New Clinical Note** starts a fresh
workspace; unsaved notes are not kept.

## 15. Testing
Automated offline tests (no API call). Run from the project folder:
```
python -m unittest tests.test_app -v
```
Manual tests and honest results, including what has **not** been tested, are in `docs/test_results.md`.

## 16. Limitations
- Not clinically validated. Output is not medical advice.
- AI output can change between runs and can contain errors or omissions.
- Testing used a small number of synthetic cases, and parts of the newest features have not yet been tested live.
- Voice input records in the browser and transcribes with Gemini after you click Transcribe. It is not real-time and has not been checked for medical terms. Review the text before analyzing.
- The personal-identifier check only catches obvious patterns (emails, phone numbers, ID-like numbers, name labels).
- Saved reports are session-only. There is no login or permanent storage.
- The look relies on Streamlit's theme settings plus a small amount of CSS. A future Streamlit update could change some element names; the CSS is written so that anything it can no longer find falls back to Streamlit's default look.
- PDF export uses standard fonts, so unusual symbols are replaced with simple ones.
- Colours: if the app looks plain white or the buttons are red, Streamlit did not pick up `.streamlit/config.toml`. Check that the `.streamlit` folder sits next to `app.py`, start the app from that folder, update with `pip install -U streamlit`, and restart. The app's own stylesheet still sets the main colours without the file.
- Needs an internet connection and a Gemini API key. Free-tier quotas can interrupt use.
- English only.

## 17. Responsible AI / Safety
- Described as an educational / documentation-assistance prototype throughout the interface.
- The model is told it is a documentation assistant, not a doctor.
- Differential diagnoses are possibilities, not confirmed diagnoses.
- The plan is limited to considerations for clinician review, with no drug names or doses.
- Missing information is identified, not guessed. An empty field means "Not provided", never "No".
- Use synthetic or de-identified text only. Text you enter, and voice recordings you transcribe, are sent to Google's
  Gemini API; check Google's current terms for how API data is handled.
- The app does not store your text on disk.

## 18. Future Enhancements
- Check that input looks like clinical text before calling the model
- Optional permanent storage with sign-in (needs a privacy and security review first)
- Real-time or streaming voice dictation
- More languages and more note formats
- Review of output quality by a qualified clinician
