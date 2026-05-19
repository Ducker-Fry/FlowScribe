# FlowScribe Bookmarklet

一键添加网页音视频到 FlowScribe 转录队列的浏览器书签工具。

## 功能特性

### ✨ 智能 URL 提取
- **YouTube**: 自动提取标准格式 `youtube.com/watch?v=xxx`
  - 支持 `youtu.be` 短链接
  - 支持 `youtube.com/embed` 嵌入链接
- **Bilibili**: 自动提取 BV 号格式 `bilibili.com/video/BVxxx`
  - 支持 BV 号和 av 号
- **通用页面**: 使用完整 URL（支持所有 yt-dlp 兼容网站）

### 📋 元数据提取
- 自动读取页面标题（`document.title`）
- 优先使用 `og:title` meta 标签
- 清理常见网站后缀（如 " - YouTube"）
- **队列中显示标题而非 URL**

### 🎨 美化提示 UI
- 自定义通知框（不使用浏览器原生 `alert`）
- 渐变背景色 + 淡入淡出动画
- 右上角固定位置，不阻塞页面
- 不同状态显示不同颜色和图标

### 🛡️ 错误处理
- **网络超时**: 5 秒无响应自动提示
- **服务未启动**: 检测连接失败并提示
- **URL 格式不支持**: 验证 URL 有效性
- **重复检测**: 自动检测队列中的重复 URL

## 安装方法

### 方法 1: 使用安装页面（推荐）

1. 在浏览器中打开 `bookmarklet/index.html`
2. 将页面中的按钮拖拽到书签栏
3. 完成！

### 方法 2: 手动创建书签

1. 在浏览器书签栏右键，选择"添加书签"
2. 名称填写: `Add to FlowScribe`
3. URL 填写: 复制 `bookmarklet/flowscribe-bookmarklet.min.js` 的内容
4. 保存

## 使用步骤

### 1. 启动 FlowScribe 服务器

```powershell
flowscribe serve
```

服务器将在 `http://127.0.0.1:8765` 监听请求。

### 2. 浏览网页

访问任何包含音视频的网页，例如：
- YouTube 视频
- Bilibili 视频
- 播客网站
- 其他 yt-dlp 支持的网站

### 3. 点击 Bookmarklet

点击书签栏中的 "Add to FlowScribe" 按钮。

### 4. 查看通知

页面右上角会显示通知框：
- ✓ **成功**: 绿色渐变，显示标题和队列位置
- ⚠ **重复**: 橙色渐变，显示已存在状态
- ✗ **错误**: 红色渐变，显示错误信息

### 5. 打开 GUI 查看队列

```powershell
flowscribe gui
```

在 GUI 的"队列"标签页中查看和管理任务。任务将以**页面标题**显示，而非 URL。

## 错误提示说明

| 提示信息 | 原因 | 解决方法 |
|---------|------|---------|
| `Connection timeout (5s)` | 网络请求超时 | 检查服务器是否运行 |
| `Cannot connect to FlowScribe` | 服务器未启动 | 运行 `flowscribe serve` |
| `Invalid URL format` | URL 格式不支持 | 检查页面 URL 是否有效 |
| `Already in queue: pending` | URL 已在队列中 | 无需重复添加 |

## 高级配置

### 修改服务器地址

如果服务器运行在其他地址，编辑 `flowscribe-bookmarklet.js` 中的：

```javascript
const CONFIG = {
    serverUrl: 'http://127.0.0.1:8765',  // 改为你的服务器地址
    timeout: 5000,
    notificationDuration: 3000,
};
```

### 修改超时时间

默认 5 秒超时，可以修改 `timeout` 值（单位：毫秒）：

```javascript
timeout: 10000,  // 10 秒
```

### 修改通知显示时长

默认 3 秒自动消失，可以修改 `notificationDuration` 值：

```javascript
notificationDuration: 5000,  // 5 秒
```

## 文件说明

```
bookmarklet/
├── flowscribe-bookmarklet.js      # 完整版源代码（带注释）
├── flowscribe-bookmarklet.min.js  # 压缩版（用于书签）
├── index.html                     # 安装和测试页面
└── README.md                      # 本文档
```

## 技术细节

### URL 提取逻辑

**YouTube**:
```javascript
// youtu.be/xxx → youtube.com/watch?v=xxx
// youtube.com/embed/xxx → youtube.com/watch?v=xxx
// youtube.com/watch?v=xxx&list=... → youtube.com/watch?v=xxx
```

**Bilibili**:
```javascript
// 提取 BV 号: bilibili.com/video/BVxxx
// 提取 av 号: bilibili.com/video/avxxx
```

### 标题清理

自动移除常见网站后缀：
- ` - YouTube`
- ` - Bilibili` / ` - 哔哩哔哩`
- ` | Bilibili` / ` | 哔哩哔哩`

### 通知 UI 实现

- 使用 `position: fixed` 固定在右上角
- `z-index: 999999` 确保在最上层
- CSS 动画实现淡入淡出效果
- 自动清理 DOM 元素，避免内存泄漏

## 浏览器兼容性

- ✅ Chrome / Edge (推荐)
- ✅ Firefox
- ✅ Safari
- ⚠️ 需要支持 ES6+ (async/await, fetch API)

## 故障排查

### Bookmarklet 点击无反应

1. 检查浏览器控制台是否有错误
2. 确认服务器正在运行: `flowscribe serve`
3. 测试服务器连接: 访问 `http://127.0.0.1:8765/status`

### 通知框不显示

1. 检查页面是否有 CSP (Content Security Policy) 限制
2. 尝试在其他网站测试
3. 查看浏览器控制台错误信息

### URL 提取不正确

1. 检查页面 URL 格式
2. 查看 `flowscribe-bookmarklet.js` 中的提取逻辑
3. 可以手动修改提取规则

## 开发说明

### 修改源代码

编辑 `flowscribe-bookmarklet.js`，然后压缩：

```javascript
// 使用在线工具压缩，或使用 terser:
npx terser flowscribe-bookmarklet.js -c -m -o flowscribe-bookmarklet.min.js
```

### 测试

1. 启动服务器: `flowscribe serve`
2. 打开 `index.html` 安装 Bookmarklet
3. 访问测试页面并点击 Bookmarklet
4. 检查通知和队列

## 许可证

MIT License - 与 FlowScribe 主项目相同
