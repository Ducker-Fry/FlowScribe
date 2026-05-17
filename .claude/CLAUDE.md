# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

FlowScribe is a local-first audio/video transcription toolkit for Windows. It provides a CLI (`flowscribe`) and a PySide6 desktop GUI for transcribing local media and public URL audio, with transcript review, editing, search, and re-export capabilities.

**Stack**: Python 3.10+ CLI + PySide6 GUI + .NET 8 WASAPI helper (system audio capture)  
**Current release**: v0.2.7  
**License**: MIT

## Quick Commands

```powershell
# Run tests (redirect output to save tokens)
python -m pytest > test.log 2>&1; Get-Content test.log -Tail 5
python -m pytest -p no:cacheprovider --basetemp="$env:TEMP\pytest-fs" tests/test_file.py

# Lint
python -m ruff check src tests

# Build CLI package
.\scripts\build_exe.ps1 > build.log 2>&1; Get-Content build.log | Select-String "error|Done|Release"

# Build GUI package (run after CLI build, not in parallel)
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_gui_exe.ps1 -Python python > gui_build.log 2>&1

# Smoke tests
.\dist\FlowScribe\FlowScribe.exe doctor
.\dist\FlowScribeGUI\FlowScribeGUI.exe --self-test

# Run from source
python -m flowscribe --help
python -m flowscribe.gui

# Release (commit then tag)
git commit -m "Prepare v0.x.y"; git push; git tag v0.x.y; git push origin v0.x.y
```

## Package Structure

```
src/flowscribe/
├── app/            Service layer — TranscriptionService, ProgressEvent, TranscriptionJob
├── cli/            CLI entry point (main.py), argparse (args.py)
├── config/         Runtime settings (AppSettings), presets
├── core/           Domain models, pipeline orchestration, progressive chunking, ports/protocols, errors
├── gui/            PySide6 GUI (qt_app.py), form state (state.py), transcript viewer
├── input/          Local file discovery, URL download/inspection, cookies, proxy, security
├── library/        Transcript library (JSON-backed persistent index)
├── media/          ffmpeg audio extraction, media probing, system audio capture (WASAPI)
├── nlp/            Chinese word alignment (jieba), simplified Chinese conversion (opencc)
├── output/         Writers for txt/md/json/srt/vtt, path builder
├── search/         Full-text search over transcript JSON
├── transcript/     Transcript editing, re-export from existing JSON
└── transcription/  Provider abstraction + LocalWhisperTranscriber (faster-whisper)
tests/              28 test files corresponding to source modules
scripts/            build_exe.ps1, build_gui_exe.ps1, build_wasapi_helper.ps1
tools/              wasapi-capture-helper/ (.NET 8 C# WASAPI loopback capture)
docs/               Developer handoff, dev-state, packaging, release-automation, roadmap
```

## Architecture & Key Classes

### Core Domain Models (`src/flowscribe/core/models.py`)
| Class | Lines | Purpose |
|-------|-------|---------|
| `MediaItem` | 12 | One local media file (wraps `Path`) |
| `PreparedAudio` | 19 | WAV audio ready for transcription |
| `Transcript` | 65 | Full transcript with segments, language, model info |
| `TranscriptSegment` | 39 | One timed segment with text, words |
| `TranscriptWord` | 29 | Word-level timing unit |
| `TranscriptionChunk` | 146 | One progressive chunk window (start/end/overlap) |
| `ChunkTranscriptionResult` | 180 | Result of one chunk (status: done/failed/skipped) |
| `ProgressiveTranscriptionState` | 192 | Full progressive run state with `.completed_chunks` and `.failed_chunks` |
| `OutputArtifacts` | 81 | Written output file paths |

### Application Models (`src/flowscribe/app/models.py`)
| Class | Lines | Purpose |
|-------|-------|---------|
| `SourceSpec` | 29 | One user source (local/url/capture), keep_media, url_media_kind |
| `TranscriptionJob` | 42 | Full job request — sources, model, progressive options |
| `ProgressEvent` | 77 | Structured progress with chunk_index, chunk_count, failed_chunks |
| `TranscriptionResult` | 109 | Final result — outputs, errors, canceled |

### Core Ports (Protocols) (`src/flowscribe/core/ports.py`)
- `MediaPreparer` — `prepare(item, work_dir) -> PreparedAudio`
- `Transcriber` — `transcribe(audio) -> Transcript`
- `ArtifactWriter` — `write_all(transcript, output_dir) -> OutputArtifacts`
- `InputSource` — `discover() -> list[MediaItem]`

### Error Hierarchy (`src/flowscribe/core/errors.py`)
```
FlowScribeError
├── InputError
├── MediaPreparationError
├── TranscriptionError
├── OutputError
├── SearchError
├── DownloadError
└── CancellationError
```

### Pipeline (`src/flowscribe/core/pipeline.py`)
- `LocalTranscriptionPipeline` — central orchestrator wiring preparer + transcriber + writer
  - `build_transcript(item)` — one-shot
  - `build_progressive_transcript(item, chunk_duration_seconds, chunk_overlap_seconds, resume, max_workers, max_failed_chunks=3)` — chunked
  - `_prepare_or_cache(item, work_dir)` — checks `PreparedAudioCache` before ffmpeg

### Progressive Transcription (`src/flowscribe/core/progressive.py`)
- `PreparedAudioDurationProbe` — WAV duration from header
- `FixedDurationChunkPlanner` — plans overlapping chunks (default 30s, 3s overlap, 4s for Chinese)
- `ProgressiveTranscriptionExecutor.execute(audio, plan, cache_store, resume, max_workers, max_failed_chunks=0, update_callback)` — runs chunks, retries once per chunk on failure, skips if within `max_failed_chunks`
- `ConservativeChunkMergePolicy` — deduplicates chunk boundaries, Chinese-aware
- `ProgressiveTranscriptConsistencyChecker` — validates segment order/overlap
- `ProgressiveChunkCache` — persists chunk results as JSON for resume

