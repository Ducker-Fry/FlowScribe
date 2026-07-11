[中文](gui-user-guide.md) | English

# FlowScribe GUI User Guide

> Version: v0.3.5  
> Updated: 2026-06-05  
> Platform: Windows 10/11

## 1. Global View First

The current GUI revolves around three top-level views:

- `Single Task`: one local transcription job or one URL
- `Library`: browse historical transcripts and generated artifacts
- `Queue`: batch local files and URLs

The top toolbar also provides:

- `Settings`: global settings
- `Help`: open local documentation

> ![GUI main window overview](assets/p1.png)

## 2. Quick Start

### 2.1 Launch

Portable build:

```text
FlowScribeGUI.exe
```

For installed builds, the first launch may prompt you to prepare a model first. Current installed builds do not silently auto-download models in the background by default.

### 2.2 The First Two Things To Do

1. Open `Settings` and confirm your output directory and output formats.
2. Open `Model Center` and download at least one model.

Recommended starting points:

- daily local work: `small`
- Chinese-first path: `paraformer-zh`
- quick smoke tests: `tiny`

> ![First-time Settings and Model Center](assets/p2.png)

### 2.3 Complete Your First Transcription

The most stable first-run path is:

1. go to `Single Task`
2. click `Add Files`
3. select a local audio or video file
4. check the file in the list
5. click `Start Transcription`
6. inspect progress in `Run Details`
7. click `Open View` after the run finishes

> ![Add Files to Open View workflow](assets/gif1.gif)

## 3. Single Task View

`Single Task` is the simplest and most stable GUI entry.

### 3.1 Local Files

The `Local Files` area supports:

- `Add Files`
- `Select All`
- `Clear`
- drag and drop
- per-file selection checkboxes

The status summary shows selected count versus total count.

> ![Local Files panel](assets/p3.png)

### 3.2 URL Sources

The `Online Source` area supports one URL at a time plus download preferences:

- `Preserve media`
- `Type`: `Audio` / `Video`
- `Quality`: `Best` / `High` / `Medium` / `Low`
- `Format`: `Auto` or a specific container

Pressing Enter can start the current URL quickly. If you need many URLs, `Queue` is the better path.

### 3.3 Start / Cancel / Settings / Open Transcript / Open View

These controls map to:

- `Start Transcription`
- `Cancel`
- `Settings`
- `Open Transcript`
- `Open View`

Two important notes:

- `Open Transcript` is mainly for valid transcript `.json` files, not arbitrary output artifacts.
- `Open View` can open during a run for progress details, and after a run it becomes the full review workspace.

### 3.4 Run Details

The lower area of `Single Task` includes an embedded `Run Details` tab for:

- progress messages
- phase/status text
- warnings and cancel notices

Full review, search, editing, and artifact preview happen in the separate `Open View` window.

### 3.5 System Audio Capture Entry

The GUI includes a `System Audio Capture` collapsible section with:

- `Start Capture`
- `Stop Capture`
- status labels

However, this path is still being refined. For more stable work today:

- prefer local files
- or capture audio externally and then import the file into FlowScribe

> ![System Audio Capture section](assets/p4.png)

## 4. Open View Window

`Open View` is the most important post-processing window in the current GUI. It has two tabs:

- `Run Details`
- `Workspace`

### 4.1 Run Details

Shows:

- current run logs
- completed run output
- total duration if present in the result object

### 4.2 Workspace Overview

`Workspace` combines:

- media binding and playback
- transcript search
- segment browsing
- text editing
- artifact preview

> ![Open View workspace](assets/gif2.gif)

### 4.3 Media Binding And Playback

If the transcript JSON already contains media binding info, the window will try to bind automatically. Otherwise click:

```text
Bind Media To Transcript
```

After binding, you can:

- play media
- scrub the timeline
- jump to matching positions from search results or transcript segments

### 4.4 Search And Segments

`Workspace` supports:

- keyword search
- clickable search results
- full segment browsing
- clicking a segment to sync media position

This is especially useful for long transcript correction and precise review.

### 4.5 Editing Transcript Text

The GUI supports segment-text correction inside transcript JSON.

Workflow:

1. select a segment
2. edit the text
3. choose how to save:
   - overwrite the original JSON
   - save a corrected copy

Important boundaries:

- this edits segment text only; it does not rerun the model
- timestamps and segment ordering are preserved

### 4.6 Re-Export From JSON

For a valid transcript JSON, `Workspace` can re-export:

- `txt`
- `md`
- `json`
- `srt`
- `vtt`

If there are unsaved edits, the GUI asks you to save first.

### 4.7 Artifact Preview

`Workspace` concentrates previewable artifacts in one place:

