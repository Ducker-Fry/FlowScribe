# Queue Keep Media Bug Fix and UI Improvement

## Bug Description
Users reported that even when "Preserve media" was checked in the Queue view, downloaded audio/video files were not being saved after transcription completed.

## Root Cause
The `keep_media` setting is part of the `SourceSpec` (source specification) for each queue item. When URLs were added to the queue, the `keep_media` value was captured at that moment. However:

1. The Queue Item Settings Dialog only allowed editing `QueueItemSettings`, not `SourceSpec` properties
2. Users could not modify `keep_media` for items already in the queue
3. If users checked "Preserve media" after adding URLs, those existing queue items would still have `keep_media=false`

## Solution

### Part 1: Fix the Queue Item Settings Dialog
Added a new "URL Media Settings" section to the Queue Item Settings Dialog that allows editing:
- **Preserve downloaded media** - checkbox to enable/disable media preservation
- **Media kind** - dropdown to select "audio" or "video"
- **Auto-bind media to transcript** - checkbox to automatically link media file in transcript JSON

This section only appears for URL sources (hidden for local files).

### Part 2: Clarify the Queue View UI
Added a clear **"Default Settings for New Items"** group box around the settings in the Queue view to clarify that these are defaults applied when adding new URLs, not settings for existing items.

## How to Use

### For New URLs
1. In the Queue view, configure the "Default Settings for New Items":
   - Check "Preserve media" if you want to save downloaded files
   - Select "Type" (Audio or Video)
   - Choose "Quality" and "Format" preferences
2. Add your URLs - these settings will be applied to each new item

### For Existing Queue Items
1. Select a queue item
2. Click "Edit Settings" button
3. Scroll to the "URL Media Settings" section at the bottom
4. Check "Preserve downloaded media"
5. Select media kind (audio/video)
6. Click "Apply"

## Technical Details

### Files Modified
- `src/flowscribe/gui/dialogs/queue_item_settings_dialog.py` - Added URL Media Settings section
- `src/flowscribe/gui/views/queue_view.py` - Added "Default Settings for New Items" group box
- `src/flowscribe/gui/new_main_window.py` - Updated to handle SourceSpec updates
- `src/flowscribe/gui/windows/queue_controls.py` - Updated legacy main window

### Tests Added
- `tests/test_queue_item_settings_dialog.py` - Dialog functionality tests
- `tests/test_queue_keep_media_fix.py` - Integration tests for keep_media preservation

### Where Media Files Are Saved
When `keep_media=true`, downloaded media files are saved to:
```
{output_dir}/url-media/{cleanup_dir_name}/{filename}
```

For example:
```
outputs/184002-BV1P69KBZEjE/url-media/url-1081512fd92d3ba0/remote-audio.m4a
```

The transcript JSON file will include a `media_binding` field with the path to the media file if `auto_bind_media=true`.

## Benefits
1. **Bug Fixed**: Users can now preserve media for queue items
2. **Flexibility**: Can edit media settings for items already in queue
3. **Clarity**: Clear distinction between "defaults for new items" vs "settings for existing items"
4. **Convenience**: Set defaults once, add multiple URLs without editing each one

## Migration Notes
Existing queue items created before this fix will have `keep_media=false`. To preserve media for these items:
1. Open the Queue view
2. Select each item you want to preserve media for
3. Click "Edit Settings"
4. Check "Preserve downloaded media" in the "URL Media Settings" section
5. Click "Apply"
