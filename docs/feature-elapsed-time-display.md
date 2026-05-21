# Feature: Elapsed Time Display

## Overview
Added elapsed time display for transcription tasks in both the Single Task view and Run Details dialog.

## Changes Made

### 1. Single Task View (`src/flowscribe/gui/views/single_task_view.py`)

**Added:**
- Import `TranscriptionResult` from `flowscribe.app.models`
- Instance variable `_last_result` to store the last transcription result

**Modified:**
- `__init__`: Added `_last_result = None` initialization
- `_on_finished`: 
  - Store result in `_last_result`
  - Format elapsed time as "Xm Ys" for times >= 60s, or "X.Xs" for times < 60s
  - Display elapsed time in status label (e.g., "Transcription complete! Succeeded: 1. (Time: 2m 30s)")
  - Add elapsed time line to preview output
- `_open_view`: Pass `result=self._last_result` to TranscriptionViewDialog

**Time Format:**
- Less than 60 seconds: `5.5s`, `30.0s`
- 60 seconds or more: `1m 30s`, `2m 5s`, `61m 1s`

### 2. Transcription View Dialog (`src/flowscribe/gui/dialogs/transcription_view_dialog.py`)

**Added:**
- Import `QScrollArea` for workspace scrolling (separate feature)
- Parameter `result` to `__init__` method
- Instance variable `_result` to store the result

**Modified:**
- `__init__`: Accept optional `result` parameter
- `_create_run_details_tab`: 
  - Display elapsed time at the top of Run Details tab if result is available
  - Styled with bold, larger font, and green color
  - Format: "Elapsed Time: 2m 30s"

### 3. Tests (`tests/test_elapsed_time_display.py`)

**Created new test file with:**
- `format_elapsed_time`: Helper function to format elapsed seconds
- `test_format_elapsed_time_none`: Test None handling
- `test_format_elapsed_time_seconds`: Test seconds formatting
- `test_format_elapsed_time_minutes`: Test minutes formatting
- `test_elapsed_seconds_property`: Test TranscriptionResult.elapsed_seconds property

**Test Results:** All 4 tests passed ✓

## User Experience

### Single Task View
After transcription completes, users will see:
1. Status label shows elapsed time: "Transcription complete! Succeeded: 1. (Time: 2m 30s)"
2. Preview output includes: "Elapsed time: Time: 2m 30s"

### Run Details Dialog
When opening the transcription view:
1. Run Details tab shows elapsed time at the top in bold green text
2. Format: "Elapsed Time: 2m 30s"

## Implementation Notes

1. **Backward Compatibility**: 
   - TranscriptionViewDialog's `result` parameter is optional
   - Queue view calls without result still work (shows no elapsed time)
   - Handles None elapsed_seconds gracefully

2. **Time Calculation**:
   - Uses existing `TranscriptionResult.elapsed_seconds` property
   - Calculates as `(finished_at - started_at).total_seconds()`
   - Returns None if transcription not finished

3. **Display Logic**:
   - Only shows elapsed time if result is available and finished
   - Formats consistently across both views
   - Clear, human-readable format

## Related Files
- `src/flowscribe/app/models.py` - TranscriptionResult with elapsed_seconds property (no changes)
- `src/flowscribe/gui/views/queue_view.py` - Calls TranscriptionViewDialog without result (no changes needed)

## Future Enhancements
- Add realtime speed factor display (e.g., "4.2x realtime")
- Show estimated time remaining during transcription
- Add elapsed time to queue item display
