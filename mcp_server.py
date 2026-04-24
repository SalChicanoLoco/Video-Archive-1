#!/usr/bin/env python3
"""
Video Archive Pipeline — MCP Server

Exposes pipeline setup and management as MCP tools so Claude can
orchestrate the full environment setup conversationally.

Auto-registered by setup.sh via .mcp.json at the repo root.
When you run `claude` in this directory, these tools are available.

Tools:
  check_environment   — verify Docker, git, dirs, .env, port
  connect_airtable    — save credentials to .env and test connection
  start_pipeline      — docker compose up -d + health poll
  stop_pipeline       — docker compose down
  pipeline_status     — full status: containers, Airtable, Anthropic key
  process_batch       — transcribe + EDL all MP4s in input dir
  get_logs            — tail container logs
  reload_config       — tell running pipeline to refresh from Airtable
  set_env_var         — write/update any key in video_pipeline/.env
"""

import json
import os
import re
import socket
import subprocess
import time
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# ── Paths ─────────────────────────────────────────────────────────────────────
REPO_ROOT    = Path(__file__).parent.resolve()
PIPELINE_DIR = REPO_ROOT / "video_pipeline"
ENV_FILE     = PIPELINE_DIR / ".env"
BATCH_SCRIPT = PIPELINE_DIR / "process_batch.sh"
COMPOSE_FILE = PIPELINE_DIR / "docker-compose.yml"
API_URL      = "http://localhost:5000"

mcp = FastMCP("video-archive-pipeline")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _run(cmd: list[str], cwd: Path | None = None, timeout: int = 60) -> tuple[int, str]:
    """Run a subprocess and return (returncode, combined output)."""
    try:
        r = subprocess.run(
            cmd, cwd=cwd or PIPELINE_DIR,
            capture_output=True, text=True, timeout=timeout,
        )
        out = (r.stdout + r.stderr).strip()
        return r.returncode, out
    except subprocess.TimeoutExpired:
        return 1, f"Command timed out after {timeout}s: {' '.join(cmd)}"
    except FileNotFoundError:
        return 1, f"Command not found: {cmd[0]}"
    except Exception as exc:
        return 1, str(exc)