### Service Layer (`src/flowscribe/app/service.py`)
- `TranscriptionService.run(job, progress=None, should_cancel=None)` — main entry point
- `_run_local_source()` — discovers files, runs pipeline per item
- `_run_url_source()` — downloads URL media, then runs pipeline
- `_build_pipeline(job, settings)` — wires full pipeline with FfmpegAudioExtractor, LocalWhisperTranscriber, TranscriptArtifactWriter
- `_emit_progressive_update()` — converts ProgressiveTranscriptionUpdate → ProgressEvent

### CLI (`src/flowscribe/cli/main.py`)
| Function | Line | Command |
|----------|------|---------|
| `main()` | 26 | Argparse dispatch |
| `run_transcribe()` | 68 | `flowscribe transcribe` |
| `run_url()` | 81 | `flowscribe url` |
| `run_inspect()` | 92 | `flowscribe inspect` |
| `run_search()` | 160 | `flowscribe search` |
| `_print_cli_progress()` | 287 | CLI progress bar rendering |

### GUI (`src/flowscribe/gui/qt_app.py`)
- `FlowScribeMainWindow` (line 1021) — `__new__` pattern defining `_Window(QMainWindow)` 
- `run_gui()` (line 998) — entry point
- `_TranscriptionWorker` (line 1064) — runs TranscriptionService in QThread
- `GuiTranscriptionForm` (`src/flowscribe/gui/state.py:19`) — form state, `to_job()` → TranscriptionJob

### Audio Cache (`src/flowscribe/media/audio_extractor.py`)
- `FfmpegAudioExtractor.prepare(item, work_dir)` — runs ffmpeg to create WAV
- `PreparedAudioCache(cache_dir).get(item)` / `.put(audio)` — source-hash-keyed WAV cache, validates by mtime+size

### URL Downloader (`src/flowscribe/input/url_downloader.py`)
- `UrlAudioDownloader.download_audio(url, saved_media_kind)` → `UrlDownloadResult`
- `UrlSavedMediaKind = Literal["audio", "video"]`
- Handles: direct audio, direct video, page-based media (via yt-dlp)

### Provider (`src/flowscribe/transcription/providers.py`)
- `TranscriptionProvider` protocol: `build_transcriber(settings)`, `capabilities`
- `LocalWhisperProvider` — builds `LocalWhisperTranscriber` (faster-whisper wrapper)
- `LocalWhisperTranscriber` — implements `transcribe()` and `transcribe_clip()`, supports `fork_for_worker()`

## Key Workflows

### CLI Transcription
```
User → `flowscribe transcribe file.mp4`
  → cli/main.py:run_transcribe()
    → TranscriptionJob (app/models.py:42)
      → TranscriptionService.run() (app/service.py:51)
        → _run_local_source()
          → LocalTranscriptionPipeline.process() or process_progressive()
```

### GUI Transcription
```
User clicks Start → GuiTranscriptionForm.to_job() (gui/state.py)
  → _TranscriptionWorker (gui/qt_app.py:1064)
    → TranscriptionService.run(job, progress=...) (app/service.py)
      → ProgressEvent → Qt Signal → _append_progress() (gui/qt_app.py:2879)
```

### URL Transcription
```
User submits URL → SourceSpec(kind="url")
  → _run_url_source() (app/service.py:252)
    → UrlAudioDownloader.download_audio() (input/url_downloader.py)
      → direct audio/video via ffmpeg, or page media via yt-dlp
    → pipeline.process() progressive or one-shot
    → optionally preserve media (audio/video) + auto-bind
```

### Progressive Chunked Flow
```
transcriber.transcribe_clip(audio, start, end)  # per chunk
  → FixedDurationChunkPlanner.plan() → [Chunk 1..N]
    → ProgressiveTranscriptionExecutor.execute()
      → serial or parallel (max 2 workers)
        → retry once on failure, skip if within max_failed_chunks
        → ConservativeChunkMergePolicy.merge()
          → ProgressiveTranscriptConsistencyChecker.validate()
            → ProgressiveChunkCache (persist for resume)
```

## Key Dependencies

- `faster-whisper>=1.0` — local speech-to-text (CTranslate2 + Whisper)
- `PySide6>=6.7` — desktop GUI (Qt for Python)
- `yt-dlp>=2025.1` — URL media extraction
- `jieba>=0.42` — Chinese text segmentation
- `opencc-python-reimplemented>=0.1.7` — Traditional→Simplified Chinese
- External: `ffmpeg`/`ffprobe`, `WasapiCaptureHelper.exe` (.NET 8)

## Testing Patterns

- Tests use `pytest`, configured in `pyproject.toml` with `testpaths = ["tests"]`
- Ruff lint: line-length 100, sources `src` and `tests`
- Mock-based testing for service, URL downloader, and progressive executor
- Run focused tests: `python -m pytest tests/test_progressive_transcription.py tests/test_app_service.py`

## User Workflow Preferences

**Light mode** (default): Only change code. Skip non-essential docs. Do not commit unless asked. Run only focused tests/checks.  
**Standard mode**: Change code + add/update tests + run relevant tests + lint + commit.  
**Wrap-up mode**: Full test suite + build + docs + release if requested.

The user runs build and test commands themselves (redirecting to file), and only shares relevant error lines. Do not run lengthy commands that produce large output.