- `.json`
- `.md`
- `.txt`
- `.srt`
- `.vtt`

Useful for:

- comparing different export formats
- copying text into downstream tools
- checking corrected export output quickly

## 5. Library View

`Library` is for historical transcript management.

### 5.1 What Gets Recorded

When the GUI completes a transcription with JSON output, it tries to add an entry containing:

- transcript path
- output directory
- source type
- generated artifacts
- optional media binding

### 5.2 What You Can Do

Current library capabilities:

- search by name, path, or output directory
- filter by source type: `All / Local / URL / Capture / Unknown`
- filter by status: available / missing
- filter by whether the item was opened before
- sort by `Last Opened / Created / Name`

### 5.3 Detail Actions

When you select one entry, the detail area supports:

- `Open`
- `Output Dir`
- `Copy Path`
- `Rebind`
- `Open Artifact`
- `Copy Artifact Path`

> ![Library view](assets/p5.png)

## 6. Queue View

`Queue` is the batch-processing path.

### 6.1 Add Tasks

You can add content in three ways:

- `Add Local Files...`
- paste multiple URLs and click `Add URLs`
- `Import from File...`

The URL input also supports:

```text
Ctrl+Enter
```

as a quick submit action.

### 6.2 Default Settings For New Tasks

The `Queue` page provides defaults for newly added items:

- `Max Retries`
- `Preserve media`
- `Type`
- `Quality`
- `Format`

These affect newly added items only. They do not rewrite existing items automatically.

### 6.3 Queue Operations

The queue area supports:

- internal drag reordering
- `Start Queue`
- `Cancel Queue`
- `Skip Current`
- `Open View`
- `Edit Settings`
- `Retry Failed`
- `Remove Selected`
- `Clear Completed`
- `Select All`

### 6.4 Batch Edit Item Settings

`Edit Settings` opens the queue-item settings dialog and can batch-edit:

- output directory, output name, output formats
- provider and model
- language and preset
- timestamp options
- progressive transcription settings
- network settings
- URL media options

For URL items, it can also set:

- whether downloaded media is kept
- media type
- whether the media should auto-bind to the transcript

### 6.5 Bookmarklet Server

`Queue` includes the bookmarklet server entry inside the `Advanced Settings` collapsible area.

Current controls:

- `Enable Server`
- custom port
- runtime status

Default bookmarklet install address:

```text
http://127.0.0.1:8765/bookmarklet.js
```

> ![Queue view](assets/p6.png)
> ![Bookmarklet to queue workflow](assets/gif3.gif)

## 7. Settings Dialog

`Settings` is split into four tabs.

### 7.1 Appearance

Currently used for theme switching.

### 7.2 Transcription

Global transcription defaults:

- output directory
- output name base
- output formats
- overwrite behavior
- provider / model / language / preset
- segment timestamps
- word timestamps

The `Model Center` button opens the model manager window.

### 7.3 Network

Mainly affects URL work:

- `Network family`
- `Proxy`
- `Cookies file`

### 7.4 Advanced

Current progressive-transcription settings:

- whether progressive mode is enabled
- whether resume is enabled
- chunk duration
- maximum worker count
- native threads

## 8. Model Center

`Model Center` handles local model management.

Current capabilities:

- list downloadable models
- download selected models
- list installed models
- remove installed models
- import local `whisper.cpp` `.bin` models
- open the local model guide

Useful for:

- preparing models before first use on installed builds
- importing your own `.bin` file for `native-engine`
- cleaning unused models to save disk space

## 9. Recommended Usage

### 9.1 One File Or A Few Files

Use `Single Task`:

1. add local files
2. select the files
3. start transcription
4. open `Open View`
5. search, correct, and re-export in `Workspace`

### 9.2 Many URLs

Use `Queue`:

1. paste multiple URLs or import a file
2. confirm default download settings
3. start the queue
4. use `Open View` to review completed items one by one

### 9.3 Historical Review

Use `Library`:

1. search the record
2. open the transcript or artifact
3. rebind media if needed

## 10. Current Boundaries And Notes

### 10.1 `Open Transcript` Mainly Targets JSON

Treat the `Open Transcript` button as “open transcript JSON,” not “open any transcript-related file.”

### 10.2 System Audio Capture Is Still Being Refined

The main window already includes `System Audio Capture`, but the more stable paths are still:

- local files
- single URLs
- batch queue work

### 10.3 Do Not Rely On Old GUI Manuals For Advanced Export Features

Older manuals described features such as named export profiles, separate API chapters, or GUI command-line batch launch behavior in ways the current main GUI no longer exposes. This guide intentionally follows the current code path instead.
