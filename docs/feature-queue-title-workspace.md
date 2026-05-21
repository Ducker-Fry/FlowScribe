# Feature: Queue Title Display & Workspace Transcript Loading

**Date**: 2026-05-21  
**Version**: v0.3.0+  
**Status**: Implemented

## Overview

Two related features to improve user experience with transcript management:

1. **Queue Title Display**: Display web page titles instead of URLs in the queue view
2. **Workspace Transcript Loading**: Open transcript JSON files directly in the workspace

## 1. Queue Title Display

### Problem
When using bookmarklets to add videos to the queue, items were displayed with their full URLs (e.g., `https://www.youtube.com/watch?v=dQw4w9WgXcQ`), making it difficult to identify and distinguish between different videos.

### Solution
Modified `QueueView._format_item_display()` to use `QueueItem.display_label` property, which prioritizes the `title` field over the URL.

### Implementation

**Files Modified**:
- `src/flowscribe/gui/views/queue_view.py` (lines 494-506)

**Key Changes**:
```python
# Before
source_label = f"[URL] {item.source.value[:60]}..."

# After
display_name = item.display_label  # Prioritizes title over URL
if len(display_name) > 80:
    display_name = display_name[:77] + "..."
source_label = f"[URL] {display_name}"
```

**Data Flow**:
1. Bookmarklet extracts page title and URL
2. Sends JSON: `{url: "...", title: "...", timestamp: "..."}`
3. `AddUrlHandler.add_url()` creates `QueueItem` with `title` field
4. `QueueItem.display_label` returns `title` if available, else falls back to URL
5. `QueueView._format_item_display()` uses `display_label` for display

### Behavior

**With Title** (from bookmarklet):
```
[⏳] [URL] Never Gonna Give You Up - Rick Astley
[⏳] [URL] 【中文测试】这是一个B站视频标题
```

**Without Title** (manual URL entry or file import):
```
[⏳] [URL] https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

**Local Files** (unchanged):
```
[⏳] [FILE] my_recording.mp4
```

### Edge Cases
- **Long titles**: Truncated to 80 characters (77 + "...")
- **Empty title**: Falls back to URL display
- **Chinese/Unicode titles**: Fully supported
- **Local files**: Title field ignored, always shows filename

## 2. Workspace Transcript Loading

### Problem
Users could only view transcripts that were just completed in the current session. There was no way to open and review existing transcript JSON files in the workspace.

### Solution
Added "Open Transcript" button to the TranscriptionViewDialog workspace, allowing users to load any transcript JSON file and update the workspace display.

### Implementation

**Files Modified**:
- `src/flowscribe/gui/dialogs/transcription_view_dialog.py` (lines 362-509)

**Key Changes**:
1. Added "Open Transcript" button to artifacts section toolbar
2. Implemented `_open_transcript_file()` method:
   - Opens file dialog for JSON selection
   - Validates transcript format (checks for 'segments' field)
   - Calls `_load_transcript()` to update all views
   - Updates status label with result

**UI Layout**:
```
Transcript artifacts
┌─────────────────────────────────────┐
│ [Open Transcript]                   │  ← New button
├─────────────────────────────────────┤
│ Current artifact: [dropdown] [...]  │
│ Quick switch: [JSON] [SRT] [VTT]... │
│ [Artifact viewer]                   │
└─────────────────────────────────────┘
```

### Behavior

**Successful Load**:
1. User clicks "Open Transcript"
2. File dialog opens (filters: `*.json`)
3. User selects transcript JSON file
4. Workspace updates:
   - Transcript summary refreshed
   - Segments list populated
   - Artifacts discovered and loaded
   - Media auto-binding attempted
   - Status: "Loaded transcript: filename.json"

**Validation Errors**:
- Missing 'segments' field: "Invalid transcript format - missing segments"
- File read error: "Error loading transcript: [error message]"
- User cancels: No action taken

### Integration Points

**SingleTaskView**:
- Existing "Open Transcript" button (line 160-161)
- Automatically opens TranscriptionViewDialog after loading
- Emits `transcript_loaded` signal

**TranscriptionViewDialog**:
- New "Open Transcript" button in workspace (line 369)
- Allows switching between different transcripts
- Reuses existing `_load_transcript()` infrastructure

## Testing

### Test Files Created

**1. `tests/test_queue_display_title.py`** (Unit tests)
- `test_queue_item_display_label_with_title`: Verify display_label returns title
- `test_queue_item_display_label_without_title`: Verify fallback to URL
- `test_format_item_display_with_title`: Verify QueueView formatting with title
- `test_format_item_display_without_title`: Verify QueueView formatting without title
- `test_format_item_display_truncates_long_title`: Verify 80-char truncation
- `test_local_file_display_unchanged`: Verify local files unaffected

**2. `tests/test_bookmarklet_title_integration.py`** (Integration tests)
- `test_bookmarklet_title_integration`: End-to-end bookmarklet → queue → display
- `test_bookmarklet_without_title_fallback`: Verify URL fallback behavior
- `test_bookmarklet_batch_with_titles`: Verify batch URL addition with titles
- `test_queue_view_format_with_bookmarklet_title`: Verify Chinese title support

**3. `tests/test_transcription_view_dialog.py`** (Dialog tests)
- `test_open_transcript_file_valid_json`: Verify successful JSON loading
- `test_open_transcript_file_invalid_json`: Verify validation (missing segments)
- `test_open_transcript_file_cancelled`: Verify cancel handling
- `test_open_transcript_file_read_error`: Verify error handling

### Test Execution

```powershell
# Run all new tests
python -m pytest tests/test_queue_display_title.py tests/test_bookmarklet_title_integration.py tests/test_transcription_view_dialog.py -v

