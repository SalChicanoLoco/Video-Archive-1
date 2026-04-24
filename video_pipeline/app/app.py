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

from . import utils as app_utils
from .pipeline import rename as rename_module
from .pipeline import metadata as metadata_module
from .pipeline import audio as audio_module
from .pipeline import transcribe as transcribe_module

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

    # Preload the Whisper model when the first request arrives. Using
    # before_first_request avoids the overhead during the WSGI app
    # import. The model object is stored on the Flask app for reuse.
    @app.before_first_request
    def load_whisper_model():
        if WhisperModel is None:
            app.logger.warning("faster-whisper is not installed; transcription will not work")
            return
        app.logger.info(f"Loading Whisper model: {whisper_size}")
        # Use int8 compute type on CPU to reduce RAM usage
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
            }
            return jsonify(job_dict), 200
        except Exception as exc:
            app.logger.exception("Error processing file")
            return jsonify({"error": str(exc)}), 500

    return app


# Create app for gunicorn
app = create_app()