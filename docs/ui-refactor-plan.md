# FlowScribe UI Architecture Refactor Plan

## 目标

将当前的"主窗口+Views窗口"架构重构为"单一主窗口+任务绑定"架构。

## 当前架构问题

1. **Settings/Run Details/Workspace在独立的Views窗口中**，与转写任务没有绑定关系
2. **主窗口只是启动器**，真正的工作界面在Views窗口
3. **Queue只支持URL**，不支持本地文件作为任务
4. **Settings是嵌入式面板**，占用大量空间

## 目标架构

```
主窗口 (MainWindow)
├── 工具栏
│   ├── Settings按钮 → 打开设置对话框
│   ├── Library按钮 → 切换到Library视图
│   └── Queue按钮 → 切换到Queue视图
├── 主视图区域 (QStackedWidget)
│   ├── [0] 单任务转写视图 (SingleTaskView)
│   │   ├── 源选择区域
│   │   │   ├── 本地文件列表 (支持拖拽、多选)
│   │   │   ├── URL输入
│   │   │   └── 系统音频捕获
│   │   ├── 转写控制
│   │   │   ├── Start按钮
│   │   │   ├── Cancel按钮
│   │   │   └── 进度条
│   │   ├── Run Details (转写进度详情)
│   │   └── Workspace (转写结果查看/编辑)
│   ├── [1] Library视图 (LibraryView)
│   │   ├── 搜索/过滤
│   │   ├── 转写记录列表
│   │   └── 操作按钮 (Open/Delete/Rebind)
│   └── [2] Queue视图 (QueueView)
│       ├── 添加任务区域
│       │   ├── 添加本地文件
│       │   ├── 添加URL
│       │   └── 从文件导入
│       ├── 任务列表 (支持checkbox、拖拽排序)
│       ├── 任务操作
│       │   ├── Edit Settings (每个任务独立设置)
│       │   ├── Start Queue
│       │   ├── Remove Selected
│       │   └── Select All
│       └── Bookmarklet Server控制
└── 状态栏
    └── 全局状态信息
```

## 实施步骤

### Phase 1: 准备工作 (1-2小时)

#### Step 1.1: 创建新的UI组件骨架
```
src/flowscribe/gui/views/
├── __init__.py
├── single_task_view.py      # 单任务转写视图
├── library_view.py           # Library视图 (从现有代码迁移)
└── queue_view.py             # Queue视图 (从现有代码迁移)

src/flowscribe/gui/dialogs/
├── __init__.py
├── settings_dialog.py        # 设置对话框 (新建)
└── queue_item_settings_dialog.py  # 已存在
```

#### Step 1.2: 分析现有代码依赖
- 列出`main_window.py`中需要保留的方法
- 列出Views窗口中需要迁移的功能
- 确定哪些mixin可以复用

### Phase 2: 创建Settings对话框 (2-3小时)

#### Step 2.1: 创建SettingsDialog
**文件**: `src/flowscribe/gui/dialogs/settings_dialog.py`

**内容**:
- 复用当前主窗口的Settings区域布局
- 添加OK/Cancel/Apply按钮
- 返回更新后的设置（类似QueueItemSettingsDialog）

**字段**:
```python
- output_dir: Path
- output_name_base: str
- model_name: str
- language: str | None
- preset: str | None
- output_formats: tuple[str, ...]
- timestamps: bool
- word_timestamps: bool
- overwrite: bool
- network_family: str
- proxy: str | None
- cookies_path: Path | None
- progressive_enabled: bool
- progressive_resume: bool
- progressive_chunk_seconds: float
- progressive_max_workers: int
```

#### Step 2.2: 集成到主窗口
- 添加"Settings"工具栏按钮
- 连接到`_show_settings_dialog()`方法
- 保存设置到`_current_settings`成员变量

### Phase 3: 创建SingleTaskView (3-4小时)

#### Step 3.1: 设计SingleTaskView布局
**文件**: `src/flowscribe/gui/views/single_task_view.py`

**布局**:
```
QVBoxLayout
├── 源选择区域 (QGroupBox "Source")
│   ├── 本地文件列表 (SourceListWidget - 复用现有)
│   ├── 文件操作按钮 (Add/Clear/Select All)
│   ├── URL输入 (QLineEdit)
│   ├── URL媒体保存选项
│   └── 系统音频捕获控制
├── 转写控制区域 (QHBoxLayout)
│   ├── Start按钮
│   ├── Cancel按钮
│   ├── Settings按钮
│   └── 进度条
├── QTabWidget
│   ├── [0] Run Details标签
│   │   └── 进度输出 (QTextEdit)
│   └── [1] Workspace标签
│       ├── 转写文本查看器
│       ├── 媒体播放器
│       └── 编辑工具
└── 状态栏信息 (QLabel)
```

