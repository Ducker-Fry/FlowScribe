# Phase 1 Analysis: Code Dependencies and Migration Plan

## Current Architecture Overview

### MainWindow Structure
- **Location**: `src/flowscribe/gui/main_window.py` (1198 lines)
- **Inheritance**: 7 mixins + QMainWindow
  - TranscriptionControlsMixin
  - TranscriptViewerControlsMixin
  - LibraryControlsMixin
  - WorkspaceControlsMixin
  - CaptureControlsMixin
  - SettingsControlsMixin
  - QueueControlsMixin

### Current Layout
```
MainWindow (Launcher)
├── Left Panel: Sources
│   ├── Local file list (SourceListWidget)
│   ├── URL input
│   └── System audio capture controls
├── Right Panel: Settings + Actions
│   ├── Settings (embedded, ~100 lines of UI code)
│   │   ├── Output dir/name
│   │   ├── Model/Language/Preset
│   │   ├── Formats (checkboxes)
│   │   ├── Network/Proxy/Cookies
│   │   └── Progressive options
│   ├── Action buttons
│   │   ├── Start/Cancel Transcription
│   │   ├── Open Views
│   │   ├── View Settings/Library/Recent Work
│   │   └── Help/Export Profiles
│   └── Progress bar
└── Status bar

Views Dialog (Separate Window)
├── Toolbar (View Menu + Close)
└── QTabWidget
    ├── [0] Run Details (progress output)
    ├── [1] Workspace (transcript viewer + media player + editing)
    ├── [2] Library (search + list + actions)
    └── [3] Queue (batch processing)
```

## Key Components to Migrate

### 1. Settings Panel (Lines 285-366)
**Current**: Embedded QGroupBox in MainWindow right panel
**Target**: SettingsDialog

**UI Elements**:
- output_dir_input (QLineEdit) + Browse button
- output_name_input (QLineEdit)
- model_combo (QComboBox) - GUI_MODEL_OPTIONS
- language_combo (QComboBox) - GUI_LANGUAGE_OPTIONS
- preset_combo (QComboBox) - GUI_PRESET_OPTIONS
- network_combo (QComboBox) - GUI_NETWORK_OPTIONS
- proxy_input (QLineEdit)
- cookies_input (QLineEdit) + Browse button
- format_checks (dict[str, QCheckBox]) - SUPPORTED_GUI_FORMATS
- timestamps_check (QCheckBox)
- word_timestamps_check (QCheckBox)
- overwrite_check (QCheckBox)
- progressive_enabled_check (QCheckBox)
- progressive_resume_check (QCheckBox)

**Methods to migrate**:
- `_choose_output_dir()` - from SettingsControlsMixin
- `_choose_cookies()` - from SettingsControlsMixin
- `_save_settings()` - from SettingsControlsMixin
- `_show_saved_settings()` - from SettingsControlsMixin

### 2. Run Details Tab (Lines 660-664)
**Current**: Tab in Views dialog
**Target**: Tab in SingleTaskView

**UI Elements**:
- preview_output (QPlainTextEdit) - progress log

**Methods to migrate**:
- Progress update logic from TranscriptionControlsMixin

### 3. Workspace Tab (Lines 665-780)
**Current**: Tab in Views dialog
**Target**: Tab in SingleTaskView

**UI Elements**:
- Media player controls
- Transcript viewer (segments list)
- Search box
- Segment editor
- Artifact viewer

**Methods to migrate**:
- From TranscriptViewerControlsMixin
- From WorkspaceControlsMixin

### 4. Library Tab (Lines 781-854)
**Current**: Tab in Views dialog
**Target**: LibraryView (standalone)

**UI Elements**:
- Filter combos (source, missing, opened, sort, direction)
- Library entries list
- Action buttons (Open/Bind/Remove/Cleanup)

**Methods to migrate**:
- From LibraryControlsMixin

### 5. Queue Tab (Lines 860-873)
**Current**: Tab in Views dialog, QueueTabWidget
**Target**: QueueView (standalone)

**UI Elements**:
- QueueTabWidget (already exists in `gui/widgets/queue_tab_widget.py`)

**Methods to migrate**:
- From QueueControlsMixin
- Queue file watcher setup

## Mixin Dependencies

### TranscriptionControlsMixin
**File**: `src/flowscribe/gui/windows/transcription_controls.py`
**Key methods**:
- `_start_transcription()` - main entry point
- `_cancel_transcription()`
- `_on_transcription_progress()`
- `_on_transcription_finished()`
- `_on_transcription_error()`

