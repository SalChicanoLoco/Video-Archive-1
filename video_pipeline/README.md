# Video Archive Processing Pipeline

This repository provides a complete containerised environment for processing H.264 (MP4) video files.  The pipeline performs standardised renaming, metadata embedding, audio extraction, time‑coded transcription using [faster‑whisper](https://github.com/guillaumekln/faster-whisper) and exposes a simple Flask API for orchestration.  The Docker image is designed to run efficiently on both x86 and Apple Silicon (arm64) hosts and includes a predownloaded Whisper **large‑v3** model so that transcription works on the first request without additional downloads.

## Why these dependencies?

- **ffmpeg** – used for all media manipulation.  We install ffmpeg via `apt` because the official Debian package makes setup simple.  The UnderHost guide notes that on Debian (bookworm) ffmpeg can be installed with `apt update` followed by `apt install ffmpeg -y`【308060662158292†L187-L199】.  When embedding metadata we use the `-metadata` flag and `-codec copy` so that streams are not re‑encoded, preserving quality【545890140196842†L143-L175】.  For audio extraction we rely on `-vn` to ignore video and either `-acodec copy` or a PCM codec; the tinyapps article shows how `ffmpeg -i video.mp4 -vn -acodec copy audio.m4a` extracts audio without re‑encoding【165115472084467†L9-L16】, while UnderHost demonstrates using `-q:a 0 -map a` for high‑quality MP3 extraction【308060662158292†L216-L219】.
- **libsndfile1** – required by audio libraries such as **pydub** and **soundfile** to read/write WAV and other audio formats【321951324672017†L49-L64】.
- **faster‑whisper** – a drop‑in replacement for OpenAI’s Whisper that is optimised for CPU inference.  The library uses CTranslate2 and does not depend on ffmpeg because audio decoding is handled via PyAV【904580658027665†L150-L156】.  You instantiate a `WhisperModel` and call `model.transcribe` with parameters such as `beam_size`, `vad_filter` and `word_timestamps`【904580658027665†L227-L239】【904580658027665†L303-L320】.  We load the model once at start‑up to avoid repeated downloads and set `beam_size=5`, `vad_filter=True` as recommended.
- **Flask & Gunicorn** – provide a lightweight web framework and a production‑grade WSGI server.  The latest Flask version (`3.1.3`) was released on 2026‑02‑18【357769048210266†L25-L33】, while Gunicorn `25.3.0` (2026‑03‑26) offers robust worker management【509562318137200†L29-L36】.  We run Gunicorn with two workers and four threads for concurrency.
- **Other Python libraries** – pinned to stable versions from their PyPI pages: `ffmpeg-python==0.2.0`【605022600950048†L29-L36】, `pydub==0.25.1`【584713412733312†L25-L33】, `srt==3.5.3`【960426035313273†L25-L34】, `python-dateutil==2.9.0.post0`【28462305698625†L25-L33】, `requests==2.33.1`【680507163322713†L25-L33】, `pyairtable==3.3.0`【432478653367461†L25-L33】 and `python-dotenv==1.2.2`【892615089904154†L25-L33】.

## Project Structure

```
.
├── Dockerfile           # Multi‑stage build with preloaded Whisper model
├── docker-compose.yml    # Compose service with named volumes
├── requirements.txt       # Pinned Python dependencies
├── .env.example          # Template for environment variables
├── app/
│   ├── __init__.py       # Logging configuration
│   ├── app.py            # Flask API with endpoints
│   └── pipeline/
│       ├── utils.py      # Helpers for paths and filenames
│       ├── rename.py     # File renaming logic
│       ├── metadata.py   # Metadata embedding via ffmpeg
│       ├── audio.py      # Audio extraction via ffmpeg
│       └── transcribe.py # Transcription via faster‑whisper
├── test_pipeline.sh      # End‑to‑end test script
└── README.md             # This file
```

## Build and Run

1. **Prepare environment variables** – copy `.env.example` to `.env` and adjust values if needed (e.g., set `WHISPER_MODEL_SIZE=large-v3`).

2. **Build the Docker image** (requires Docker Desktop and buildx):
   ```bash
   docker compose build
   ```
   This step installs system packages, Python dependencies and downloads the Whisper model into the `models` volume.

3. **Start the service**:
   ```bash
   docker compose up
   ```
   The API will listen on `localhost:5000`.  Logs are emitted in JSON format to stdout and captured by Docker.

4. **Test the pipeline**:
   ```bash
   docker compose exec app bash test_pipeline.sh
   ```
   The script downloads a sample video, exercises each endpoint and prints PASS/FAIL for each step.  Output files (renamed video, extracted audio and SRT transcript) will appear in the `output` volume and can be inspected on the host via Docker Desktop or by running `docker compose exec app ls /app/output`.

## API Endpoints

| Method | Path             | Description |
|-------:|------------------|-------------|
| `GET`  | `/health`        | Returns service status and whether the Whisper model is loaded. |
| `POST` | `/rename`        | JSON body: `{path, new_name}` → renames a file in `/app/input` and returns `{new_path}`. |
| `POST` | `/embed-metadata`| JSON body: `{path, title, date, comment}` → writes metadata tags using ffmpeg `-metadata` and returns `{path}`. |
| `POST` | `/extract-audio` | JSON body: `{path, format}` (`wav` or `mp3`) → extracts audio and returns `{audio_path}`. |
| `POST` | `/transcribe`    | JSON body: `{audio_path, model_size}` → starts an asynchronous transcription job and returns `{job_id}`.  Poll `/jobs/<job_id>` to obtain status and SRT path. |
| `GET`  | `/jobs/<id>`     | Returns the status of a transcription job: `queued`, `running`, `finished` or `failed`.  When finished, the response includes the SRT path. |
| `POST` | `/process`       | JSON body: `{path, new_name?, title?, date?, comment?}` → runs the full pipeline synchronously (rename → embed metadata → extract audio → transcribe) and returns a dictionary with paths to the renamed file, audio and SRT transcript. |

## Troubleshooting

* **Long build times / large image** – downloading the Whisper `large‑v3` model can take several minutes and uses around 2.9 GB of space.  You can choose a smaller model by setting `WHISPER_MODEL_SIZE` in your `.env` file, e.g. `base` or `small`.  Be aware that accuracy may decrease.
* **Permission errors on Mac volumes** – Docker Desktop on macOS may mount named volumes with root ownership.  Our Dockerfile creates a non‑root user (`pipeline`) and sets ownership of `/app` so that read/write works correctly.  If you still encounter permission errors, ensure your host user has rights to the Docker volumes or adjust the volume mapping in `docker-compose.yml`.
* **ffmpeg missing codecs** – the Debian ffmpeg build included in this image supports H.264 and common audio formats.  If you encounter unsupported formats, ensure the input files are H.264 MP4s as expected or extend the image to include additional codecs.
* **Whisper model download fails** – network issues can interrupt model download during `docker compose build`.  In that case, rerun the build; Docker will resume downloading layers.  Alternatively, you can mount a pre‑downloaded model into the `models` volume at `/app/models`.

## License

This project is provided as‑is for demonstration purposes.  Consult the licenses of the individual dependencies (ffmpeg, faster‑whisper, Flask, etc.) for details.