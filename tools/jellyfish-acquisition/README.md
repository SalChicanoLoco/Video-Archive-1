# NUMARA JELLYFISH: Acquisition + Validation Agent (v0.4)

**Status:** code/tests prepared; internet acquisition and remote scheduled execution NOT verified until the GitHub workflow is merged and run. Never infer atmospheric variables from these archival gates.

This add-only component belongs under `tools/jellyfish-acquisition` in the existing `Video-Archive-1` repo; it does not alter the existing FastAPI application.

## What actually works

1. Ingest five **pinned official CRS-35 Space Force photographs** by identifying the originals through Wikimedia Commons' public MediaWiki API (`imageinfo`).
2. Download only HTTPS media from exact allowed hostnames, enforcing redirect allowlist, max 40 MiB, timeout, and bounded reads.
3. Cross-validate mission/date/photo ID, MIME, file size, MediaWiki upstream SHA-1 (base36), JPEG decode and dimensions. The SHA-1 is from the same distribution system; it is a transit check, not an independent authenticity proof.
4. Compute SHA-256; write immutable content-addressed raw archive plus JSON manifests. Scientific validation remains BLOCKED until calibrated.
5. Archive public media as **GitHub Release assets**, requiring no account secrets beyond the GitHub Actions `GITHUB_TOKEN`. It is a cloud object store for this public experiment, not a private bucket. Release tag `CRS-35_2026-10-13`. Assets named after SHA-256, never clobbered.
6. Optional Google Cloud Storage backend uses Application Default Credentials and generation preconditions; requires externally configured bucket and workload identity.
7. Run scheduled daily checks once the pull request is merged into the default branch (GitHub schedule will not run on a PR branch). Schedule triggers can be delayed or disabled for inactivity by GitHub.

## Access and privacy

Public GitHub repository -> **public** release assets; upload only vetted U.S. government public-domain material. NASA/independent CC imagery excluded by default. Internal research annotations stay in the separately created private Google Drive evidence vault until a cloud-backend integration is approved. GitHub data acquisition cannot authenticate to the user's Drive connector automatically; a Drive folder alone does not confer programmatic access. Do NOT put Google OAuth tokens or JSON service-account keys in repo.

## Scientific status

`RAW_OBSERVED_UNCALIBRATED` means the camera-produced image bytes were archived and passed byte/metadata checks, NOT that a vortex/altitude/wind was measured. EXIF clocks lack verified UTC offset. Missing camera pose, exposure/original RAW, plume phase, solar model, feature persistence, independent holdout, and error bars block research promotion.

## Future discovery / DVIDS direct access

DVIDS has a documented JSON search API (`https://api.dvidshub.net/docs/search_api`) but requires API key. Use it for **candidate discovery only**; newly discovered items require mission/date/license checks and must first enter quarantine/review, not auto-download into scientific data. Wikimedia Commons `imageinfo` provides immediate acquisition of already-vetted public images.

## To enable

Submit the PR to the repository default branch, then in GitHub Actions run `NUMARA Jellyfish media acquisition` with **Run workflow** (or wait for daily schedule). View public cloud archive in **Releases**. Scheduled runs may not happen exactly at 13:21 UTC. If Release writes fail due GitHub repo policy or token permissions, see audit artifact; no fake success is recorded. Optional private object storage: create dedicated GCS bucket and configure WIF, then change workflow storage mode to GCS.

## Testing

```
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m agent.acquire --config config/crs35.json --out runtime --storage local
```

No local fixture is labeled real observational evidence; tests mock the source bytes and image metadata.

## Canonical graph

Append-only extension from v0.1/v0.2/v0.3. Raw blobs -> manifest -> gates -> quarantined/uncalibrated -> calibrated observations -> independent null test -> scientific model. No promotion of physical claims without calibration and evidence.
