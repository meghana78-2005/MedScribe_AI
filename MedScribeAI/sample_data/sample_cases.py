"""Synthetic clinical samples for demonstration.

All cases are fictional and contain no real patient information. Each sample fills the guided
fields (only what the narrative says) and the free-text dictation. Some samples leave details out
on purpose so we can check that the app reports them as missing instead of inventing them.
"""

EMPTY_CASE = {
    "age": "", "sex": None, "chief_complaint": "", "duration": "", "symptoms": [], "other_symptoms": "",
    "history": "", "medications": "", "allergies": "", "exam": "", "vitals": "", "other": "", "dictation": "",
}


def _case(**fields) -> dict:
    return {**EMPTY_CASE, **fields}


SAMPLES: dict[str, dict] = {
    "Headache": _case(
        age="28", sex="Female", chief_complaint="Headache on the left side of the head", duration="2 days",
        symptoms=["Headache", "Nausea", "Vomiting"],
        dictation=(
            "28-year-old female with a throbbing headache on the left side of the "
            "head for the last two days. She describes it as moderate to severe and "
            "says it gets worse with bright light and loud noise. She felt nauseous "
            "yesterday and vomited once. She reports similar headaches a few times "
            "in the past year. No head injury. No fever. She takes no regular "
            "medication. No examination findings were recorded."
        ),
    ),
    "Cough & Fever": _case(
        age="34", sex="Male", chief_complaint="Dry cough", duration="5 days",
        symptoms=["Cough", "Fever", "Fatigue", "Shortness of breath"], other_symptoms="Sore throat",
        dictation=(
            "Patient is a 34-year-old male presenting with a dry cough for the past "
            "five days. He also reports a sore throat and mild fever that started "
            "two days ago. He says he feels tired and has had some shortness of "
            "breath when climbing stairs. No chest pain reported. He has no known "
            "history of asthma. He is a non-smoker. On examination, temperature is "
            "38.1 degrees Celsius and oxygen saturation is 97 percent on room air. "
            "Chest auscultation shows mild wheeze on the right side."
        ),
    ),
    "Abdominal Pain": _case(
        age="52", sex="Male", chief_complaint="Upper abdominal pain", duration="About 1 week",
        symptoms=["Pain"], other_symptoms="Bloating, belching",
        dictation=(
            "52-year-old male complaining of pain in the upper abdomen for about one "
            "week. The pain is burning in nature and seems worse when he is hungry, "
            "and eating gives some relief. He reports occasional bloating and "
            "belching. He has been taking ibuprofen for knee pain for the last "
            "month. No vomiting. No black stools noticed. Vital signs and "
            "abdominal examination were not recorded."
        ),
    ),
    "Fatigue": _case(
        age="42", sex="Female", chief_complaint="Persistent tiredness", duration="About 3 weeks",
        symptoms=["Fatigue", "Shortness of breath"],
        dictation=(
            "42-year-old female with persistent tiredness for about three weeks. She "
            "reports difficulty concentrating and feeling sleepy during the day. She "
            "has noticed that she gets short of breath more easily when walking "
            "uphill. No fever and no weight loss reported. She works night shifts. "
            "Medications, vital signs and examination findings were not recorded."
        ),
    ),
    "Chest Discomfort": _case(
        age="55", sex="Male", chief_complaint="Chest discomfort", duration="2 days",
        other_symptoms="Chest pressure, sweating",
        dictation=(
            "55-year-old male with chest discomfort for two days. He describes a "
            "pressure-like feeling in the centre of the chest that comes and goes, "
            "sometimes when climbing stairs and easing with rest. He noticed mild "
            "sweating once yesterday. No fever and no cough. He has high blood "
            "pressure and takes a tablet for it daily. Vital signs, ECG and "
            "examination findings were not recorded."
        ),
    ),
    "Shoulder Pain": _case(
        age="45", sex="Female", chief_complaint="Right shoulder pain", duration="3 weeks", symptoms=["Pain"],
        dictation=(
            "45-year-old female with pain in the right shoulder for three weeks. "
            "Pain is worse when lifting her arm above the head and at night when "
            "lying on that side. She works at a desk and does a lot of computer "
            "work. She denies any fall or injury. No numbness or tingling in the "
            "arm. On examination there is tenderness over the front of the shoulder "
            "and painful movement when raising the arm sideways. No swelling noted."
        ),
    ),
    "Minimal Information": _case(
        dictation=(
            "Patient reports feeling unwell and tired for the past few days. "
            "No other details were recorded."
        ),
    ),
    "Blank / Custom Case": _case(),
}

# Free-text narrative of each sample (used by the tests and the documentation).
SAMPLE_CASES: dict[str, str] = {name: s["dictation"] for name, s in SAMPLES.items() if s["dictation"]}
