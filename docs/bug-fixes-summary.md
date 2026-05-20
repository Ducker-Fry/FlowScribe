# Bug Fixes Summary

## Issues Fixed

### 1. Library Missing Entries Cleanup ✅
**Problem**: 点击"Clean Missing Entries"按钮无法清理丢失的项目

**Root Cause**: 没有先调用`refresh_missing_statuses()`来检测丢失的项目

**Fix**: 
- 文件：`src/flowscribe/gui/new_main_window.py`
- 在`_on_library_cleanup_missing()`中先调用`refresh_missing_statuses()`
- 然后再调用`remove_missing_entries()`

```python
def _on_library_cleanup_missing(self) -> None:
    # First refresh to detect missing entries
    self._library_store.refresh_missing_statuses()
    # Then remove them
    removed = self._library_store.remove_missing_entries()
    self._library_view.refresh_library()
    self.statusBar().showMessage(f"Removed {len(removed)} missing entries")
```

### 2. Queue Store Method Name Error ✅
**Problem**: `AttributeError: 'BatchQueueStore' object has no attribute 'list_items'`

**Root Cause**: 方法名错误，应该是`load_items()`而不是`list_items()`

**Fix**:
- 文件：`src/flowscribe/gui/new_main_window.py`
- 修改：`list_items()` → `load_items()`

### 3. QueueItem.with_settings AttributeError ✅
**Problem**: `AttributeError: 'QueueItem' object has no attribute 'with_settings'`

**Root Cause**: `QueueItem`是frozen dataclass，没有`with_settings()`方法

**Fix**:
- 文件：`src/flowscribe/gui/new_main_window.py`
- 导入：`from dataclasses import replace`
- 使用：`replace(item, settings=updated_settings)`代替`item.with_settings()`

### 4. Duplicate Settings Button ✅
**Problem**: 工具栏和SingleTaskView都有Settings按钮，重复了

**Fix**:
- 文件：`src/flowscribe/gui/new_main_window.py`
- 移除工具栏的Settings按钮
- 保留SingleTaskView中的Settings按钮

### 5. Missing Output Name in Queue Settings ✅
**Problem**: Queue项目设置中缺少output_name字段

**Fix**:
- 文件：`src/flowscribe/queue/models.py`
  - 添加：`output_name_base: str = ""`到`QueueItemSettings`
- 文件：`src/flowscribe/gui/dialogs/queue_item_settings_dialog.py`
  - 添加：`output_name_input`字段
  - 更新：`_load_settings()`和`get_settings()`方法
- 文件：`src/flowscribe/gui/new_main_window.py`
  - 更新：`_settings_to_queue_settings()`包含`output_name_base`

### 6. Library Missing Select All Button ✅
**Problem**: Library视图缺少"Select All"按钮

**Fix**:
- 文件：`src/flowscribe/gui/views/library_view.py`
- 添加："Select All"按钮
- 实现：`_on_select_all()`方法调用`selectAll()`

### 7. Library Cleanup Auto-Detection ✅
**Problem**: 点击清理按钮时不自动检测丢失项

**Fix**:
- 文件：`src/flowscribe/gui/views/library_view.py`
- 改进：`_on_cleanup_missing()`先检测丢失项数量
- 如果没有丢失项，显示提示信息

### 8. Missing Open Transcript Button ✅
**Problem**: SingleTaskView缺少打开transcript的按钮

**Fix**:
- 文件：`src/flowscribe/gui/views/single_task_view.py`
- 添加："Open Transcript"按钮
- 实现：`_open_transcript()`方法打开文件选择器

### 9. Workspace Transcript Viewer Not Working ✅
**Problem**: 打开JSON转写文件没有反应，workspace无法显示

**Fix**:
- 文件：`src/flowscribe/gui/views/single_task_view.py`
- 替换：Workspace tab的placeholder为实际的`QPlainTextEdit`
- 实现：完整的`_open_transcript()`方法
  - 读取JSON文件
  - 解析segments
  - 格式化显示（时间戳 + 文本）
  - 自动切换到Workspace tab
- 添加：`transcript_loaded`信号

## Modified Files

```
src/flowscribe/gui/new_main_window.py              5 fixes
src/flowscribe/gui/views/library_view.py           3 fixes
src/flowscribe/gui/views/single_task_view.py       3 fixes
src/flowscribe/gui/dialogs/queue_item_settings_dialog.py  2 fixes
src/flowscribe/queue/models.py                     1 fix
```

## Testing

### Lint Check ✅
```bash
python -m ruff check src/flowscribe/gui/new_main_window.py src/flowscribe/gui/views/ src/flowscribe/gui/dialogs/queue_item_settings_dialog.py src/flowscribe/queue/models.py
```
**Result**: All checks passed!

### Manual Testing Required
- [ ] Library: Clean missing entries
- [ ] Library: Select all entries
- [ ] Queue: Edit item settings with output name
- [ ] SingleTask: Open transcript JSON
- [ ] Workspace: View transcript segments

## Summary

所有9个问题已修复：
1. ✅ Library清理丢失项现在可以工作
2. ✅ Queue store方法名错误已修复
3. ✅ Queue item设置编辑已修复
4. ✅ 重复的Settings按钮已移除
5. ✅ Queue设置中添加了output name字段
6. ✅ Library添加了Select All按钮
7. ✅ Library清理自动检测丢失项
8. ✅ SingleTask添加了Open Transcript按钮
9. ✅ Workspace可以显示transcript内容

所有代码通过linting检查，可以重新测试GUI！
