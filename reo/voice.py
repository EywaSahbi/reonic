"""ElevenLabs speech-to-text and text-to-speech for talking to reo (plan: VOICE.md).

Both calls return None on any failure, so a voice problem never breaks the text chat.
"""
import logging
import os
import re
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
API = "https://api.elevenlabs.io/v1"
DEFAULT_VOICE = "cgSgspJ2msm6clMCkdW9"  # "Jessica" (premade), used until app picks reo's voice
log = logging.getLogger("reo.voice")


def _key() -> str | None:
    return os.getenv("ELEVENLABS_API_KEY") or None


def enabled() -> bool:
    return _key() is not None


def transcribe(audio: bytes, filename: str = "audio.webm", content_type: str = "audio/webm") -> str | None:
    """Customer's recording -> text (language auto-detected), or None."""
    if not enabled() or not audio:
        return None
    try:
        r = httpx.post(f"{API}/speech-to-text", headers={"xi-api-key": _key()},
                       data={"model_id": os.getenv("ELEVENLABS_STT_MODEL", "scribe_v2")},
                       files={"file": (filename, audio, content_type)}, timeout=30)
        r.raise_for_status()
        return r.json().get("text", "").strip() or None
    except (httpx.HTTPError, ValueError) as e:
        log.warning("speech-to-text failed: %s", e)
        return None


NUM = r"\d[\d.,]*"
SPOKEN = [  # (pattern, replacement), applied in order; spoken text only, the chat text is never changed
    (rf"€\s?({NUM})\s?[–-]\s?€?({NUM})", r"\1 to \2 euros"),            # €11,900–22,600
    (rf"€\s?({NUM})", r"\1 euros"),
    (rf"({NUM})\s?[–-]\s?({NUM})", r"\1 to \2"),                        # 5–10
    (rf"({NUM})\s?%", r"\1 percent"),
    (r"\bkWp\b", "kilowatt peak"), (r"\bkWh\b", "kilowatt hours"), (r"\bkW\b", "kilowatts"),
    (r"\bkg\b", "kilograms"), (r"m²|\bm2\b|\bqm\b", "square metres"), (r"\bct\b", "cents"),
    (r"CO₂|\bCO2\b", "carbon dioxide"), (r"\bKfW\b", "K f W"), (r"\bEVs?\b", "E V"), (r"\bPV\b", "solar"),
    (r"/\s?(?:yr|year|a)\b", " per year"), (r"/\s?(?:mo|month)\b", " per month"), (r"\byrs\b", "years"),
    (rf"({NUM})\s?[×x]\s?(?=\d)", r"\1 by "), (rf"({NUM})×", r"\1 times"),          # 8 x 6 m, 3.7×
    (r"\be\.g\.", "for example"), (r"\bi\.e\.", "that is"), (r"\bapprox\.", "approximately"), (r"~", "about "),
    (r"\s+", " "),
]


def spoken(text: str) -> str:
    """Text as it should be read aloud: units, currency, ranges and abbreviations written out."""
    for pattern, repl in SPOKEN:
        text = re.sub(pattern, repl, text)
    return text.strip()


def speak(text: str) -> bytes | None:
    """reo's reply text -> mp3 bytes, or None."""
    if not enabled() or not text:
        return None
    text = spoken(text)
    voice = os.getenv("ELEVENLABS_VOICE_ID") or DEFAULT_VOICE
    try:
        r = httpx.post(f"{API}/text-to-speech/{voice}", params={"output_format": "mp3_44100_128"},
                       headers={"xi-api-key": _key()},
                       json={"text": text, "model_id": os.getenv("ELEVENLABS_TTS_MODEL", "eleven_flash_v2_5")},
                       timeout=30)
        r.raise_for_status()
        return r.content
    except httpx.HTTPError as e:
        log.warning("text-to-speech failed: %s", e)
        return None
