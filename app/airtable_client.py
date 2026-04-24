"""
Airtable integration for the Video Archive pipeline.

Source of truth for tape state. Every pipeline operation calls this module.

GUARDRAIL: Operation Log is append-only. This module has no update/delete
           methods for the Operation Log table — only create via log().

Do not change function signatures without updating all callers.

Expected Airtable base structure
─────────────────────────────────
Tapes          — one record per tape
Transcripts    — one record per transcript, linked to Tapes via "Tape ID" text
EDLs           — one record per EDL, linked to Tapes via "Tape ID" text
Operation Log  — append-only event log

Field names match the defaults in Settings. Override via env vars if your base
uses different names (AIRTABLE_TABLE_TAPES, etc.).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from pyairtable import Api

from app.config import settings

logger = logging.getLogger("video_archive.airtable")

# ── Status constants (Airtable single-select values) ─────────────────────────
STATUS_INTAKE = "Intake"
STATUS_RENAMED = "Renamed"
STATUS_METADATA_DONE = "Metadata Done"
STATUS_AUDIO_EXTRACTED = "Audio Extracted"
STATUS_TRANSCRIBED = "Transcribed"
STATUS_QA_PASSED = "QA Passed"
STATUS_QA_FAILED = "QA Failed"
STATUS_EDL_GENERATED = "EDL Generated"
STATUS_EDL_VALIDATED = "EDL Validated"
STATUS_APPROVED = "Approved"
STATUS_ERROR = "⚠️ Error"
STATUS_AWAITING_HUMAN = "⏸ Awaiting Human"


# ── Internal helpers ──────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _escape(s: str) -> str:
    """Escape single quotes for use in Airtable formula strings."""
    return s.replace("'", "\\'")


def _base():
    return Api(settings.airtable_api_key).base(settings.airtable_base_id)


def _tapes():
    return _base().table(settings.airtable_table_tapes)


def _transcripts():
    return _base().table(settings.airtable_table_transcripts)


def _edls():
    return _base().table(settings.airtable_table_edls)


def _log_table():
    return _base().table(settings.airtable_table_log)


def _find_tape(tape_id: str) -> dict:
    """Return the first Airtable record matching tape_id. Raises ValueError if missing."""
    records = _tapes().all(formula=f"{{Tape ID}}='{_escape(tape_id)}'")
    if not records:
        raise ValueError(f"Tape not found in Airtable: {tape_id!r}")
    return records[0]


def _find_edl(tape_id: str, edl_name: str) -> dict:
    records = _edls().all(
        formula=f"AND({{Tape ID}}='{_escape(tape_id)}', {{EDL Name}}='{_escape(edl_name)}')"
    )
    if not records:
        raise ValueError(f"EDL {edl_name!r} not found for tape {tape_id!r}")
    return records[0]


# ── Public API — do not change signatures ─────────────────────────────────────

def log(tape_id: str, operation: str, result: str, detail: str = "", operator: str = "system") -> None:
    """Append an entry to the Operation Log. Never updates or deletes existing entries."""
    try:
        _log_table().create({
            "Tape ID": tape_id,
            "Operation": operation,
            "Result": result,
            "Detail": detail,
            "Operator": operator,
            "Timestamp": _now(),
        })
    except Exception as exc:
        # Log failures must never crash the pipeline
        logger.error("Airtable log() failed: %s", exc)


def set_tape_status(tape_id: str, status: str, notes: str = "") -> None:
    """Update the Status field on a tape record. Called on every step and on errors."""
    record = _find_tape(tape_id)
    fields: dict = {"Status": status}
    if notes:
        fields["Notes"] = notes
    _tapes().update(record["id"], fields)


def create_tape(tape_id: str, original_filename: str, checksum: str) -> dict:
    """Register a new tape at intake. Returns {"record_id": str, "tape_id": str}."""
    record = _tapes().create({
        "Tape ID": tape_id,
        "Original Filename": original_filename,
        "Checksum": checksum,
        "Status": STATUS_INTAKE,
        "Created At": _now(),
    })
    log(tape_id, "intake", "✅ Success", f"Registered {original_filename}")
    return {"record_id": record["id"], "tape_id": tape_id}


def get_tape(tape_id: str) -> dict:
    """Return the full Airtable record dict for a tape. Raises ValueError if not found."""
    return _find_tape(tape_id)


def mark_renamed(tape_id: str, new_filename: str) -> None:
    """Record the standardized filename after the rename step."""
    record = _find_tape(tape_id)
    _tapes().update(record["id"], {
        "New Filename": new_filename,
        "Status": STATUS_RENAMED,
    })
    log(tape_id, "rename", "✅ Success", f"→ {new_filename}")


def mark_metadata_done(tape_id: str, date: str, location: str, context: str, set_by: str) -> None:
    """Record that metadata has been embedded into the output copy."""
    record = _find_tape(tape_id)
    _tapes().update(record["id"], {
        "Date": date,
        "Location": location,
        "Context": context,
        "Set By": set_by,
        "Status": STATUS_METADATA_DONE,
    })
    log(tape_id, "metadata_embed", "✅ Success", f"Set by {set_by}")


def create_transcript(tape_id: str, srt_filename: str, model: str, word_count: int) -> dict:
    """Create a Transcript record and advance tape status to Transcribed."""
    record = _transcripts().create({
        "Tape ID": tape_id,
        "SRT Filename": srt_filename,
        "Model": model,
        "Word Count": word_count,
        "Status": STATUS_TRANSCRIBED,
        "Created At": _now(),
    })
    set_tape_status(tape_id, STATUS_TRANSCRIBED)
    log(tape_id, "transcribe", "✅ Success", f"{srt_filename} — {word_count} words")
    return {"record_id": record["id"]}


def flag_bad_audio(tape_id: str, detail: str) -> None:
    """Mark tape as Error and log pipeline halt. Requires human intervention."""
    set_tape_status(tape_id, STATUS_ERROR, notes=detail)
    log(tape_id, "audio_check", "⚠️ Error", detail)
    log(tape_id, "pipeline_halt", STATUS_AWAITING_HUMAN, "Bad audio — manual review required")


def mark_qa_sampled(tape_id: str, passed: bool, notes: str = "") -> None:
    """Record QA sampling result: QA Passed or QA Failed."""
    status = STATUS_QA_PASSED if passed else STATUS_QA_FAILED
    set_tape_status(tape_id, status, notes=notes)
    emoji = "✅ Success" if passed else "⚠️ Error"
    log(tape_id, "qa_sample", emoji, notes or status)


def create_edl(tape_id: str, edl_name: str, theme: str, clip_count: int, frame_rate: str, generated_by: str) -> dict:
    """Create an EDL record and advance tape status to EDL Generated."""
    record = _edls().create({
        "Tape ID": tape_id,
        "EDL Name": edl_name,
        "Theme": theme,
        "Clip Count": clip_count,
        "Frame Rate": frame_rate,
        "Generated By": generated_by,
        "Premiere Verified": False,
        "Approved": False,
        "Created At": _now(),
    })
    set_tape_status(tape_id, STATUS_EDL_GENERATED)
    log(tape_id, "generate_edl", "✅ Success", f"{edl_name} | {clip_count} clips | {theme}", generated_by)
    return {"record_id": record["id"]}


def validate_edl(tape_id: str, edl_name: str, premiere_ok: bool, notes: str = "") -> None:
    """Salvador validates that the EDL imports cleanly in Premiere Pro."""
    record = _find_edl(tape_id, edl_name)
    _edls().update(record["id"], {
        "Premiere Verified": premiere_ok,
        "Validation Notes": notes,
        "Validated At": _now(),
    })
    status = STATUS_EDL_VALIDATED if premiere_ok else STATUS_ERROR
    set_tape_status(tape_id, status, notes=notes)
    emoji = "✅ Success" if premiere_ok else "⚠️ Error"
    log(tape_id, "validate_edl", emoji, f"Premiere OK: {premiere_ok}. {notes}", "salvador")


def approve_edl(tape_id: str, edl_name: str) -> None:
    """Mark approves EDL for delivery. Premiere Verified must be True first.

    GUARDRAIL: Raises ValueError if Premiere Verified is not set — callers
               translate this to HTTP 400.
    """
    record = _find_edl(tape_id, edl_name)
    if not record["fields"].get("Premiere Verified", False):
        raise ValueError("EDL must be validated by Salvador before client approval.")
    _edls().update(record["id"], {
        "Approved": True,
        "Approved At": _now(),
    })
    set_tape_status(tape_id, STATUS_APPROVED)
    log(tape_id, "approve_edl", "✅ Success", f"{edl_name} approved", "mark")


def get_pending_intake() -> list[dict]:
    """Return tapes waiting for Mark's metadata form submission."""
    records = _tapes().all(formula="{Status}='Pending Intake'")
    return [r["fields"] for r in records]


