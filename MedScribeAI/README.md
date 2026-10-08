# MedScribeAI: Clinical Dictation-to-SOAP & Differential Diagnosis Assistant

## 1. Project Overview
MedScribeAI is a Streamlit web application for AI-assisted clinical documentation. It takes
clinical dictation (synthetic or de-identified text) and uses Google Gemini to produce:

- a clinical summary
- a SOAP note (Subjective, Objective, Assessment, Plan)
- a differential diagnosis table (possibilities, not confirmed diagnoses)
- a list of information that may need clarification
- a safety note

Notes can be saved as reports during the session and downloaded as text or JSON. It is an
**educational / documentation prototype**. It is not a medical device and does not replace a
qualified healthcare professional.

## 2. Problem Statement
Clinical dictation is usually free text, and turning it into a structured note takes time.
Language models can help, but they can also invent symptoms, findings or treatments that were never
dictated. MedScribeAI structures the dictation, reports missing information instead of guessing, and
keeps the output cautious and easy to check against the original text.

## 3. Objectives
1. Convert clinical dictation into a clinical summary and a SOAP note.
2. Suggest cautious differential diagnoses with supporting and missing information.
3. Report missing information clearly instead of inventing it.
4. Let users save and export notes without storing clinical text on disk.
5. Handle errors gracefully and protect privacy.

## 4. Features
- **New Note:** large dictation box, synthetic sample cases, word count, one-click generation
- **Structured output:** summary, S / O / A / P cards, differential diagnosis table, missing information, safety note
- **Saved Reports:** save notes during the session, open them again, download as text or JSON, delete them
- **Safety & Privacy page:** responsible-use guidance, data handling and known limits
- **Input checks:** empty, too short, too long, and a basic personal-identifier check
- **Friendly errors:** missing key, rejected key, quota, timeout, no internet and unreadable AI replies
- Nothing is written to disk. Saved reports exist only in the current browser session.

## 5. How the AI Is Guided
The app sends the dictation to Gemini with a built-in safety-constrained prompt (in
`prompts/prompts.py`). It tells the model to act as an AI clinical documentation assistant (not a
doctor), to use only information stated in the dictation, never to invent findings, to write
"Not provided in the clinical dictation." when there is no objective data, to avoid presenting any
diagnosis as confirmed, and to return no differentials when information is insufficient. The reply is
requested as JSON, checked, and displayed as cards. Details: `docs/prompt_evaluation.md`.

## 6. System Workflow
```
Clinical dictation -> Validation (length, personal identifiers)
  -> Prompt (prompts/prompts.py) -> Gemini API (utils/llm_client.py)
  -> JSON check (utils/formatting.py) -> Note cards (utils/ui.py)
  -> Optional: save to session reports, download as text or JSON (utils/reports.py)
```
Diagrams: `docs/architecture.png` and `docs/workflow.png`.

## 7. Technology Stack
- Python 3.10 or newer
- Streamlit (interface, styled with a small amount of custom CSS and a theme in `.streamlit/config.toml`)
- `google-genai` (Google Gemini API)
- `python-dotenv` (reads the API key from `.env`)

## 8. Folder Structure
```
MedScribeAI/
├── app.py                    # Streamlit interface and page routing
├── requirements.txt
├── README.md
├── .env.example              # template for your API key (placeholders only)
├── .gitignore                # keeps .env out of Git
├── .streamlit/
│   └── config.toml           # colour theme
├── prompts/
│   └── prompts.py            # prompts, safety rules, worked examples
├── utils/
│   ├── llm_client.py         # Gemini call and error messages
│   ├── validation.py         # input checks
│   ├── formatting.py         # JSON parsing and validation
│   ├── ui.py                 # styling and note cards
│   ├── reports.py            # session reports and exports
│   └── comparison.py         # optional developer tool, not shown in the interface
├── sample_data/
│   └── sample_cases.py       # synthetic sample cases
├── tests/
│   └── test_app.py           # automated offline tests
└── docs/
    ├── prompt_evaluation.md  # prompt documentation and evaluation notes
    ├── test_results.md       # testing record
    ├── architecture.png
    └── workflow.png
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

`GEMINI_MODEL` can be changed without editing code. Model names change over time. If you see a
"model not found" message, check the current model list in Google AI Studio and update this value.

## 11. How to Run
```
streamlit run app.py
```
A browser tab opens at `http://localhost:8501`. The sidebar shows "API key detected" when the key is
found. After changing `.env`, stop the app (`Ctrl + C`) and start it again.

## 12. Sample Input
In **New Note**, choose "Headache" in the sample-case dropdown:

> 28-year-old female with a throbbing headache on the left side of the head for the last two days.
> She describes it as moderate to severe and says it gets worse with bright light and loud noise.
> She felt nauseous yesterday and vomited once. She reports similar headaches a few times in the
> past year. No head injury. No fever. She takes no regular medication. No examination findings
> were recorded.

All sample cases are fictional. Do not enter real patient information.

## 13. Expected Output
After **Generate Clinical Note** you should see: Clinical Summary, then Subjective, Objective,
Assessment and Plan cards, a differential diagnosis table, Information That May Need Clarification
and a safety notice. For the Headache case, **Objective shows "Not provided in the clinical
dictation."** because no examination findings were given.

Example differential table (shortened, from one real run; wording changes between runs):

| Possible Condition | Supporting Information | Missing / Helpful Information |
|---|---|---|
| Migraine | Throbbing one-sided headache, worse with light and noise, nausea, similar past episodes | Neurological examination, aura symptoms |
| Tension-type headache | Recurrent headache episodes | Detailed pain description, associated features |

## 14. Reports and Export
Choose **Save to Reports** under a generated note. Open **Saved Reports** to review, download
(text or JSON) or delete reports. Reports live in memory for the current browser session only and are
lost when the page is closed or refreshed, so download anything you want to keep.

## 15. Testing
Automated offline tests (no API call). Run from the project folder:
```
python -m unittest tests.test_app -v
```
Manual tests and honest results, including what has **not** been tested, are in `docs/test_results.md`.

## 16. Limitations
- Not clinically validated. Output is not medical advice.
- AI output can change between runs and can still contain errors or omissions.
- Testing so far used a small number of synthetic cases and was judged by reading the outputs.
- The personal-identifier check only catches obvious patterns (emails, phone numbers, ID-like numbers, name labels).
- The app checks length, not whether the text is clinical.
- Saved reports are session-only. There is no login or permanent storage.
- Needs an internet connection and a Gemini API key. Free-tier quotas can interrupt use.
- English only.

## 17. Responsible AI / Safety
- Described as an educational / documentation prototype throughout the interface.
- The model is told it is a documentation assistant, not a doctor.
- Differential diagnoses are possibilities, not confirmed diagnoses.
- The plan is limited to considerations for clinician review, with no drug names or doses.
- Use synthetic or de-identified text only. Text you enter is sent to Google's Gemini API; check
  Google's current terms for how API data is handled.
- The app does not store your text on disk.

## 18. Future Enhancements
- Check that input looks like clinical text before calling the model
- Optional permanent storage with sign-in (needs a privacy and security review first)
- Export as PDF or DOCX
- Voice dictation
- Review of output quality by a qualified clinician
- More languages
