# Phase 2 Summary And Phase 3 Plan

Phase 2 name: **URL Transcription, Search, And Release Automation**

Phase 2 release: **v0.2.2**

Completion date: **2026-05-13**

## Phase 2 Goal

Phase 1 proved that FlowScribe could transcribe local media files through a
usable CLI. Phase 2 turned that prototype into a broader information-processing
tool: users can now inspect and transcribe public URL media, produce structured
transcript data, search transcript content by keyword, and download a packaged
Windows release without setting up a Python development environment.

The core direction of this phase was:

```text
local file transcription
  -> URL transcription
  -> structured transcript data
  -> keyword timestamp location
  -> reusable service interface
  -> automated release packaging
```

## Completed Work

### URL Input

FlowScribe now supports URL transcription through:

```powershell
flowscribe url "https://example.com/video" -o outputs
```

Implemented capabilities:

- Public direct audio/video URL handling.
- Public video page extraction through `yt-dlp`.
- Audio-first behavior by default.
- Combined-media fallback when no standalone audio stream exists.
- Temporary URL media isolation and cleanup.
- `--keep-media` for retaining downloaded or extracted intermediate media.
- Size, duration, timeout, and public-network safety limits.
- SSRF-oriented blocking for localhost, private, loopback, reserved, and unsafe addresses.

### Inspect Command

`flowscribe inspect` was added to let users check sources before transcription:

```powershell
flowscribe inspect "D:\media\lecture.mp4"
flowscribe inspect "https://example.com/video"
```

It helps users understand:

- Whether a local file has audio.
- Whether a URL is direct audio, direct video, or a video page.
- Whether the page exposes audio-only media.
- Whether FlowScribe will need to stream combined media and extract audio.
- Which strategy will be used before running a full transcription.

### Network Controls

URL media access now includes explicit troubleshooting options:

```powershell
--network-family ipv4
--cookies "D:\private\cookies.txt"
--proxy "http://127.0.0.1:7890"
```

These options solve common real-world URL problems:

- DNS or proxy environments returning unusual IPv6 addresses.
- Login-required pages that need user-provided cookies.
- Local proxies such as Clash.

The design keeps these controls explicit. FlowScribe does not collect cookies,
does not silently use browser sessions, and does not attempt to bypass DRM or
restricted media.

### Structured Transcript Outputs

Phase 2 expanded output formats:

```text
txt
md
json
srt
vtt
```

JSON became the core intermediate format for future GUI and automation work. It
now carries stable transcript metadata and segment data that can support:

- AI analysis.
- Search.
- Subtitle generation.
- GUI playback synchronization.
- Future text-click-to-video-seek behavior.

### Word Timing And Chinese Alignment

FlowScribe now reserves and uses a richer timing model:

```text
TranscriptWord
TranscriptSegment.words
TranscriptSegment.raw_words
```

For English, provider word timestamps map naturally to words. For Chinese,
Phase 2 added natural-word alignment:

```text
provider raw timing tokens -> Chinese word segmentation -> aligned natural words
```

This means JSON can preserve both:

- `raw_words`: original provider timing units.
- `words`: user-facing natural words when alignment is possible.

This is important for the later goal: clicking a word or phrase in a transcript
and jumping to the corresponding video time.

### Keyword Search And Timestamp Location

`flowscribe search` was added:

```powershell
flowscribe search outputs\video.json "机器学习"
```

Search supports:

- Multiple matches.
- `--limit`.
- `--after`.
- `--before`.
- `--context-chars`.
- `--json` output for GUI and automation.
- Word-level timestamps when available.
- Segment-level fallback when word timing is unavailable.

This changed FlowScribe from merely "read the transcript" to "locate a concept
inside media quickly."

### App Service Layer

The CLI local and URL transcription paths were migrated toward:

```text
TranscriptionJob
TranscriptionResult
TranscriptionService
ProgressEvent
ErrorInfo
SourceSpec
```

This is the architectural bridge to the future GUI. The CLI and future desktop
interface should share the same execution layer instead of duplicating media,
URL, transcription, and output logic.

### Documentation And Open Source Readiness

Phase 2 added or improved documentation for:

- URL demos.
- Inspect command.
- Cookies.
- Proxy configuration.
- VAD behavior.
- JSON format.
- GUI-facing interfaces.
- Release automation.
- Packaging.
- User guide.

The GitHub project now has stronger open-source project structure:

- README badges.
- Contribution guide.
- Security policy.
- Issue templates.
- Release installation guide.
- Demo screenshots.
- Automated CI.
- Automated Release workflow.

### Release Automation

GitHub Actions now performs the release path:

```text
push tag
  -> test
  -> lint
  -> install/prepare ffmpeg
  -> PyInstaller build
  -> packaged exe doctor check
  -> zip archive
  -> GitHub Release
  -> upload Windows x64 asset
```

The final successful Phase 2 release is:

```text
v0.2.2
FlowScribe-v0.2.2-windows-x64.zip
```

