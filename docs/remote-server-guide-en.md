# Remote Server Guide

This guide shows how to run FlowScribe as a remote transcription server and how
Windows clients connect to it from the CLI or GUI.

Use this workflow when:

- the Windows client should stay lightweight
- you want one shared server for URL downloads and transcription
- you need server-side cookies for login-required URL media
- you want finished artifacts downloaded back into the local client workspace

See also:

- [server-configuration.md](server-configuration.md)
- [agent-api.md](agent-api.md)

## What Changed

Recent remote-execution improvements:

- CLI and GUI can both target a saved remote server profile or a raw base URL
- server profiles can store a bearer token and a server-side `cookies.txt` path
- remote artifact download now uses a server-managed staging directory instead
  of reusing a client-local path
- the HTTP control plane is threaded, so status and event requests stay
  responsive during a long transcription
- heavy remote transcription is still limited to one active task by default, so
  low-memory hosts fail fast with HTTP `429` instead of overcommitting memory

## Architecture

Typical flow:

1. The Windows client submits one job to `/v1/tasks`.
2. If the source is a local file, the client uploads it to `/v1/uploads`.
3. The server downloads URL media or resolves the uploaded file locally.
4. The server runs transcription and writes artifacts into its own output area.
5. If artifact download is enabled, the client downloads result files back to
   its local output directory.

For remote URL media, the optional `remote_cookies_path` is resolved on the
server, not on the client.

## Server Prerequisites

Example target host:

- Ubuntu 24.04
- Python 3.10+
- `ffmpeg` available on `PATH`
- enough disk space for media downloads, work files, and transcript artifacts

Suggested model starting points:

- `tiny` for 2-core / 2 GB servers
- `small` for normal remote use when you can spend more memory and time
- `native-engine` only after you have already validated the server runtime,
  model path, and accuracy trade-offs for your own workload

## Server Setup On Ubuntu

Install base packages:

```bash
sudo apt update
sudo apt install -y git ffmpeg python3 python3-venv
```

Clone and create a virtual environment:

```bash
git clone https://github.com/Ducker-Fry/FlowScribe.git
cd FlowScribe
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

Create server-owned directories:

```bash
mkdir -p ~/flowscribe/config
mkdir -p ~/flowscribe/out
mkdir -p ~/.flowscribe-secrets
```

Optional: place a Netscape-format cookie file on the server for sites that need
logged-in URL access:

```bash
cp /path/to/cookies.txt ~/.flowscribe-secrets/bilibili.cookies.txt
chmod 600 ~/.flowscribe-secrets/bilibili.cookies.txt
```

Download a starting model:

```bash
source .venv/bin/activate
export FLOWSCRIBE_CONFIG_DIR="$HOME/flowscribe/config"
flowscribe model download tiny
```

Run a quick health check:

```bash
flowscribe doctor
```

## Start The Remote Server

Foreground example:

```bash
source .venv/bin/activate
export FLOWSCRIBE_CONFIG_DIR="$HOME/flowscribe/config"
flowscribe serve \
  --host 0.0.0.0 \
  --port 8765 \
  --api-token CHANGE_ME \
  -o "$HOME/flowscribe/out" \
  --format txt,md,json \
  -m tiny \
  --task-retention-hours 24
```

Recommended defaults for small hosts:

- start with `-m tiny`
- keep the default single active remote task
- watch free disk space under the output directory and `/tmp`

## Optional systemd Service

Example unit file:

```ini
[Unit]
Description=FlowScribe remote server
After=network.target

[Service]
Type=simple
User=fry
WorkingDirectory=/home/fry/FlowScribe
Environment=FLOWSCRIBE_CONFIG_DIR=/home/fry/flowscribe/config
ExecStart=/home/fry/FlowScribe/.venv/bin/flowscribe serve --host 0.0.0.0 --port 8765 --api-token CHANGE_ME -o /home/fry/flowscribe/out --format txt,md,json -m tiny --task-retention-hours 24
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

After writing the unit:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now flowscribe.service
sudo systemctl status flowscribe.service
```

## Validate The Server

From any client that can reach the host:

```powershell
Invoke-WebRequest `
  -Uri http://SERVER_IP:8765/v1/server `
  -Headers @{ Authorization = "Bearer CHANGE_ME" } |
  Select-Object -ExpandProperty Content
```

Expected:

- an HTTP `200`
- JSON showing server name, version, retention, and capabilities

## Connect From The CLI

Create a saved remote server profile:

```powershell
flowscribe remote add-server prod-linux `
  --url http://SERVER_IP:8765 `
  --token CHANGE_ME `
  --remote-cookies-path /home/fry/.flowscribe-secrets/bilibili.cookies.txt `
  --timeout 30 `
  --download-artifacts
```

Inspect it:

```powershell
flowscribe remote list-servers
flowscribe remote show-server prod-linux
```

Run a remote local-file transcription:

```powershell
flowscribe transcribe "D:\media\lecture.mp4" `
  --execution remote `
  --server prod-linux `
  -o .\client-out `
  --format json `
  --json `
  --non-interactive
```

Run a remote URL transcription:

```powershell
flowscribe url "https://www.bilibili.com/video/BV1PC4y1G7T5/" `
  --execution remote `
  --server prod-linux `
  -o .\client-out-url `
  --format txt,md,json `
  --json `
  --non-interactive
```

Useful follow-up commands:

```powershell
flowscribe remote status prod-linux TASK_ID
flowscribe remote events prod-linux TASK_ID
flowscribe remote result prod-linux TASK_ID -o .\recovered-out --download-artifacts
```

## Connect From The GUI

1. Open `Settings`.
2. In the remote execution area, switch `Execution mode` to `Remote`.
3. Click `Manage Remote Servers...`.
4. Create a profile with:
   - `Base URL`: `http://SERVER_IP:8765`
   - `Token`: your bearer token
   - `Remote cookies path`: optional server-side `cookies.txt`
   - `Download artifacts by default`: enabled for the common workstation flow
5. Save the profile and select it in the main remote execution widget.
6. Start a normal `Single Task` or `Queue` job.

What to expect:

- progress text will mention `Submitting remote task`
- the task gets a remote task id
- when download is enabled, output files are saved back into the local client
  output directory

## Provider And Model Notes

Remote execution sends the provider and model settings with the task.

That means:

- `local-whisper` model names such as `tiny` or `small` are resolved on the
  server
- `native-engine` model values must be valid server-side file paths
- a Windows path such as `D:\models\ggml-base.en.bin` is not valid on Linux

Example `native-engine` remote run:

```powershell
flowscribe transcribe "D:\media\clip.wav" `
  --execution remote `
  --server prod-linux `
  --provider native-engine `
  --model /home/fry/models/ggml-base.en.bin `
  -o .\client-out
```

## Troubleshooting

`Timed out while contacting remote server`

- confirm the service is running
- confirm the host and port are reachable from the client
- on slow hosts, start with `tiny` and keep one task at a time

`Remote server is already processing the maximum number of tasks`

- the server returned HTTP `429`
- wait for the current task to finish, then retry
- this is expected on small hosts with the default one-task capacity guard

URL media fails but local uploads work:

- verify `yt-dlp` can reach the source site from the server
- verify the remote cookies file exists on the server
- confirm the cookies file is a valid Netscape-format export

Artifacts finish on the server but not locally:

- make sure artifact download is enabled in the profile or per-run settings
- retry with `flowscribe remote result SERVER TASK_ID --download-artifacts`