#### Step 3.2: 迁移转写逻辑
- 从`TranscriptionControlsMixin`迁移`_start_transcription()`
- 从`TranscriptViewerControlsMixin`迁移查看器逻辑
- 从`WorkspaceControlsMixin`迁移工作区逻辑
- 保持与现有`TranscriptionWorker`的兼容性

### Phase 4: 扩展Queue支持本地文件 (2-3小时)

#### Step 4.1: 扩展QueueItem模型
**文件**: `src/flowscribe/queue/models.py`

**当前**:
```python
source: SourceSpec  # kind="url" only
```

**目标**:
```python
source: SourceSpec  # kind="local" or "url"
```

#### Step 4.2: 更新QueueView UI
**文件**: `src/flowscribe/gui/views/queue_view.py`

**添加功能**:
- "Add Local Files"按钮 → 文件选择对话框
- 支持拖拽本地文件到Queue列表
- 显示本地文件路径（而不只是URL）

**更新显示**:
```python
def _format_queue_item_display(item: QueueItem) -> str:
    if item.source.kind == "local":
        return f"[FILE] {Path(item.source.value).name}"
    else:
        return f"[URL] {item.source.value}"
```

#### Step 4.3: 更新Queue处理逻辑
- `QueueRunner`已经支持`SourceSpec(kind="local")`
- 确保`TranscriptionService`正确处理本地文件源

### Phase 5: 重构主窗口 (3-4小时)

#### Step 5.1: 简化MainWindow
**文件**: `src/flowscribe/gui/main_window.py`

**移除**:
- 嵌入式Settings面板（约100行）
- Views窗口创建逻辑（约300行）
- 复杂的标签页管理（约150行）

**保留**:
- 菜单栏
- 工具栏
- 状态栏
- 全局状态管理

**新增**:
```python
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._current_settings = self._load_default_settings()
        self._setup_ui()
    
    def _setup_ui(self):
        # 工具栏
        toolbar = self.addToolBar("Main")
        toolbar.addAction("Settings", self._show_settings_dialog)
        toolbar.addAction("Library", lambda: self._view_stack.setCurrentIndex(1))
        toolbar.addAction("Queue", lambda: self._view_stack.setCurrentIndex(2))
        
        # 主视图区域
        self._view_stack = QStackedWidget()
        self._single_task_view = SingleTaskView(self._current_settings)
        self._library_view = LibraryView()
        self._queue_view = QueueView(self._current_settings)
        
        self._view_stack.addWidget(self._single_task_view)
        self._view_stack.addWidget(self._library_view)
        self._view_stack.addWidget(self._queue_view)
        
        self.setCentralWidget(self._view_stack)
```

#### Step 5.2: 连接信号
```python
# Settings更新
self._settings_dialog.settings_changed.connect(self._on_settings_changed)

# 单任务视图
self._single_task_view.transcription_started.connect(...)
self._single_task_view.transcription_finished.connect(...)

# Queue视图
self._queue_view.queue_started.connect(...)
self._queue_view.item_completed.connect(...)
```

### Phase 6: 迁移Library和Queue视图 (2-3小时)

#### Step 6.1: 创建LibraryView
**文件**: `src/flowscribe/gui/views/library_view.py`

**迁移内容**:
- 从`LibraryControlsMixin`迁移所有逻辑
- 保持独立性，不依赖MainWindow

#### Step 6.2: 创建QueueView
**文件**: `src/flowscribe/gui/views/queue_view.py`

**迁移内容**:
- 从`QueueControlsMixin`和`QueueTabWidget`迁移
- 添加本地文件支持
- 保持Bookmarklet Server功能

### Phase 7: 测试和调试 (2-3小时)

#### Step 7.1: 单元测试
- 测试SettingsDialog的设置保存/加载
- 测试Queue本地文件添加
- 测试SingleTaskView的转写流程

#### Step 7.2: 集成测试
- 测试Settings → SingleTask的设置传递
- 测试Queue → SingleTask的任务执行
- 测试Library → SingleTask的转写记录打开

#### Step 7.3: UI/UX测试
- 测试所有按钮和菜单项
- 测试拖拽功能
- 测试键盘快捷键
- 测试窗口大小调整

### Phase 8: 清理和优化 (1-2小时)

#### Step 8.1: 删除废弃代码
- 删除Views窗口相关代码
- 删除废弃的mixin（如果完全迁移）
- 清理未使用的导入

#### Step 8.2: 更新文档
- 更新CLAUDE.md
- 更新用户文档
- 添加架构图

## 关键技术决策