During release hardening, the workflow exposed a packaging issue: Chocolatey
installed ffmpeg shims under `C:\ProgramData\Chocolatey\bin`, and those shim
executables failed after being copied into the release folder. The packaging
script was fixed to skip Chocolatey shims and copy the real ffmpeg/ffprobe
binaries instead.

## Engineering Outcomes

Phase 2 improved FlowScribe in several dimensions:

- **Usability**: users can paste URLs, inspect media, and search transcript JSON.
- **Reliability**: URL limits, errors, proxy/cookies support, and doctor checks make failure modes clearer.
- **Extensibility**: service-layer models prepare the codebase for GUI and capture.
- **Portability**: Windows release packages are generated automatically.
- **Portfolio value**: the project now shows CLI design, media processing, testing, release automation, documentation, and open-source hygiene.

## Remaining Gaps After Phase 2

Phase 2 is complete, but several areas remain intentionally unfinished:

- No desktop GUI yet.
- No system audio capture yet.
- No transcript/video synchronized player yet.
- No job history or transcript library.
- No external speech-to-text provider abstraction.
- No plugin-style provider system.
- No full end-to-end GUI-user workflow.

These become Phase 3 and later work.

## Phase 3 Name

**Phase 3: Desktop GUI And Interactive Transcript Workflow**

## Phase 3 Goal

Phase 3 should make FlowScribe usable by non-technical users and move the project
from a command-line tool toward a daily desktop application.

The main product direction:

```text
CLI-capable transcription engine
  -> desktop GUI
  -> drag/drop and paste URL
  -> job progress
  -> transcript viewer
  -> keyword search
  -> media playback synchronization
```

## Phase 3 Core Features

### 1. Desktop GUI Foundation

Build a first usable desktop interface around the existing service layer.

Expected capabilities:

- Drag and drop local media files.
- Paste URL input.
- Choose output directory.
- Select model, language, preset, formats, timestamps, proxy, and cookies.
- Start/cancel jobs.
- Show progress events from `TranscriptionService`.
- Show errors in a user-friendly way.
- Open output folder.

The GUI must call the same service path as the CLI:

```text
GUI -> TranscriptionJob -> TranscriptionService -> outputs
```

### 2. Job Queue And Progress

Add a simple job list:

- Pending.
- Running.
- Completed.
- Failed.
- Canceled.

Each job should show:

- Source name.
- Source type: local or URL.
- Current stage.
- Output files.
- Error message if failed.

### 3. Transcript Viewer

Add a transcript reading view based on generated JSON:

- Segment list.
- Timestamp display.
- Search box.
- Click a search result to scroll to the matching segment.
- Show context around matches.

This does not need full video synchronization first. A fast transcript viewer is
already a meaningful user feature.

### 4. Media Playback Synchronization

After the transcript viewer is stable, add media playback:

- Load local source media when available.
- Click a segment timestamp to seek video/audio.
- Use segment-level timestamps first.
- Use word-level timestamps later for precise seek.

This should be built gradually:

```text
segment click -> seek to segment start
word click -> seek to word start
selected phrase -> seek to phrase range
```

### 5. Configuration Persistence

Store non-sensitive user preferences:

- Default output directory.
- Default model.
- Default language/preset.
- Default output formats.
- Default proxy URL.

Do not store cookie contents. If a cookies path is stored later, it should be
clearly visible and editable by the user.

### 6. GUI Packaging

Extend packaging so ordinary users can download one artifact and run it:

- `FlowScribe.exe` CLI remains available.
- GUI executable or launcher is added.
- ffmpeg/ffprobe remain bundled.
- Models remain unbundled.
- Release notes explain CLI and GUI usage.

## Phase 3 Technical Tasks

Recommended implementation order:

1. Choose GUI technology and create a minimal shell.
2. Build a `TranscriptionService` adapter suitable for background threads.
3. Add GUI-safe progress and cancellation handling.
4. Implement local-file transcription from the GUI.
5. Implement URL transcription from the GUI.
6. Add transcript JSON viewer.
7. Add search UI using existing search module.
8. Add segment-level media seek.
9. Add packaging workflow for GUI artifacts.
10. Add GUI smoke tests where feasible.

## Phase 3 Non-Goals

Avoid expanding too much during Phase 3:

- Do not add DRM bypass.
- Do not add database-backed library management yet.
- Do not add multi-user accounts.
- Do not add cloud sync.
- Do not add large AI summarization features inside FlowScribe.

The focus should remain:

```text
make transcription usable, visible, controllable, and navigable
```

## Phase 3 Success Criteria

Phase 3 can be considered complete when:

- A non-technical user can open the GUI and transcribe a local file.
- A user can paste a supported URL and transcribe it.
- Progress and errors are visible without reading terminal logs.
- Outputs can be opened from the GUI.
- A transcript JSON can be opened and searched.
- Clicking a transcript segment can seek local media to the right time.
- A Windows release artifact includes the GUI workflow.
- CLI functionality remains intact and tested.

## Recommended Version Target

Phase 3 should target:

```text
v0.3.0
```

Reason: a desktop GUI and interactive transcript workflow are user-facing feature
additions, not patch-level fixes.
