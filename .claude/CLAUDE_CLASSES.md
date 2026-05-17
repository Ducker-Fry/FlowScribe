# Detailed Class Reference

Read this file on demand when detailed class structure is needed. Do not load by default.

## Core Domain Models (`src/flowscribe/core/models.py`)

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

## Application Models (`src/flowscribe/app/models.py`)

| Class | Lines | Purpose |
|-------|-------|---------|
| `SourceSpec` | 29 | One user source (local/url/capture), keep_media, url_media_kind |
| `TranscriptionJob` | 42 | Full job request — sources, model, progressive options |
| `ProgressEvent` | 77 | Structured progress with chunk_index, chunk_count, failed_chunks |
| `TranscriptionResult` | 109 | Final result — outputs, errors, canceled |

## Core Ports (Protocols) (`src/flowscribe/core/ports.py`)

- `MediaPreparer` — `prepare(item, work_dir) -> PreparedAudio`
- `Transcriber` — `transcribe(audio) -> Transcript`
- `ArtifactWriter` — `write_all(transcript, output_dir) -> OutputArtifacts`
- `InputSource` — `discover() -> list[MediaItem]`

## Error Hierarchy (`src/flowscribe/core/errors.py`)

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

## Pipeline (`src/flowscribe/core/pipeline.py`)

- `LocalTranscriptionPipeline` — central orchestrator wiring preparer + transcriber + writer
  - `build_transcript(item)` — one-shot
  - `build_progressive_transcript(item, chunk_duration_seconds, chunk_overlap_seconds, resume, max_workers, max_failed_chunks=3)` — chunked
  - `_prepare_or_cache(item, work_dir)` — checks `PreparedAudioCache` before ffmpeg

## Progressive Transcription (`src/flowscribe/core/progressive.py`)

- `PreparedAudioDurationProbe` — WAV duration from header
- `FixedDurationChunkPlanner` — plans overlapping chunks (default 30s, 3s overlap, 4s for Chinese)
- `ProgressiveTranscriptionExecutor.execute(audio, plan, cache_store, resume, max_workers, max_failed_chunks=0, update_callback)` — runs chunks, retries once per chunk on failure, skips if within `max_failed_chunks`
- `ConservativeChunkMergePolicy` — deduplicates chunk boundaries, Chinese-aware
- `ProgressiveTranscriptConsistencyChecker` — validates segment order/overlap
- `ProgressiveChunkCache` — persists chunk results as JSON for resume

## Service Layer (`src/flowscribe/app/service.py`)

- `TranscriptionService.run(job, progress=None, should_cancel=None)` — main entry point
- `_run_local_source()` — discovers files, runs pipeline per item
- `_run_url_source()` — downloads URL media, then runs pipeline
- `_build_pipeline(job, settings)` — wires full pipeline with FfmpegAudioExtractor, LocalWhisperTranscriber, TranscriptArtifactWriter
- `_emit_progressive_update()` — converts ProgressiveTranscriptionUpdate → ProgressEvent

## CLI (`src/flowscribe/cli/main.py`)

| Function | Line | Command |
|----------|------|---------|
| `main()` | 26 | Argparse dispatch |
| `run_transcribe()` | 68 | `flowscribe transcribe` |
| `run_url()` | 81 | `flowscribe url` |
| `run_inspect()` | 92 | `flowscribe inspect` |
| `run_search()` | 160 | `flowscribe search` |
| `_print_cli_progress()` | 287 | CLI progress bar rendering |

## GUI (`src/flowscribe/gui/`)

- **`main_window.py`** — `MainWindow(QMainWindow)`, full UI logic (~95 methods)
- **`qt_app.py`** — `run_gui()` entry, `FlowScribeMainWindow` compat wrapper
- **`utils.py`** — 68 stateless pure functions (payload building, formatting, artifact rendering)
- **`state_manager.py`** — `load_gui_state()` / `save_gui_state()` using QStandardPaths
- **`state.py`** — `GuiTranscriptionForm` (line 19), `to_job()` → TranscriptionJob
- **`workers/transcription_worker.py`** — `TranscriptionWorker(QObject)` — runs service on QThread
- **`widgets/source_list_widget.py`** — `SourceListWidget(QListWidget)` — drag-drop media list

## Audio Cache (`src/flowscribe/media/audio_extractor.py`)

- `FfmpegAudioExtractor.prepare(item, work_dir)` — runs ffmpeg to create WAV
- `PreparedAudioCache(cache_dir).get(item)` / `.put(audio)` — source-hash-keyed WAV cache, validates by mtime+size

## URL Downloader (`src/flowscribe/input/url_downloader.py`)

- `UrlAudioDownloader.download_audio(url, saved_media_kind)` → `UrlDownloadResult`
- `UrlSavedMediaKind = Literal["audio", "video"]`
- Handles: direct audio, direct video, page-based media (via yt-dlp)

## Provider (`src/flowscribe/transcription/providers.py`)

- `TranscriptionProvider` protocol: `build_transcriber(settings)`, `capabilities`
- `LocalWhisperProvider` — builds `LocalWhisperTranscriber` (faster-whisper wrapper)
- `LocalWhisperTranscriber` — implements `transcribe()` and `transcribe_clip()`, supports `fork_for_worker()`
