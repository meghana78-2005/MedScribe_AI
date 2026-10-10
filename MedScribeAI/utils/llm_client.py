"""Talks to the Google Gemini API.

The API key and model name are read from the .env file.
Every problem is turned into a short, friendly LLMError message,
so the app never shows raw stack traces to the user.
"""

import os

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

load_dotenv()  # reads the .env file in the project folder

DEFAULT_MODEL = "gemini-3.5-flash-lite"
TIMEOUT_SECONDS = 60


class LLMError(Exception):
    """An error whose message is safe to show to the user."""


def is_api_key_configured() -> bool:
    """True if a real-looking key is present (the key itself is never shown)."""
    key = os.getenv("GEMINI_API_KEY", "").strip()
    return bool(key) and key != "your_api_key_here"


def get_model_name() -> str:
    return os.getenv("GEMINI_MODEL", "").strip() or DEFAULT_MODEL


def _generate(contents, json_output: bool = False) -> str:
    """Send contents (text, or text plus audio) to Gemini and return the reply text."""
    if not is_api_key_configured():
        raise LLMError(
            "No API key found. Create a .env file (copy .env.example) and set "
            "GEMINI_API_KEY, then restart the app."
        )

    config = types.GenerateContentConfig(
        temperature=0.2,  # low = more consistent, less "creative" output
        response_mime_type="application/json" if json_output else "text/plain",
        http_options=types.HttpOptions(timeout=TIMEOUT_SECONDS * 1000),  # milliseconds
    )

    try:
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY").strip())
        response = client.models.generate_content(
            model=get_model_name(), contents=contents, config=config
        )
    except errors.APIError as err:
        raise LLMError(_explain_api_error(err)) from err
    except Exception as err:  # network down, timeout, etc.
        text = str(err).lower()
        if "timed out" in text or "timeout" in text:
            raise LLMError("The request timed out. Please try again.") from err
        raise LLMError(
            "Could not reach the Gemini API. Check your internet connection and try again."
        ) from err

    reply = (response.text or "").strip()
    if not reply:
        raise LLMError(
            "The model returned an empty response (it may have been blocked). "
            "Try rephrasing the input or try again."
        )
    return reply


def generate_text(prompt: str, json_output: bool = False) -> str:
    """Send a prompt to Gemini and return the reply text.

    Args:
        prompt: the full prompt text.
        json_output: ask Gemini to reply with JSON only.
    """
    return _generate(prompt, json_output)


TRANSCRIBE_INSTRUCTION = (
    "Transcribe the speech in this audio exactly as spoken. Do not add, correct, "
    "summarise or interpret anything. Return only the transcript. If there is no "
    "clear speech, return an empty reply."
)


def transcribe_audio(audio_bytes: bytes, mime_type: str = "audio/wav") -> str:
    """Convert a short recording to text with Gemini (not real-time, not medically validated)."""
    audio_part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)
    return _generate([TRANSCRIBE_INSTRUCTION, audio_part])


def _explain_api_error(err: errors.APIError) -> str:
    """Turn a Gemini API error into a simple message."""
    code = getattr(err, "code", None)
    text = str(err).lower()

    if code in (401, 403) or "api key not valid" in text or "api_key_invalid" in text:
        return "The API key was rejected. Check GEMINI_API_KEY in your .env file."
    if code == 404 or "not found" in text:
        return (
            f"The model '{get_model_name()}' was not found or is not available for "
            "your key. Change GEMINI_MODEL in your .env file."
        )
    if code == 429:
        return "Rate limit or free-tier quota reached. Wait a minute and try again."
    if code and code >= 500:
        return "The Gemini service is having problems right now. Please try again later."
    return "The Gemini API returned an error. Please try again."