def _curl_get(path: str, timeout: int = 5) -> tuple[int, dict]:
    """GET the pipeline API; returns (http_status_or_-1, body_dict)."""
    try:
        import urllib.request
        with urllib.request.urlopen(f"{API_URL}{path}", timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except Exception as exc:
        return -1, {"error": str(exc)}


def _curl_post(path: str, body: dict, timeout: int = 10) -> tuple[int, dict]:
    """POST to the pipeline API."""
    try:
        import urllib.request, urllib.error
        data = json.dumps(body).encode()
        req = urllib.request.Request(
            f"{API_URL}{path}", data=data,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except Exception as exc:
        return -1, {"error": str(exc)}


def _read_env() -> dict[str, str]:
    """Parse video_pipeline/.env into a dict."""
    env: dict[str, str] = {}
    if not ENV_FILE.exists():
        return env
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip()
    return env


def _write_env(env: dict[str, str]) -> None:
    """Write dict back to .env, preserving comments from existing file."""
    existing_lines: list[str] = []
    if ENV_FILE.exists():
        existing_lines = ENV_FILE.read_text().splitlines()

    written_keys: set[str] = set()
    output_lines: list[str] = []

    for line in existing_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            output_lines.append(line)
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in env:
            output_lines.append(f"{key}={env[key]}")
            written_keys.add(key)
        else:
            output_lines.append(line)

    # Append any new keys not already in file
    for k, v in env.items():
        if k not in written_keys:
            output_lines.append(f"{k}={v}")

    ENV_FILE.write_text("\n".join(output_lines) + "\n")


def _port_open(host: str = "127.0.0.1", port: int = 5000) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


# ── Tools ─────────────────────────────────────────────────────────────────────

@mcp.tool()
def check_environment() -> str:
    """
    Check all prerequisites for the Video Archive Pipeline.

    Verifies: Docker installed + running, docker compose available,
    video_pipeline/ directory and Dockerfile present, input/output dirs,
    .env file exists with required keys, port 5000 availability.
    Returns a human-readable status report with PASS/FAIL per item.
    """
    lines: list[str] = ["=== Environment Check ===", ""]
    all_ok = True

    def check(label: str, ok: bool, detail: str = "") -> None:
        nonlocal all_ok
        status = "✓ PASS" if ok else "✗ FAIL"
        if not ok:
            all_ok = False
        line = f"  {status}  {label}"
        if detail:
            line += f" — {detail}"
        lines.append(line)

    # Docker daemon
    rc, out = _run(["docker", "info", "--format", "{{.ServerVersion}}"])
    check("Docker installed + running", rc == 0, f"v{out}" if rc == 0 else out[:120])

    # Docker Compose
    rc2, out2 = _run(["docker", "compose", "version", "--short"])
    check("docker compose plugin", rc2 == 0, out2[:80] if rc2 == 0 else out2[:120])

    # Pipeline directory
    check("video_pipeline/ exists", PIPELINE_DIR.is_dir())
    check("docker-compose.yml present", COMPOSE_FILE.is_file())
    check(
        "Dockerfile present",
        (PIPELINE_DIR / "Dockerfile").is_file(),
    )

    # Directories
    check("video_pipeline/input/ exists", (PIPELINE_DIR / "input").is_dir(),
          "run: mkdir -p video_pipeline/input" if not (PIPELINE_DIR / "input").is_dir() else "")
    check("video_pipeline/output/ exists", (PIPELINE_DIR / "output").is_dir(),
          "run: mkdir -p video_pipeline/output" if not (PIPELINE_DIR / "output").is_dir() else "")

    # .env
    env = _read_env()
    check(".env file exists", ENV_FILE.is_file(),
          "copy .env.example → .env" if not ENV_FILE.is_file() else "")
    check("AIRTABLE_API_KEY set", bool(env.get("AIRTABLE_API_KEY", "").strip()))
    check("AIRTABLE_BASE_ID set", bool(env.get("AIRTABLE_BASE_ID", "").strip()))

    # Port
    port_busy = _port_open()
    check("Port 5000 available (or pipeline already up)",
          True,  # always pass — just informational
          "pipeline is running" if port_busy else "free (pipeline not yet started)")

    # MP4 files to process
    mp4s = list((PIPELINE_DIR / "input").glob("*.mp4")) if (PIPELINE_DIR / "input").is_dir() else []
    lines.append("")
    lines.append(f"  ℹ  Input files ready: {len(mp4s)} MP4(s) in video_pipeline/input/")

    lines.append("")
    lines.append("All checks passed ✓" if all_ok else "Some checks failed — see FAIL items above.")
    return "\n".join(lines)


@mcp.tool()
def connect_airtable(api_key: str, base_id: str) -> str:
    """
    Save Airtable credentials to video_pipeline/.env and test the connection.

    Writes AIRTABLE_API_KEY and AIRTABLE_BASE_ID into .env, then asks the
    running pipeline to reload config. If the pipeline isn't up yet, tests
    the credentials directly via pyairtable.

    Args:
        api_key:  Airtable Personal Access Token (starts with 'pat')
        base_id:  Airtable Base ID (starts with 'app')
    """
    if not api_key.strip() or not base_id.strip():
        return "ERROR: Both api_key and base_id are required."

    # Save to .env
    if not ENV_FILE.exists():
        if (PIPELINE_DIR / ".env.example").exists():
            import shutil
            shutil.copy(PIPELINE_DIR / ".env.example", ENV_FILE)
        else:
            ENV_FILE.write_text("")

    env = _read_env()
    env["AIRTABLE_API_KEY"] = api_key.strip()
    env["AIRTABLE_BASE_ID"] = base_id.strip()
    _write_env(env)

    lines = ["Saved AIRTABLE_API_KEY and AIRTABLE_BASE_ID to .env"]

    # Try reloading via running pipeline first
    status, body = _curl_post("/setup/reload", {})
    if status != -1:
        lines.append(f"Pipeline reload response ({status}): {json.dumps(body)}")
        if body.get("airtable_connected"):
            lines.append("✓ Airtable connection confirmed via pipeline.")
            if body.get("anthropic_key_available"):
                lines.append("✓ Anthropic API key found in Airtable Config table.")
            else:
                lines.append(
                    "⚠  No ANTHROPIC_API_KEY found in Airtable yet.\n"
                    "   Add a row to your Airtable Config table:\n"
                    "     Key   = ANTHROPIC_API_KEY\n"
                    "     Value = sk-ant-..."
                )
        return "\n".join(lines)

    # Pipeline not running — test directly
    lines.append("Pipeline not running; testing Airtable directly...")
    try:
        from pyairtable import Api
        config_table = env.get("AIRTABLE_CONFIG_TABLE", "Config")
        table = Api(api_key.strip()).base(base_id.strip()).table(config_table)
        records = table.all()
        keys_found = [r["fields"].get("Key", "") for r in records if r["fields"].get("Key")]
        lines.append(f"✓ Connected. Config table '{config_table}' has {len(records)} row(s).")
        if keys_found:
            lines.append(f"  Keys found: {', '.join(keys_found)}")
        if "ANTHROPIC_API_KEY" not in keys_found:
            lines.append(
                "⚠  ANTHROPIC_API_KEY not in Config table yet.\n"
                "   Add it in Airtable: Key = ANTHROPIC_API_KEY, Value = sk-ant-..."
            )
        else:
            lines.append("✓ ANTHROPIC_API_KEY is present — EDL generation will be enabled.")
    except ImportError:
        lines.append("pyairtable not installed in this env (it IS in the Docker image).")
        lines.append("Credentials saved to .env — they will be tested when the pipeline starts.")
    except Exception as exc:
        lines.append(f"✗ Airtable connection failed: {exc}")
        lines.append("Double-check the token and base ID.")

    return "\n".join(lines)


@mcp.tool()
def start_pipeline() -> str:
    """
    Start the pipeline service with `docker compose up -d` and wait for /health.

    Builds the image if needed (first run takes ~10 min to download Whisper model).
    Polls /health for up to 3 minutes after containers start.
    Returns the health status when ready.
    """
    lines: list[str] = []

    # Check if already up
    status, body = _curl_get("/health")
    if status == 200:
        return f"Pipeline is already running. Health: {json.dumps(body)}"

    lines.append("Starting pipeline with docker compose up -d ...")
    rc, out = _run(["docker", "compose", "up", "-d", "--build"], timeout=900)
    if rc != 0:
        return f"docker compose up failed (exit {rc}):\n{out}"
    lines.append(out)

    # Poll /health
    lines.append("Waiting for /health ...")
    deadline = time.time() + 180
    while time.time() < deadline:
        s, b = _curl_get("/health", timeout=3)
        if s == 200:
            lines.append(f"✓ Pipeline ready. {json.dumps(b)}")
            # Also fire config load
            _curl_post("/setup/reload", {})
            return "\n".join(lines)
        time.sleep(5)

    lines.append("✗ Pipeline did not respond within 3 minutes.")
    lines.append("Check logs with: get_logs()")
    return "\n".join(lines)


@mcp.tool()
def stop_pipeline() -> str:
    """
    Stop the pipeline service with `docker compose down`.
    Data in input/ and output/ is preserved.
    """
    rc, out = _run(["docker", "compose", "down"], timeout=60)
    if rc == 0:
        return f"Pipeline stopped.\n{out}"
    return f"docker compose down failed (exit {rc}):\n{out}"


@mcp.tool()
def pipeline_status() -> str:
    """
    Full status report: container state, /health API, Airtable connection,
    Anthropic key availability, MP4 count in input/, SRT/EDL count in output/.
    """
    lines: list[str] = ["=== Pipeline Status ===", ""]

    # Container state
    rc, out = _run(["docker", "compose", "ps", "--format", "json"])
    if rc == 0 and out.strip():
        try:
            containers = json.loads(out) if out.startswith("[") else [json.loads(out)]
            for c in containers:
                name   = c.get("Name", c.get("Service", "?"))
                state  = c.get("State", c.get("Status", "?"))
                health = c.get("Health", "")
                lines.append(f"  Container: {name}  state={state}  health={health}")
        except Exception:
            lines.append(f"  Containers: {out[:200]}")
    else:
        lines.append("  Containers: not running (or docker compose ps failed)")

    lines.append("")

    # API health
    status, body = _curl_get("/health")
    if status == 200:
        lines.append(f"  API /health: ✓  {json.dumps(body)}")
    else:
        lines.append(f"  API /health: ✗  ({body.get('error', 'unreachable')})")

    # Config status from pipeline
    cs, cb = _curl_get("/setup", timeout=5)
    # /setup returns HTML — try /health which has basic info
    # Instead POST to /setup/reload to get JSON status indirectly
    # Actually we parse the .env directly here for a quick report
    env = _read_env()
    lines.append(f"  Airtable key in .env: {'✓' if env.get('AIRTABLE_API_KEY') else '✗ (not set)'}")
    lines.append(f"  Airtable base in .env: {'✓' if env.get('AIRTABLE_BASE_ID') else '✗ (not set)'}")

    # Try reload to get live status
    if status == 200:
        rs, rb = _curl_post("/setup/reload", {}, timeout=8)
        if rs != -1 and isinstance(rb, dict):
            lines.append(f"  Airtable connected: {'✓' if rb.get('airtable_connected') else '✗'}")
            lines.append(f"  Anthropic key:      {'✓ (EDL enabled)' if rb.get('anthropic_key_available') else '✗ (SRT-only mode)'}")

    lines.append("")

    # File counts
    input_dir  = PIPELINE_DIR / "input"
    output_dir = PIPELINE_DIR / "output"
    mp4s  = list(input_dir.glob("*.mp4"))  if input_dir.is_dir()  else []
    srts  = list(output_dir.glob("*.srt")) if output_dir.is_dir() else []
    edls  = list(output_dir.glob("*.edl")) if output_dir.is_dir() else []
    wavs  = list(output_dir.glob("*.wav")) if output_dir.is_dir() else []
    lines.append(f"  Input  MP4s : {len(mp4s)}")
    lines.append(f"  Output SRTs : {len(srts)}")
    lines.append(f"  Output EDLs : {len(edls)}")
    lines.append(f"  Output WAVs : {len(wavs)}")

    return "\n".join(lines)


@mcp.tool()
def process_batch(input_dir: str = "") -> str:
    """
    Kick off batch processing: transcribe all MP4s and generate EDLs.

    Runs process_batch.sh in the background. Returns the log file path
    immediately — use get_logs() to tail progress. The job can run for
    hours on large files.

    Args:
        input_dir: Path to MP4 files visible to the HOST (not the container).
                   Defaults to video_pipeline/input/ if empty.
    """
    if not BATCH_SCRIPT.is_file():
        return f"Batch script not found: {BATCH_SCRIPT}"

    # Check pipeline is up
    s, _ = _curl_get("/health", timeout=3)
    if s != 200:
        return "Pipeline is not running. Call start_pipeline() first."

    target = input_dir.strip() if input_dir.strip() else str(PIPELINE_DIR / "input")

    # Ensure the directory exists
    if not Path(target).is_dir():
        return f"Directory not found: {target}"

    mp4s = list(Path(target).glob("*.mp4"))
    if not mp4s:
        return f"No MP4 files found in {target}"

    log_path = PIPELINE_DIR / f"batch_{int(time.time())}.log"

    proc = subprocess.Popen(
        ["bash", str(BATCH_SCRIPT), target],
        cwd=PIPELINE_DIR,
        stdout=open(log_path, "w"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )

    return (
        f"Batch job started (PID {proc.pid}) — processing {len(mp4s)} MP4(s).\n"
        f"Log file: {log_path}\n"
        f"Use get_logs() to watch progress (pipeline container logs).\n"
        f"Results will appear in video_pipeline/output/"
    )


@mcp.tool()
def get_logs(lines: int = 60) -> str:
    """
    Tail the most recent lines from the pipeline container logs.

    Args:
        lines: Number of log lines to return (default 60).
    """
    rc, out = _run(
        ["docker", "compose", "logs", "--no-log-prefix", f"--tail={lines}"],
        timeout=15,
    )
    if rc != 0:
        return f"docker compose logs failed:\n{out}"
    return out or "(no log output yet)"


@mcp.tool()
def reload_config() -> str:
    """
    Tell the running pipeline to refresh its config from Airtable.

    Useful after adding or updating keys in the Airtable Config table
    without restarting the container.
    Returns the updated config status (Airtable connected, Anthropic key present, etc.).
    """
    s, b = _curl_get("/health", timeout=3)
    if s != 200:
        return "Pipeline is not running — start it first with start_pipeline()."

    rs, rb = _curl_post("/setup/reload", {}, timeout=15)
    if rs == -1:
        return f"Reload request failed: {rb.get('error', 'unknown')}"

    lines = [f"Config reloaded (HTTP {rs})."]
    if isinstance(rb, dict):
        lines.append(f"  Airtable connected: {'✓' if rb.get('airtable_connected') else '✗'}")
        lines.append(f"  Anthropic key:      {'✓ (EDL enabled)' if rb.get('anthropic_key_available') else '✗ (SRT-only)'}")
        keys = rb.get("config_keys_found", [])
        if keys:
            lines.append(f"  Config keys in Airtable: {', '.join(keys)}")
    return "\n".join(lines)


@mcp.tool()
def set_env_var(key: str, value: str) -> str:
    """
    Write or update a key in video_pipeline/.env.

    Use this to set any environment variable the pipeline reads
    (e.g. WHISPER_MODEL_SIZE, EDL_THEME, EDL_CRITERIA).
    Credentials should be set via connect_airtable() instead.

    Args:
        key:   Environment variable name (e.g. WHISPER_MODEL_SIZE)
        value: New value
    """
    if not key.strip():
        return "ERROR: key cannot be empty."

    # Guard against accidentally overwriting credential keys this way
    sensitive = {"AIRTABLE_API_KEY", "AIRTABLE_BASE_ID", "ANTHROPIC_API_KEY"}
    if key.strip().upper() in sensitive:
        return (
            f"Use connect_airtable() to set credentials, not set_env_var().\n"
            f"ANTHROPIC_API_KEY should live in the Airtable Config table."
        )

    if not ENV_FILE.exists():
        return f".env file not found at {ENV_FILE}. Run check_environment() first."

    env = _read_env()
    old = env.get(key.strip(), "(not set)")
    env[key.strip()] = value.strip()
    _write_env(env)

    return f"Set {key} = {value!r}  (was: {old!r})\nRestart the pipeline for changes to take effect."


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