**Dependencies**:
- `self.file_list` (SourceListWidget)
- `self.url_input` (QLineEdit)
- `self.output_dir_input` (QLineEdit)
- `self.output_name_input` (QLineEdit)
- `self.model_combo`, `self.language_combo`, `self.preset_combo`
- `self.format_checks` (dict)
- `self.timestamps_check`, `self.word_timestamps_check`, `self.overwrite_check`
- `self.progressive_enabled_check`, `self.progressive_resume_check`
- `self.start_button`, `self.cancel_button`
- `self.progress_bar`
- `self.preview_output` (QPlainTextEdit)

### TranscriptViewerControlsMixin
**File**: `src/flowscribe/gui/windows/transcript_viewer_controls.py`
**Key methods**:
- `_open_transcript_json()`
- `_load_transcript_view()`
- `_on_segment_selected()`
- `_on_search_requested()`

### LibraryControlsMixin
**File**: `src/flowscribe/gui/windows/library_controls.py`
**Key methods**:
- `_show_transcript_library()`
- `_refresh_transcript_library_list()`
- `_open_selected_library_transcript()`
- `_remove_selected_library_entry()`

### WorkspaceControlsMixin
**File**: `src/flowscribe/gui/windows/workspace_controls.py`
**Key methods**:
- Artifact viewer management
- Media binding

### QueueControlsMixin
**File**: `src/flowscribe/gui/windows/queue_controls.py`
**Key methods**:
- `_enqueue_urls_from_text()`
- `_enqueue_from_file()`
- `_start_queue_processing()`
- `_stop_queue_processing()`
- `_edit_queue_item_settings()`
- `_remove_queue_items()`

## Settings Data Model

### Current Settings Collection
Settings are collected from UI widgets in `_collect_settings()` method:

```python
@dataclass
class TranscriptionSettings:
    output_dir: Path
    output_name_base: str
    model_name: str
    language: str | None  # "auto" → None
    preset: str | None    # "none" → None
    output_formats: tuple[str, ...]
    timestamps: bool
    word_timestamps: bool
    overwrite: bool
    network_family: str
    proxy: str | None
    cookies_path: Path | None
    progressive_enabled: bool
    progressive_resume: bool
    progressive_chunk_seconds: float
    progressive_max_workers: int
```

### Settings Persistence
- Saved to: `{AppData}/FlowScribe/gui-state.json`
- Key: `"saved_preferences"`
- Method: `_save_settings()` in SettingsControlsMixin

## Migration Strategy

### Phase 1 Deliverables
1. ✅ Created skeleton files:
   - `src/flowscribe/gui/views/single_task_view.py`
   - `src/flowscribe/gui/views/library_view.py`
   - `src/flowscribe/gui/views/queue_view.py`
   - `src/flowscribe/gui/views/__init__.py`
   - `src/flowscribe/gui/dialogs/settings_dialog.py`
   - Updated `src/flowscribe/gui/dialogs/__init__.py`

2. ✅ Analyzed dependencies:
   - Identified UI elements to migrate
   - Mapped mixin methods to new views
   - Documented settings data model

### Next Steps (Phase 2)
1. Implement SettingsDialog:
   - Copy settings panel layout from MainWindow
   - Add OK/Cancel/Apply buttons
   - Implement get_settings() method
   - Add validation logic

2. Create settings data structure:
   - Define GlobalSettings dataclass
   - Implement load/save functions
   - Integrate with SettingsDialog

## Reusable Components

### Can be reused as-is:
- `SourceListWidget` (gui/widgets/source_list_widget.py)
- `QueueTabWidget` (gui/widgets/queue_tab_widget.py)
- `TranscriptionWorker` (gui/workers/transcription_worker.py)
- `QueueRunner` (gui/workers/queue_runner.py)
- All mixin logic (just needs to be copied/adapted)

### Need modification:
- MainWindow - will be simplified to just host QStackedWidget
- Views dialog - will be removed, content moved to views

## Risk Assessment

### Low Risk
- Settings dialog creation (similar to QueueItemSettingsDialog)
- View skeleton creation (straightforward Qt layouts)
- Mixin method copying (well-isolated logic)

### Medium Risk
- Signal/slot rewiring (many connections to update)
- State management (need to ensure settings propagate correctly)
- Queue file watcher (needs to work with new architecture)

### High Risk
- Transcript viewer migration (complex UI with media player)
- Workspace artifact viewer (many interdependencies)
- Maintaining backward compatibility (settings/state files)

## Testing Strategy

### Unit Tests
- SettingsDialog: load/save/validate
- View creation: ensure all widgets initialized
- Settings propagation: verify updates reach views

### Integration Tests
- Single task flow: source → settings → transcribe → view
- Queue flow: add items → edit settings → process → complete
- Library flow: search → open → rebind media

### Manual Tests
- All buttons and menus functional
- Drag-drop works in all contexts
- Keyboard shortcuts work
- Window resize/layout behaves correctly
