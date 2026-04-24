"""
Main Flask application for the video processing pipeline.

The app exposes a REST API with endpoints for renaming files,
embedding metadata, extracting audio, transcribing audio and
orchestrating the full processing pipeline. The Whisper model is
initialised once at startup to avoid repeated downloads and heavy
loading on each request. Background jobs are tracked via a simple
in‑memory dictionary keyed by a UUID.
"""

import os
import uuid
import threading
from datetime import datetime

from flask import Flask, request, jsonify
from markupsafe import escape

from .pipeline import utils as app_utils
from . import config_store
from .pipeline import rename as rename_module
from .pipeline import metadata as metadata_module
from .pipeline import audio as audio_module
from .pipeline import transcribe as transcribe_module
from .pipeline import edl as edl_module

try:
    from faster_whisper import WhisperModel
except ImportError:
    # During documentation builds or testing outside Docker we may not
    # have faster-whisper installed. In that case we stub out the
    # import to avoid crashing.
    WhisperModel = None


def create_app():
    """Factory to create and configure the Flask app."""
    app = Flask(__name__)

    # Load configuration from environment variables
    whisper_size = os.getenv("WHISPER_MODEL_SIZE", "large-v3")
    beam_size = int(os.getenv("WHISPER_BEAM_SIZE", "5"))
    vad_filter = os.getenv("WHISPER_VAD_FILTER", "true").lower() in {"1", "true", "yes"}

    # In‑memory job store
    jobs = {}

    # Pull config (including ANTHROPIC_API_KEY) from Airtable at startup.
    # Runs in a background thread so it never blocks the first request.
    threading.Thread(target=config_store.load, daemon=True).start()

    _whisper_lock = threading.Lock()

    def _ensure_whisper_model():
        """Load Whisper model on first use (thread-safe)."""
        if hasattr(app, "whisper_model"):
            return
        with _whisper_lock:
            if hasattr(app, "whisper_model"):
                return
            if WhisperModel is None:
                app.logger.warning("faster-whisper is not installed; transcription will not work")
                return
            app.logger.info("Loading Whisper model: %s", whisper_size)
            app.whisper_model = WhisperModel(whisper_size, device="cpu", compute_type="int8")
            app.logger.info("Whisper model loaded")

    @app.route("/health", methods=["GET"])
    def health():
        """Return health information about the API and model."""
        whisper_loaded = hasattr(app, "whisper_model") and app.whisper_model is not None
        return jsonify({"status": "ok", "whisper": whisper_loaded}), 200

    @app.route("/rename", methods=["POST"])
    def rename_endpoint():
        data = request.get_json(force=True, silent=True) or {}
        path = data.get("path")
        new_name = data.get("new_name")
        if not path or not new_name:
            return jsonify({"error": "path and new_name fields are required"}), 400
        try:
            validated = app_utils.validate_input_path(path)
            new_path = rename_module.rename_file(validated, new_name)
            return jsonify({"new_path": new_path}), 200
        except Exception as exc:
            app.logger.exception("Error renaming file")
            return jsonify({"error": str(exc)}), 500

    @app.route("/embed-metadata", methods=["POST"])
    def embed_metadata_endpoint():
        data = request.get_json(force=True, silent=True) or {}
        path = data.get("path")
        title = data.get("title") or ""
        date = data.get("date") or ""
        comment = data.get("comment") or ""
        if not path:
            return jsonify({"error": "path field is required"}), 400
        try:
            validated = app_utils.validate_input_path(path)
            new_path = metadata_module.embed_metadata(validated, title, date, comment)
            return jsonify({"path": new_path}), 200
        except Exception as exc:
            app.logger.exception("Error embedding metadata")
            return jsonify({"error": str(exc)}), 500

    @app.route("/extract-audio", methods=["POST"])
    def extract_audio_endpoint():
        data = request.get_json(force=True, silent=True) or {}
        path = data.get("path")
        fmt = data.get("format", "wav")
        if not path:
            return jsonify({"error": "path field is required"}), 400
        try:
            validated = app_utils.validate_input_path(path)
            audio_path = audio_module.extract_audio(validated, fmt)
            return jsonify({"audio_path": audio_path}), 200
        except Exception as exc:
            app.logger.exception("Error extracting audio")
            return jsonify({"error": str(exc)}), 500

    def run_transcription_job(job_id: str, audio_path: str, size: str):
        """Background worker function to perform transcription."""
        jobs[job_id]["status"] = "running"
        try:
            # Use specified model size if provided, otherwise default
            model = app.whisper_model
            # If model size differs, load a new model into a local variable
            if size and size != whisper_size:
                model = WhisperModel(size, device="cpu", compute_type="int8")
            srt_path = transcribe_module.transcribe_audio(
                audio_path,
                model=model,
                beam_size=beam_size,
                vad_filter=vad_filter,
                word_timestamps=False,
            )
            jobs[job_id]["status"] = "finished"
            jobs[job_id]["result"] = {"srt_path": srt_path}
        except Exception as exc:
            jobs[job_id]["status"] = "failed"
            jobs[job_id]["error"] = str(exc)
            app.logger.exception("Transcription job failed")

    @app.route("/transcribe", methods=["POST"])
    def transcribe_endpoint():
        _ensure_whisper_model()
        if not hasattr(app, "whisper_model"):
            return jsonify({"error": "Whisper model not loaded"}), 500
        data = request.get_json(force=True, silent=True) or {}
        audio_path = data.get("audio_path")
        model_size = data.get("model_size", whisper_size)
        if not audio_path:
            return jsonify({"error": "audio_path field is required"}), 400
        try:
            validated = app_utils.validate_input_path(audio_path, allow_output=True)
            job_id = str(uuid.uuid4())
            jobs[job_id] = {"status": "queued", "submitted": datetime.utcnow().isoformat() + "Z"}
            thread = threading.Thread(target=run_transcription_job, args=(job_id, validated, model_size))
            thread.daemon = True
            thread.start()
            return jsonify({"job_id": job_id}), 202
        except Exception as exc:
            app.logger.exception("Error starting transcription job")
            return jsonify({"error": str(exc)}), 500

    @app.route("/jobs/<job_id>", methods=["GET"])
    def job_status(job_id):
        job = jobs.get(job_id)
        if not job:
            return jsonify({"error": "job not found"}), 404
        return jsonify(job), 200

    @app.route("/generate-edl", methods=["POST"])
    def generate_edl_endpoint():
        """Generate a CMX 3600 EDL from an existing SRT file via Claude API."""
        data = request.get_json(force=True, silent=True) or {}
        srt_path = data.get("srt_path")
        tape_id = data.get("tape_id") or "TAPE"
        theme = data.get("theme") or os.getenv("EDL_THEME", "selects")
        criteria = data.get("criteria") or os.getenv(
            "EDL_CRITERIA",
            "Select the most significant, clearly spoken moments. "
            "Prefer complete thoughts over fragments.",
        )
        frame_rate = data.get("frame_rate", "30fps NDF")

        if not srt_path:
            return jsonify({"error": "srt_path field is required"}), 400
        try:
            edl_path = edl_module.generate_edl(
                srt_path=srt_path,
                tape_id=tape_id,
                theme=theme,
                criteria=criteria,
                frame_rate=frame_rate,
            )
            return jsonify({"edl_path": edl_path}), 200
        except RuntimeError as exc:
            # Missing API key or package — caller should know it's config, not a bug
            return jsonify({"error": str(exc)}), 503
        except Exception as exc:
            app.logger.exception("Error generating EDL")
            return jsonify({"error": str(exc)}), 500

    @app.route("/process", methods=["POST"])
    def process_endpoint():
        """Run the full pipeline synchronously on a single video file."""
        data = request.get_json(force=True, silent=True) or {}
        path = data.get("path")
        title = data.get("title") or ""
        date = data.get("date") or ""
        comment = data.get("comment") or ""
        if not path:
            return jsonify({"error": "path field is required"}), 400
        try:
            # Validate the input path
            validated = app_utils.validate_input_path(path)
            # Generate a standard name using a helper if none provided
            new_name = data.get("new_name") or app_utils.generate_standard_name(validated)
            renamed_path = rename_module.rename_file(validated, new_name)
            # Embed metadata
            metadata_module.embed_metadata(renamed_path, title, date, comment)
            # Extract audio
            audio_path = audio_module.extract_audio(renamed_path, "wav")
            # Transcribe synchronously
            _ensure_whisper_model()
            if not hasattr(app, "whisper_model"):
                return jsonify({"error": "Whisper model not loaded"}), 500
            srt_path = transcribe_module.transcribe_audio(
                audio_path,
                model=app.whisper_model,
                beam_size=beam_size,
                vad_filter=vad_filter,
                word_timestamps=False,
            )
            job_dict = {
                "renamed_path": renamed_path,
                "audio_path": audio_path,
                "srt_path": srt_path,
                "title": title,
                "date": date,
                "comment": comment,
                "edl_path": None,
            }

            # Generate EDL automatically if API key is present (checks Airtable then env)
            if config_store.get("ANTHROPIC_API_KEY"):
                tape_id = data.get("tape_id") or new_name.replace(".mp4", "")
                theme = data.get("theme") or os.getenv("EDL_THEME", "selects")
                criteria = data.get("criteria") or os.getenv(
                    "EDL_CRITERIA",
                    "Select the most significant, clearly spoken moments. "
                    "Prefer complete thoughts over fragments.",
                )
                try:
                    edl_path = edl_module.generate_edl(
                        srt_path=srt_path,
                        tape_id=tape_id,
                        theme=theme,
                        criteria=criteria,
                    )
                    job_dict["edl_path"] = edl_path
                except Exception as exc:
                    app.logger.warning("EDL generation skipped: %s", exc)
                    job_dict["edl_warning"] = str(exc)

            return jsonify(job_dict), 200
        except Exception as exc:
            app.logger.exception("Error processing file")
            return jsonify({"error": str(exc)}), 500

    # ── /setup wizard ────────────────────────────────────────────────────────

    _SETUP_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Pipeline Setup</title>
  <style>
    body{{font-family:system-ui,sans-serif;max-width:640px;margin:40px auto;padding:0 20px;color:#222}}
    h1{{font-size:1.6rem;margin-bottom:.25rem}}
    .subtitle{{color:#666;margin-bottom:2rem}}
    .card{{border:1px solid #ddd;border-radius:8px;padding:1.2rem;margin-bottom:1.2rem}}
    .card h2{{margin:0 0 .8rem;font-size:1rem;text-transform:uppercase;letter-spacing:.05em;color:#555}}
    .row{{display:flex;align-items:center;gap:.5rem;margin:.3rem 0}}
    .dot{{width:10px;height:10px;border-radius:50%;flex-shrink:0}}
    .green{{background:#22c55e}} .red{{background:#ef4444}} .gray{{background:#9ca3af}}
    label{{display:block;margin-bottom:.25rem;font-size:.9rem}}
    input[type=text]{{width:100%;padding:.5rem .75rem;border:1px solid #ccc;border-radius:6px;font-size:.95rem;box-sizing:border-box}}
    button{{padding:.5rem 1.2rem;border:none;border-radius:6px;cursor:pointer;font-size:.95rem}}
    .btn-primary{{background:#3b82f6;color:#fff}} .btn-primary:hover{{background:#2563eb}}
    .btn-secondary{{background:#e5e7eb;color:#222}} .btn-secondary:hover{{background:#d1d5db}}
    .msg{{margin-top:.75rem;padding:.6rem .9rem;border-radius:6px;font-size:.9rem}}
    .msg.ok{{background:#dcfce7;color:#166534}} .msg.err{{background:#fee2e2;color:#991b1b}}
    .keys{{font-size:.85rem;color:#555;margin-top:.4rem}}
    footer{{text-align:center;color:#9ca3af;font-size:.8rem;margin-top:2rem}}
  </style>
</head>
<body>
  <h1>Video Pipeline Setup</h1>
  <p class="subtitle">Configure API credentials. Keys are never stored on disk — they live in Airtable.</p>

  <div class="card">
    <h2>Airtable</h2>
    <div class="row">
      <div class="dot {at_color}"></div>
      <span>{at_label}</span>
    </div>
    {at_keys_html}
    <form method="POST" action="/setup/connect" style="margin-top:1rem">
      <label>Airtable Personal Access Token</label>
      <input type="text" name="airtable_api_key" placeholder="pat..." value="{at_key_display}">
      <label style="margin-top:.6rem">Base ID</label>
      <input type="text" name="airtable_base_id" placeholder="app..." value="{base_id_display}">
      <button class="btn-primary" type="submit" style="margin-top:.8rem">Connect / Test</button>
    </form>
    {at_msg_html}
  </div>

  <div class="card">
    <h2>Anthropic (Claude)</h2>
    <div class="row">
      <div class="dot {ant_color}"></div>
      <span>{ant_label}</span>
    </div>
    <p style="font-size:.85rem;color:#555;margin:.6rem 0 0">
      Add <code>ANTHROPIC_API_KEY</code> to the <strong>Config</strong> table in your Airtable base
      (Key column = <code>ANTHROPIC_API_KEY</code>, Value column = your key). Then click Reload.
    </p>
  </div>

  <div class="card">
    <h2>EDL Generation</h2>
    <div class="row">
      <div class="dot {edl_color}"></div>
      <span>{edl_label}</span>
    </div>
  </div>

  <form method="POST" action="/setup/reload">
    <button class="btn-secondary" type="submit">↻ Reload config from Airtable</button>
  </form>
  {reload_msg_html}

  <footer>Video Archive Pipeline · <a href="/health">/health</a></footer>
</body>
</html>"""

    def _build_setup_page(msg: str = "", msg_type: str = "ok", reload_msg: str = "") -> str:
        st = config_store.status()
        at_ok = st["airtable_connected"]
        ant_ok = st["anthropic_key_available"]
        edl_ok = st["edl_enabled"]

        at_color = "green" if at_ok else "red"
        at_label = f"Connected to base {escape(st['airtable_base_id'])}" if at_ok else "Not connected"
        ant_color = "green" if ant_ok else "gray"
        ant_label = "API key available" if ant_ok else "No key found — see instructions below"
        edl_color = "green" if edl_ok else "gray"
        edl_label = "Ready — EDL generation enabled" if edl_ok else "Disabled (Anthropic key required)"

        found_keys = st.get("config_keys_found", [])
        at_keys_html = (
            f'<div class="keys">Keys in Config table: {", ".join(escape(k) for k in found_keys) or "(none)"}</div>'
            if at_ok else ""
        )

        at_key_display = escape(os.getenv("AIRTABLE_API_KEY", ""))
        base_id_display = escape(st["airtable_base_id"] if st["airtable_base_id"] != "(not set)" else "")

        at_msg_html = f'<div class="msg {msg_type}">{escape(msg)}</div>' if msg else ""
        reload_msg_html = f'<div class="msg ok" style="margin-top:.6rem">{escape(reload_msg)}</div>' if reload_msg else ""

        return _SETUP_HTML.format(
            at_color=at_color, at_label=at_label, at_keys_html=at_keys_html,
            ant_color=ant_color, ant_label=ant_label,
            edl_color=edl_color, edl_label=edl_label,
            at_key_display=at_key_display, base_id_display=base_id_display,
            at_msg_html=at_msg_html, reload_msg_html=reload_msg_html,
        )

    @app.route("/setup", methods=["GET"])
    def setup_page():
        return _build_setup_page()

    @app.route("/setup/connect", methods=["POST"])
    def setup_connect():
        api_key = (request.form.get("airtable_api_key") or "").strip()
        base_id = (request.form.get("airtable_base_id") or "").strip()

        if api_key:
            os.environ["AIRTABLE_API_KEY"] = api_key
        if base_id:
            os.environ["AIRTABLE_BASE_ID"] = base_id

        result = config_store.reload()
        st = config_store.status()
        if st["airtable_connected"]:
            msg = f"Connected! Found {len(result)} config value(s)."
            msg_type = "ok"
        else:
            msg = "Could not connect. Check your token and base ID."
            msg_type = "err"

        return _build_setup_page(msg=msg, msg_type=msg_type)

    @app.route("/setup/reload", methods=["POST"])
    def setup_reload():
        result = config_store.reload()
        st = config_store.status()
        if st["airtable_connected"]:
            reload_msg = f"Reloaded {len(result)} value(s) from Airtable."
        else:
            reload_msg = "Reload attempted — Airtable not reachable (SRT-only mode)."
        return _build_setup_page(reload_msg=reload_msg)

    # ── end /setup ────────────────────────────────────────────────────────────

    return app


# Create app for gunicorn
app = create_app()