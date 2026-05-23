# Queue Media Settings UI Improvement

## Problem
The Queue view had "Preserve media" and download options (Type, Quality, Format) that could be confusing because similar settings also exist in the "Edit Settings" dialog for individual queue items. Users might not understand the relationship between these two places.

## Solution (Option C)
Added a clear visual grouping with the label **"Default Settings for New Items"** to clarify that the settings in the Queue view are used as defaults when adding new URLs to the queue.

## Implementation Details

### Changes Made
- Wrapped the "Max Retries" and download options (Preserve media, Type, Quality, Format) in a `QGroupBox` with the title "Default Settings for New Items"
- This makes it clear that these settings apply to newly added items, not existing queue items

### User Experience
1. **Adding new URLs**: The settings in "Default Settings for New Items" are applied to each new URL added to the queue
2. **Editing existing items**: Use the "Edit Settings" button to modify settings for items already in the queue, including the "URL Media Settings" section

### Files Modified
- `src/flowscribe/gui/views/queue_view.py` - Added QGroupBox wrapper for default settings

## Benefits
- **Clarity**: Users immediately understand that these are default settings for new items
- **No confusion**: Clear distinction between "defaults for new items" vs "settings for existing items"
- **Convenience**: Users can set defaults once and add multiple URLs without editing each one
- **Flexibility**: Individual items can still be customized via "Edit Settings" dialog

## Visual Layout
```
┌─ Add Sources ────────────────────────────────────┐
│ Local Files: [Add Local Files...]                │
│ URLs: [text area]                                 │
│ [Add URLs] [Import from File...]                 │
└───────────────────────────────────────────────────┘

┌─ Default Settings for New Items ─────────────────┐
│ Max Retries: [2]                                  │
│ ☐ Preserve media  Type: [Audio ▼]                │
│ Quality: [Best ▼]  Format: [Auto ▼]              │
└───────────────────────────────────────────────────┘

Queue:
[queue list]

[Start Queue] [Cancel Queue] [Skip Current]
[Edit Settings] [Retry Failed] [Open View] [Remove Selected] [Clear Completed]
```

## Related Features
- Queue Item Settings Dialog (`QueueItemSettingsDialog`) - includes "URL Media Settings" section for editing individual items
- See `docs/queue-keep-media-fix.md` for details on the keep_media bug fix