def get_pipeline_status() -> dict:
    """Return aggregate status counts and tape list for the dashboard."""
    all_tapes = _tapes().all()
    tapes = []
    for r in all_tapes:
        f = r["fields"]
        tapes.append({
            "tape_id": f.get("Tape ID", ""),
            "original_filename": f.get("Original Filename", ""),
            "new_filename": f.get("New Filename", ""),
            "date": f.get("Date", ""),
            "location": f.get("Location", ""),
            "status": f.get("Status", ""),
        })

    total = len(tapes)
    complete = sum(1 for t in tapes if t["status"] == STATUS_APPROVED)
    errors = sum(1 for t in tapes if STATUS_ERROR in t["status"])
    awaiting = sum(1 for t in tapes if STATUS_AWAITING_HUMAN in t["status"])
    in_progress = max(0, total - complete - errors - awaiting)

    return {
        "total": total,
        "complete": complete,
        "in_progress": in_progress,
        "errors": errors,
        "awaiting_human": awaiting,
        "tapes": tapes,
    }


def get_errors() -> list[dict]:
    """Return all tapes currently in an error state."""
    records = _tapes().all(formula="FIND('Error', {Status})")
    return [r["fields"] for r in records]


def get_awaiting_human() -> list[dict]:
    """Return all tapes paused awaiting human intervention."""
    records = _tapes().all(formula="FIND('Awaiting Human', {Status})")
    return [r["fields"] for r in records]