# Run focused tests
python -m pytest tests/test_queue_display_title.py::test_format_item_display_with_title -v
```

## User Impact

### Benefits
1. **Better Queue Readability**: Video titles are much more recognizable than URLs
2. **Improved Workflow**: Can review any transcript without re-transcribing
3. **Consistent Experience**: Title display works across all queue sources
4. **Multi-language Support**: Chinese, Japanese, and other Unicode titles fully supported

### Breaking Changes
None. Changes are backward compatible:
- Existing queue items without titles display URLs (unchanged behavior)
- Existing workflows continue to work

### Migration Notes
- No migration required
- Existing queue items will display URLs until re-added with bookmarklet
- New bookmarklet additions automatically include titles

## Future Enhancements

### Queue Title Display
- [ ] Edit title in queue view (right-click context menu)
- [ ] Fetch title from URL if missing (background task)
- [ ] Show tooltip with full URL on hover

### Workspace Transcript Loading
- [ ] Recent transcripts dropdown (MRU list)
- [ ] Drag-and-drop JSON files onto workspace
- [ ] Compare two transcripts side-by-side

## Related Files

### Source Code
- `src/flowscribe/gui/views/queue_view.py` - Queue display logic
- `src/flowscribe/gui/dialogs/transcription_view_dialog.py` - Workspace dialog
- `src/flowscribe/queue/models.py` - QueueItem.display_label property
- `src/flowscribe/server/handlers.py` - AddUrlHandler (title handling)

### Tests
- `tests/test_queue_display_title.py`
- `tests/test_bookmarklet_title_integration.py`
- `tests/test_transcription_view_dialog.py`

### Documentation
- `.claude/CLAUDE.md` - Updated architecture and features sections
- `docs/feature-queue-title-workspace.md` - This document

## References

- Issue: User feedback on bookmarklet URL display
- Bookmarklet code: Sends `{url, title, timestamp}` payload
- QueueItem model: Already had `title` field and `display_label` property
- Fix: Use `display_label` instead of direct URL access