### 1. Settings管理
**方案**: 使用全局Settings对象 + 对话框编辑
```python
@dataclass
class GlobalSettings:
    # 所有设置字段
    pass

class MainWindow:
    def __init__(self):
        self._settings = load_settings()
    
    def _show_settings_dialog(self):
        dialog = SettingsDialog(self, self._settings)
        if dialog.exec() == QDialog.Accepted:
            self._settings = dialog.get_settings()
            save_settings(self._settings)
            self._apply_settings_to_views()
```

### 2. 任务状态管理
**方案**: 每个视图独立管理自己的任务状态
```python
class SingleTaskView:
    def __init__(self, settings):
        self._current_job: TranscriptionJob | None = None
        self._worker: TranscriptionWorker | None = None
```

### 3. Queue本地文件支持
**方案**: 扩展现有SourceSpec，无需修改核心逻辑
```python
# 添加本地文件到Queue
source = SourceSpec(kind="local", value=str(file_path))
item = QueueItem(
    item_id=generate_queue_item_id(source),
    source=source,
    settings=current_settings,
)
queue_store.enqueue(item)
```

### 4. 视图切换
**方案**: 使用QStackedWidget + 工具栏按钮
```python
# 简单直接的视图切换
toolbar.addAction("Single Task", lambda: stack.setCurrentIndex(0))
toolbar.addAction("Library", lambda: stack.setCurrentIndex(1))
toolbar.addAction("Queue", lambda: stack.setCurrentIndex(2))
```

## 向后兼容性

### 保留的功能
- ✅ 所有转写功能（本地/URL/系统音频）
- ✅ Library功能（搜索/过滤/打开）
- ✅ Queue功能（批量处理/Bookmarklet）
- ✅ 设置保存/加载
- ✅ 转写记录持久化

### 移除的功能
- ❌ 独立的Views窗口
- ❌ 标签页可见性配置
- ❌ 嵌入式Settings面板

### 迁移路径
用户无需手动迁移，所有数据格式保持兼容：
- Library数据库格式不变
- Queue JSON格式不变（只是扩展支持local）
- Settings JSON格式不变

## 风险和缓解

### 风险1: 代码量大，容易出错
**缓解**: 分步实施，每步完成后测试

### 风险2: UI布局可能不符合预期
**缓解**: 先创建原型，确认布局后再实施

### 风险3: 现有功能可能丢失
**缓解**: 对照清单逐一验证功能迁移

## 验收标准

### 功能完整性
- [ ] 单任务转写（本地/URL/系统音频）正常工作
- [ ] Settings对话框可以编辑所有设置
- [ ] Queue支持添加本地文件和URL
- [ ] Queue每个项目可以独立设置
- [ ] Library可以搜索/打开历史记录
- [ ] Bookmarklet Server正常工作

### UI/UX
- [ ] 主窗口布局清晰，不拥挤
- [ ] 视图切换流畅
- [ ] 所有按钮和菜单项可用
- [ ] 拖拽功能正常
- [ ] 键盘快捷键正常

### 性能
- [ ] 启动速度不变慢
- [ ] 视图切换无延迟
- [ ] 转写性能不受影响

## 预计时间

- **Phase 1-2**: 3-5小时（准备 + Settings对话框）
- **Phase 3**: 3-4小时（SingleTaskView）
- **Phase 4**: 2-3小时（Queue扩展）
- **Phase 5**: 3-4小时（主窗口重构）
- **Phase 6**: 2-3小时（视图迁移）
- **Phase 7**: 2-3小时（测试）
- **Phase 8**: 1-2小时（清理）

**总计**: 16-24小时

## 开始新对话时的提示词

```
我需要重构FlowScribe的UI架构。请阅读 docs/ui-refactor-plan.md 了解详细计划。

当前架构问题：
1. Settings/Run Details/Workspace在独立的Views窗口中
2. 主窗口只是启动器
3. Queue只支持URL，不支持本地文件

目标架构：
1. 单一主窗口 + QStackedWidget切换视图
2. Settings改为对话框
3. Queue支持本地文件和URL
4. 每个转写任务绑定自己的Settings/Run Details/Workspace

请按照计划从Phase 1开始实施。
```

## 参考文件

实施时需要参考的关键文件：
- `src/flowscribe/gui/main_window.py` - 当前主窗口
- `src/flowscribe/gui/windows/*.py` - 各个mixin
- `src/flowscribe/gui/widgets/queue_tab_widget.py` - Queue UI
- `src/flowscribe/gui/dialogs/queue_item_settings_dialog.py` - 设置对话框参考
- `src/flowscribe/queue/models.py` - Queue数据模型
- `src/flowscribe/app/models.py` - 核心数据模型
