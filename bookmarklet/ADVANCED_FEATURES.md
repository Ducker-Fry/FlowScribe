# FlowScribe Bookmarklet - Advanced Features

## 功能版本对比

### 基础版 (flowscribe-bookmarklet.js)
- ✅ 智能 URL 提取（YouTube、Bilibili）
- ✅ 页面标题提取
- ✅ 美化通知 UI
- ✅ 错误处理
- ✅ 5秒超时保护

### 高级版 (flowscribe-bookmarklet-advanced.js)
- ✅ **所有基础版功能**
- ✅ **多视频检测与选择**
- ✅ **智能过滤（时长、广告、隐藏元素）**
- ✅ **快捷键支持（Alt+F）**
- ✅ **队列状态同步**
- ✅ **批量 URL 提交**

---

## 新增功能详解

### 6.1 多视频检测 ✅

**功能说明**：
- 自动检测页面上的所有 `<video>` 标签
- 如果检测到多个视频，弹出选择界面
- 用户可以勾选要添加的视频
- 批量发送到 FlowScribe

**实现细节**：
```javascript
// 检测所有视频元素
function detectVideos() {
    const videos = Array.from(document.querySelectorAll('video'));
    return videos
        .map((video, index) => ({
            element: video,
            index: index,
            src: getVideoSource(video),
            duration: video.duration || 0,
            width: video.videoWidth || video.offsetWidth,
            height: video.videoHeight || video.offsetHeight,
            visible: isVideoVisible(video),
        }))
        .filter(video => isValidVideo(video));
}
```

**选择界面**：
- 美化的对话框，显示每个视频的信息
- 显示视频尺寸和时长
- 默认全选，用户可以取消勾选
- "Add Selected" 按钮批量添加

---

### 6.2 智能过滤 ✅

**过滤规则**：

1. **时长过滤**：
   - 自动排除时长 < 10 秒的视频
   - 可配置：`CONFIG.minVideoDuration = 10`

2. **广告过滤**：
   - 排除 URL 包含 `ad`、`promo`、`advertisement`、`sponsor` 的视频
   - 可配置：`CONFIG.adKeywords = ['ad', 'promo', ...]`

3. **可见性过滤**：
   - 排除 `display: none` 的视频
   - 排除 `visibility: hidden` 的视频
   - 排除 `opacity: 0` 的视频
   - 排除尺寸为 0 的视频

4. **尺寸过滤**：
   - 排除宽度 < 200px 或高度 < 150px 的视频
   - 避免添加缩略图或图标

**实现代码**：
```javascript
function isValidVideo(video) {
    // 可见性检查
    if (!video.visible) return false;

    // 时长检查
    if (video.duration > 0 && video.duration < CONFIG.minVideoDuration) {
        return false;
    }

    // 广告关键词检查
    const src = video.src.toLowerCase();
    if (CONFIG.adKeywords.some(keyword => src.includes(keyword))) {
        return false;
    }

    // 尺寸检查
    if (video.width < 200 || video.height < 150) {
        return false;
    }

    return true;
}
```

---

### 6.3 快捷键支持 ✅

**功能说明**：
- 用户可以按 **Alt+F** 触发 Bookmarklet
- 无需点击书签栏
- 更快捷的操作体验

**实现代码**：
```javascript
function setupKeyboardShortcut() {
    document.addEventListener('keydown', (event) => {
        if (event.altKey && event.key.toLowerCase() === 'f') {
            event.preventDefault();
            addToFlowScribe();
        }
    });
}

// 初始化时注册快捷键
setupKeyboardShortcut();
```

**使用方法**：
1. 访问任何视频页面
2. 按 **Alt+F**
3. Bookmarklet 自动执行

**注意事项**：
- 快捷键在页面加载后立即生效
- 如果页面已有 Alt+F 快捷键，可能会冲突
- 可以修改为其他组合键（如 Ctrl+Shift+F）

---

### 6.4 状态同步 ✅

**功能说明**：
- 添加 URL 后自动查询队列状态
- 显示当前队列中的任务数量
- 提供"打开 FlowScribe"提示

**实现代码**：
```javascript
async function getQueueStatus() {
    try {
        const response = await fetchWithTimeout(
            `${CONFIG.serverUrl}/status`,
            { method: 'GET' },
            CONFIG.timeout
        );
        return await response.json();
    } catch (error) {
        return null;
    }
}

async function showQueueStatus() {
    const status = await getQueueStatus();
    if (!status) {
        showNotification('Cannot connect to FlowScribe', 'error');
        return;
    }

    const queue = status.queue;
    showNotification(
        `Queue: ${queue.pending} pending, ${queue.completed} completed`,
        'info'
    );
}
```

