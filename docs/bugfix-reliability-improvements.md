# Bug Fixes and Reliability Improvements

**Date**: 2026-05-21  
**Commit**: Preparing for stricter testing  
**Status**: Ready for commit

## Overview

This commit consolidates multiple bug fixes and reliability improvements discovered during feature development and testing. These changes ensure basic functionality works correctly before implementing stricter testing protocols.

## Fixed Issues

### 1. Queue Item Transcript Tracking
**Problem**: Queue items didn't track transcript paths after completion, making it impossible to open transcription views from queue.

**Fix**: Added `transcript_path` and `run_detail` fields to `QueueItem`
- `src/flowscribe/queue/models.py`: Added fields to dataclass
- `src/flowscribe/gui/workers/queue_runner.py`: Store transcript path and run output on completion
- `src/flowscribe/queue/store.py`: Persist new fields to JSON

**Impact**: Queue view can now open completed transcriptions directly.

### 2. Library Media Binding
**Problem**: Transcripts added to library from queue didn't preserve media bindings, breaking media playback in transcript viewer.

**Fix**: Pass artifacts to library indexing
- `src/flowscribe/gui/new_main_window.py`: Modified `_add_transcript_to_library()` to accept artifacts parameter
- Extract media path and create `LibraryMediaBinding` when auto-bind is enabled
- Preserve source kind (local/url) from artifacts

**Impact**: Media files now correctly bind to transcripts in library.

### 3. URL Download Options
**Problem**: Queue URL imports ignored download quality, format, and media type settings from UI.

**Fix**: Implement `DownloadOptions` dataclass and pass through pipeline
- `src/flowscribe/app/models.py`: Added `DownloadOptions` dataclass
- `src/flowscribe/input/url_downloader.py`: 
  - Accept `download_options` parameter
  - Implement `_build_format_selector()` for quality/format selection
  - Support video download with quality options
- `src/flowscribe/gui/new_main_window.py`: 
  - Extract download options from queue view
  - Pass to `SourceSpec` when creating queue items

**Impact**: Users can now control download quality and format for batch URL imports.

### 4. Missing yt-dlp Warning
**Problem**: Silent failure when yt-dlp not installed for video downloads.

**Fix**: Added explicit warning
- `src/flowscribe/input/url_downloader.py`: Emit `UserWarning` when yt-dlp missing
- Gracefully fall back to audio extraction

**Impact**: Users get clear feedback when video download fails due to missing dependency.

### 5. Progressive Executor Error Handling
**Problem**: Chunk execution errors not properly propagated, causing silent failures.

**Fix**: Improved error handling and logging
- `src/flowscribe/core/progressive/executor.py`: Enhanced error messages and retry logic

**Impact**: Better debugging information for progressive transcription failures.

### 6. Elapsed Time Display
**Problem**: Transcription completion didn't show elapsed time in some views.

**Fix**: Added elapsed time tracking and display
- `src/flowscribe/app/service.py`: Track elapsed seconds in `TranscriptionResult`
- `src/flowscribe/gui/views/single_task_view.py`: Display formatted elapsed time
- `src/flowscribe/gui/workers/transcription_worker.py`: Pass elapsed time through signals

**Impact**: Users can see how long transcriptions took.

### 7. Output Artifact Metadata
**Problem**: Output artifacts didn't track source kind and media binding info.

**Fix**: Enhanced `OutputArtifacts` with metadata
- `src/flowscribe/core/models.py`: Added `source_kind` and `auto_bind_media` fields
- `src/flowscribe/output/artifact_writer.py`: Populate metadata when writing
- `src/flowscribe/output/json_writer.py`: Include source info in JSON output

**Impact**: Artifacts carry complete metadata for library indexing.

### 8. CLI Download Options
**Problem**: CLI didn't expose download quality and format options.

**Fix**: Added CLI arguments
- `src/flowscribe/cli/args.py`: Added `--download-quality` and `--download-format` arguments
- `src/flowscribe/cli/main.py`: Pass options to service layer

**Impact**: CLI users can control download behavior.

### 9. Transcript Viewer Media Resolution
**Problem**: Transcript viewer couldn't resolve media paths for URL sources.

**Fix**: Enhanced media path resolution
- `src/flowscribe/gui/transcript_viewer.py`: Improved `resolve_transcript_media_path()` logic

**Impact**: Better media auto-binding in transcript viewer.

## Files Changed

### Core Models & Service
- `src/flowscribe/app/models.py` - Added `DownloadOptions`
- `src/flowscribe/app/service.py` - Elapsed time tracking
- `src/flowscribe/core/models.py` - Output artifact metadata
- `src/flowscribe/core/progressive/executor.py` - Error handling

### Input/Output
- `src/flowscribe/input/url_downloader.py` - Download options, format selection, warnings
- `src/flowscribe/output/artifact_writer.py` - Metadata population
- `src/flowscribe/output/json_writer.py` - Source info in JSON

### Queue System
- `src/flowscribe/queue/models.py` - Transcript tracking fields
- `src/flowscribe/queue/store.py` - Persist new fields
- `src/flowscribe/gui/workers/queue_runner.py` - Store transcript path and run output

### GUI
- `src/flowscribe/gui/new_main_window.py` - Library media binding, download options
- `src/flowscribe/gui/views/single_task_view.py` - Elapsed time display
- `src/flowscribe/gui/workers/transcription_worker.py` - Elapsed time signals
- `src/flowscribe/gui/transcript_viewer.py` - Media resolution

### CLI
- `src/flowscribe/cli/args.py` - Download option arguments
- `src/flowscribe/cli/main.py` - Pass options to service

## Testing Preparation

These fixes address issues discovered during:
1. Manual testing of queue → library workflow
2. Bookmarklet integration testing
3. URL download with various quality settings
4. Media binding in transcript viewer

With these fixes in place, the codebase is ready for:
- Comprehensive integration tests
- End-to-end workflow tests
- Stricter error handling tests
- Performance benchmarking

## Backward Compatibility

All changes are backward compatible:
- New fields in `QueueItem` have default values (`None`)
- `DownloadOptions` is optional with sensible defaults
- Existing queue files load correctly (new fields auto-populate as `None`)
- CLI maintains existing behavior when new flags not used

## Known Limitations

1. **Queue migration**: Existing queue items won't have transcript paths until re-run
2. **Library re-indexing**: Existing library entries may need manual media binding
3. **Download quality**: Only works with yt-dlp installed

## Next Steps

After this commit:
1. Run full test suite to verify no regressions
2. Test queue → library → viewer workflow end-to-end
3. Test URL downloads with various quality settings
4. Implement stricter validation tests
5. Add integration tests for new features
