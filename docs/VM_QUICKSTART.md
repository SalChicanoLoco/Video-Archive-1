# Ubuntu VM Quickstart (5-minute bootstrap)

This is an isolated, non-destructive path for spinning up the stack quickly on a fresh Ubuntu VM.

## 1) Clone repo

```bash
git clone <YOUR_REPO_URL>
cd Video-Archive-1
```

## 2) Install prerequisites

```bash
sudo bash scripts/bootstrap_ubuntu.sh
```

Then re-login once after docker group changes:

```bash
sudo usermod -aG docker "$USER"
# logout/login (or reboot) once, then continue
```

## 3) Start stack

```bash
bash scripts/run_stack.sh
```

Service URL:

- `http://127.0.0.1:8000`

## 4) Optional smoke check

```bash
bash scripts/smoke.sh
```

## 5) Stop stack

```bash
docker compose down
```
