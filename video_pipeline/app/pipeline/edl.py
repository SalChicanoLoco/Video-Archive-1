"""
EDL generation via the Anthropic Claude API.

Reads an SRT transcript and produces a CMX 3600 Edit Decision List
ready for import into Adobe Premiere Pro.

Requires ANTHROPIC_API_KEY in the environment. If not set, raises RuntimeError
so the caller can decide whether to hard-fail or skip gracefully.
"""

import logging
import re
from pathlib import Path

from . import utils

logger = logging.getLogger(__name__)

_EVENT_RE = re.compile(r"^\d{3}\s+", re.MULTILINE)

_DEFAULT_CRITERIA = (
    "Select the most significant, clearly spoken moments. "
    "Prefer complete thoughts over fragments. "
    "Avoid false starts, crosstalk, and silence."
)


def _count_clips(edl_text: str) -> int:
    return len(_EVENT_RE.findall(edl_text))


def generate_edl(
    srt_path: str,
    tape_id: str,
    theme: str = "selects",
    criteria: str = _DEFAULT_CRITERIA,
    frame_rate: str = "30fps NDF",
) -> str:
    """Generate a CMX 3600 EDL from an SRT transcript using Claude.

    Args:
        srt_path: Path to the .srt file (in OUTPUT_ROOT).
        tape_id:  Short identifier used as reel name (truncated to 8 chars).
        theme:    Label for the selection type, e.g. 'highlights', 'selects'.
        criteria: Instructions telling Claude which moments to pick.
        frame_rate: Written into the EDL header.

    Returns:
        Absolute path to the generated .edl file (alongside the .srt).

    Raises:
        RuntimeError: If anthropic is not installed or ANTHROPIC_API_KEY is missing.
        ValueError:   If Claude returns output that doesn't validate as a CMX EDL.
    """
    try:
        import anthropic
    except ImportError:
        raise RuntimeError(
            "anthropic package is not installed — add 'anthropic' to requirements.txt"
        )

    from .. import config_store
    api_key = config_store.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not available — add it to your Airtable Config table "
            "(Key=ANTHROPIC_API_KEY) or to your .env file to enable EDL generation"
        )

    src = Path(srt_path).resolve()
    utils.validate_input_path(str(src), allow_output=True)
    srt_content = src.read_text(encoding="utf-8")

    if not srt_content.strip():
        raise ValueError(f"SRT file is empty: {srt_path}")

    reel = tape_id[:8].upper().replace(" ", "_")

    prompt = f"""You are an expert video editor generating an industry-standard \
CMX 3600 Edit Decision List for Adobe Premiere Pro.

Tape / Reel: {reel}
Frame Rate: {frame_rate}
Theme: {theme}
Selection criteria: {criteria}

SRT Transcript:
{srt_content}

Output ONLY valid CMX 3600 EDL text. No preamble, no markdown, no explanation.

Rules:
- Reel name max 8 chars: use {reel}
- Event numbers zero-padded to 3 digits (001, 002, …)
- Track: V, Transition: C
- Record timecodes sequential starting from 00:00:00:00
- Convert SRT milliseconds to frames at 30fps (ms / 33.333)
- Include a * FROM CLIP NAME line and a * COMMENT line per event
- Minimum clip duration 10 seconds unless content demands shorter
- Target 5–15 clips per tape

TITLE: {reel} {theme.upper()} SELECTS
FCM: NON-DROP FRAME
"""

    client = anthropic.Anthropic(api_key=api_key)
    logger.info("Requesting EDL from Claude for %s (theme: %s)…", tape_id, theme)

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    edl_text = message.content[0].text.strip()

    if not edl_text.startswith("TITLE:"):
        raise ValueError(
            f"Claude returned invalid EDL for {tape_id} — "
            f"does not start with 'TITLE:'. Preview: {edl_text[:120]!r}"
        )

    clip_count = _count_clips(edl_text)
    logger.info("EDL validated: %d clips selected for %s", clip_count, tape_id)

    edl_path = src.with_suffix(".edl")
    edl_path.write_text(edl_text, encoding="utf-8")
    logger.info("EDL written: %s", edl_path)
    return str(edl_path)
