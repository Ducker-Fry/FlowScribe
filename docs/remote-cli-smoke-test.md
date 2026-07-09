# Remote CLI Smoke Test

This smoke test validates the local `single-server remote-direct` client/server path using two terminals on one machine.

## Scripted path

Run the automated local smoke script when you want one command to validate the full CS link:

```powershell
cd E:\Draft\FlowScribe
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\smoke_remote_cli_cs.ps1
```

What it does:

- starts `flowscribe serve` in a background process
- uses an isolated `FLOWSCRIBE_CONFIG_DIR` so your normal remote profiles stay untouched
- registers a temporary remote server profile
- runs one local-file remote transcription and one URL remote transcription
- checks downloaded client artifacts plus key metadata fields
- removes the temporary profile and stops the server process

The rest of this document keeps the manual two-terminal procedure for debugging and step-by-step inspection.

## Prerequisites

- Working directory: `E:\Draft\FlowScribe`
- Local runtime is healthy: `python -m flowscribe doctor`
- Sample media exists, for example `samples\english_test.wav`

## Terminal A: start the server

```powershell
cd E:\Draft\FlowScribe
python -m flowscribe serve --host 127.0.0.1 --port 18769 --api-token secret -o .\remote-server-out --format json
```

Expected:

- `FlowScribe Server` banner prints
- `Listening on: http://127.0.0.1:18769`
- Process keeps running

## Terminal B: register the server profile

```powershell
cd E:\Draft\FlowScribe
python -m flowscribe remote add-server local-test --url http://127.0.0.1:18769 --token secret
python -m flowscribe remote list-servers
python -m flowscribe remote show-server local-test
```

Expected:

- Profile save succeeds
- `local-test` appears in the list

## Test 1: local file upload -> remote transcription

```powershell
python -m flowscribe transcribe "E:\Draft\FlowScribe\samples\english_test.wav" --execution remote --server local-test -o .\client-out --format json --json --non-interactive
```

Expected:

- JSON response contains `"ok": true`
- `outputs[0].json_path` points to `client-out\*.json`
- The JSON file exists locally

Validate:

```powershell
Get-ChildItem .\client-out
Get-Content .\client-out\upload-1.json -TotalCount 40
```

## Test 2: URL -> remote transcription

```powershell
python -m flowscribe url "https://www.bilibili.com/video/BV1PC4y1G7T5/?spm_id_from=333.337.search-card.all.click&vd_source=6dc67897b1c1ee5b41ec9718c3060026" --execution remote --server local-test -o .\client-out-url --format json --json --non-interactive
```

Expected:

- JSON response contains `"ok": true`
- `source_kind` is `url`
- `transcription_strategy` is populated
- Result file is downloaded into `client-out-url`

## Pass criteria

The smoke test passes if all conditions are true:

- The server starts and remains reachable
- The remote profile resolves successfully
- Local media can be uploaded and remotely transcribed
- URL media can be remotely transcribed
- Downloaded client artifacts exist in the requested local output directory

## Cleanup

Stop Terminal A, then optionally remove the profile:

```powershell
python -m flowscribe remote remove-server local-test
```
