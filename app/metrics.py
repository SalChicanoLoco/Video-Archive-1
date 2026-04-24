from __future__ import annotations

from collections import Counter
from threading import Lock

_lock = Lock()
_request_total = 0
_request_by_status: Counter[int] = Counter()
_job_events: Counter[str] = Counter()


def inc_request(status_code: int) -> None:
    global _request_total
    with _lock:
        _request_total += 1
        _request_by_status[status_code] += 1


def inc_job_event(event: str) -> None:
    with _lock:
        _job_events[event] += 1


def render_prometheus() -> str:
    with _lock:
        lines: list[str] = [
            "# HELP app_requests_total Total HTTP requests handled",
            "# TYPE app_requests_total counter",
            f"app_requests_total {_request_total}",
            "# HELP app_requests_by_status_total HTTP requests by response status",
            "# TYPE app_requests_by_status_total counter",
        ]
        for status, count in sorted(_request_by_status.items()):
            lines.append(f'app_requests_by_status_total{{status="{status}"}} {count}')

        lines.extend(
            [
                "# HELP app_job_events_total Job lifecycle event counters",
                "# TYPE app_job_events_total counter",
            ]
        )
        for event, count in sorted(_job_events.items()):
            lines.append(f'app_job_events_total{{event="{event}"}} {count}')

    return "\n".join(lines) + "\n"