**显示内容**：
- Total: 总任务数
- Pending: 待处理任务
- Running: 正在处理
- Completed: 已完成

**时机**：
- 添加 URL 成功后 1.5 秒自动显示
- 用户可以看到队列的实时状态

---

## 批量 URL 提交

**功能说明**：
- 支持一次性添加多个视频
- 使用 `/add-urls` 端点
- 返回批量操作摘要

**实现代码**：
```javascript
async function addVideosToQueue(videos) {
    const title = extractTitle();
    const urls = videos.map((video, idx) => ({
        url: video.src,
        title: videos.length > 1 ? `${title} - Part ${idx + 1}` : title,
    }));

    const response = await fetchWithTimeout(
        `${CONFIG.serverUrl}/add-urls`,
        {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ urls: urls }),
        },
        CONFIG.timeout
    );

    const data = await response.json();
    const summary = data.summary;

    showNotification(
        `Added ${summary.queued} videos\n` +
        `Duplicates: ${summary.duplicates} | Errors: ${summary.errors}`,
        summary.errors > 0 ? 'warning' : 'success'
    );
}
```

**命名规则**：
- 单个视频：使用页面标题
- 多个视频：`标题 - Part 1`、`标题 - Part 2`...

---

## 配置选项

```javascript
const CONFIG = {
    serverUrl: 'http://127.0.0.1:8765',  // 服务器地址
    timeout: 5000,                        // 请求超时（毫秒）
    notificationDuration: 3000,           // 通知显示时长（毫秒）
    minVideoDuration: 10,                 // 最小视频时长（秒）
    adKeywords: [                         // 广告关键词
        'ad',
        'promo',
        'advertisement',
        'sponsor'
    ],
};
```

---

## 使用场景

### 场景 1: 单视频页面（YouTube、Bilibili）
1. 访问视频页面
2. 按 Alt+F 或点击书签
3. 自动提取 URL 和标题
4. 添加到队列
5. 显示队列状态

### 场景 2: 多视频页面（播放列表、课程页面）
1. 访问包含多个视频的页面
2. 按 Alt+F 或点击书签
3. 弹出视频选择对话框
4. 勾选要添加的视频
5. 点击 "Add Selected"
6. 批量添加到队列
7. 显示添加摘要和队列状态

### 场景 3: 嵌入视频页面
1. 访问包含嵌入视频的页面
2. 按 Alt+F
3. 自动检测 `<video>` 标签
4. 智能过滤广告和无效视频
5. 添加有效视频到队列

---

## 安装方法

### 方法 1: 拖拽安装（推荐）
1. 打开 `bookmarklet/index.html`
2. 拖拽"高级版"按钮到书签栏

### 方法 2: 手动创建
1. 书签栏右键 → "添加书签"
2. 名称：`FlowScribe (Advanced)`
3. URL：复制 `flowscribe-bookmarklet-advanced.min.js` 的内容
4. 保存

---

## 浏览器兼容性

- ✅ Chrome / Edge (推荐)
- ✅ Firefox
- ✅ Safari
- ⚠️ 需要支持 ES6+ (async/await, fetch API)
- ⚠️ 快捷键在某些网站可能被拦截

---

## 故障排查

### 快捷键不生效
- 检查页面是否已有 Alt+F 快捷键
- 尝试刷新页面后再按快捷键
- 某些网站（如 Gmail）可能拦截快捷键

### 多视频检测不准确
- 检查页面是否使用 `<video>` 标签
- 某些网站使用 Flash 或自定义播放器
- 可以手动添加页面 URL

### 队列状态不显示
- 确认服务器正在运行
- 检查 `/status` 端点是否可访问
- 查看浏览器控制台错误信息

---

## 开发说明

### 修改快捷键

将 `Alt+F` 改为 `Ctrl+Shift+F`：

```javascript
document.addEventListener('keydown', (event) => {
    if (event.ctrlKey && event.shiftKey && event.key.toLowerCase() === 'f') {
        event.preventDefault();
        addToFlowScribe();
    }
});
```

### 修改过滤规则

调整最小视频时长为 30 秒：

```javascript
const CONFIG = {
    minVideoDuration: 30,  // 改为 30 秒
    // ...
};
```

添加更多广告关键词：

```javascript
const CONFIG = {
    adKeywords: ['ad', 'promo', 'advertisement', 'sponsor', 'banner', 'popup'],
    // ...
};
```

---

## 未来计划

- [ ] 自定义快捷键设置
- [ ] 视频预览缩略图
- [ ] 更多平台支持（Twitter、Instagram）
- [ ] 本地存储配置
- [ ] 深色模式支持

---

## 许可证

MIT License - 与 FlowScribe 主项目相同
