"""Synthetic clinical dictation samples for demonstration.

All cases are fictional. They contain no real patient information.
Some cases intentionally leave out details (for example vitals or
medications) so we can test whether the model avoids inventing them.
"""

SAMPLE_CASES: dict[str, str] = {
    "Respiratory complaint": (
        "Patient is a 34-year-old male presenting with a dry cough for the past "
        "five days. He also reports a sore throat and mild fever that started "
        "two days ago. He says he feels tired and has had some shortness of "
        "breath when climbing stairs. No chest pain reported. He has no known "
        "history of asthma. He is a non-smoker. On examination, temperature is "
        "38.1 degrees Celsius and oxygen saturation is 97 percent on room air. "
        "Chest auscultation shows mild wheeze on the right side."
    ),
    "Headache": (
        "28-year-old female with a throbbing headache on the left side of the "
        "head for the last two days. She describes it as moderate to severe and "
        "says it gets worse with bright light and loud noise. She felt nauseous "
        "yesterday and vomited once. She reports similar headaches a few times "
        "in the past year. No head injury. No fever. She takes no regular "
        "medication. No examination findings were recorded."
    ),
    "Abdominal complaint": (
        "52-year-old male complaining of pain in the upper abdomen for about one "
        "week. The pain is burning in nature and seems worse when he is hungry, "
        "and eating gives some relief. He reports occasional bloating and "
        "belching. He has been taking ibuprofen for knee pain for the last "
        "month. No vomiting. No black stools noticed. Vital signs and "
        "abdominal examination were not recorded."
    ),
    "Musculoskeletal complaint": (
        "45-year-old female with pain in the right shoulder for three weeks. "
        "Pain is worse when lifting her arm above the head and at night when "
        "lying on that side. She works at a desk and does a lot of computer "
        "work. She denies any fall or injury. No numbness or tingling in the "
        "arm. On examination there is tenderness over the front of the shoulder "
        "and painful movement when raising the arm sideways. No swelling noted."
    ),
    "Minimal information": (
        "Patient reports feeling unwell and tired for the past few days. "
        "No other details were recorded."
    ),
}
