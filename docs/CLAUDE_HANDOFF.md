# Claude Code Handoff (Airtable Pipeline)

This repo exposes a queue-based transcription API suitable for Airtable automations and script actions.

## Core contract

- Enqueue: `POST /v1/transcribe` or `POST /v1/process`
- Poll one: `GET /v1/job/{job_id}`
- Poll events: `GET /v1/job/{job_id}/events`
- List jobs: `GET /v1/jobs`
- Intake upload: `POST /v1/intake` (multipart)
- Metrics: `GET /metrics`

## Error contract

All non-2xx errors return:

```json
{
  "code": "UNAUTHORIZED|NOT_FOUND|VALIDATION_ERROR|...",
  "message": "human-readable message",
  "details": {},
  "request_id": "trace-id"
}
```

## Airtable mapping recommendation

- `job_id` -> text field
- `status` -> single select
- `retry_count` -> number
- `max_retries` -> number
- `result_text` -> long text
- `error` -> long text
- `updated_at` -> datetime

For event timeline table:

- `job_id`
- `event`
- `timestamp`
- `detail`

## Suggested Claude tasks

1. Read table row needing transcription.
2. Call enqueue endpoint and store returned `job_id`.
3. Poll `/v1/job/{job_id}` on schedule.
4. Optionally ingest `/v1/job/{job_id}/events` for audit timeline.
5. On `succeeded`, write transcript back to Airtable.
6. On `failed`, write `error`, `retry_count`, and `request_id`.

## Auth

If `API_KEY` is set, include header:

```http
x-api-key: <API_KEY>
```
