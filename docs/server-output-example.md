# Server 输出示例

## 启动服务器

```powershell
PS E:\Draft\FlowScribe> python -m flowscribe serve
```

**输出**：
```
======================================================================
FlowScribe Bookmarklet Server
======================================================================
Listening on: http://127.0.0.1:8765
Queue store:  C:\Users\YourName\AppData\Local\FlowScribe\batch-queue.json

Bookmarklet Installation:
  1. Visit http://127.0.0.1:8765/bookmarklet.js
  2. Copy the JavaScript code
  3. Create a bookmark in your browser with the code as URL

API Endpoints:
  POST http://127.0.0.1:8765/add-url     - Add single URL
  POST http://127.0.0.1:8765/add-urls    - Add multiple URLs
  GET  http://127.0.0.1:8765/status      - Get queue status

Status reports will be shown every 30 seconds
Press Ctrl+C to stop
======================================================================

10:30:15 🚀 FlowScribe Bookmarklet server listening on 127.0.0.1:8765
10:30:15 📁 Queue store: C:\Users\YourName\AppData\Local\FlowScribe\batch-queue.json
10:30:15 Press Ctrl+C to stop
10:30:15
```

## 实时请求日志

**用户在浏览器点击 Bookmarklet**：

```
10:30:45 ✅ Added to queue (position 1): https://www.youtube.com/watch?v=dQw4w9WgXcQ - Rick Astley - Never Gonna Give You Up...
```

**重复添加相同 URL**：

```
10:31:02 ⚠️  Duplicate URL (status: pending): https://www.youtube.com/watch?v=dQw4w9WgXcQ...
```

**添加无效 URL**：

```
10:31:15 ❌ Failed to add URL: not-a-valid-url - Invalid URL: URL input only supports http and https URLs.
```

**批量添加 URL**：

```
10:31:30 📦 Batch add completed: 3 queued, 1 duplicates, 0 errors (total: 4)
```

**状态查询**：

```
10:31:45 📊 Status check - Queue: 4 total, 3 pending, 1 completed
```

## 定期状态报告

**每 30 秒自动显示**：

```
10:32:00 📊 Queue Status: 4 total | 3 pending | 0 running | 1 completed | 0 failed
10:32:30 📊 Queue Status: 4 total | 2 pending | 1 running | 1 completed | 0 failed
10:33:00 📊 Queue Status: 4 total | 1 pending | 1 running | 2 completed | 0 failed
10:33:30 📊 Queue Status: 4 total | 0 pending | 0 running | 4 completed | 0 failed
```

## 停止服务器

**按 Ctrl+C**：

```
^C
10:34:00 ⏹️  Shutting down server...

✓ Server stopped
```

## 错误处理

**端口已被占用**：

```
❌ Error: Port 8765 is already in use
   Try a different port: flowscribe serve --port 8766
```

## 完整工作流程示例

```
======================================================================
FlowScribe Bookmarklet Server
======================================================================
Listening on: http://127.0.0.1:8765
Queue store:  C:\Users\YourName\AppData\Local\FlowScribe\batch-queue.json
...
======================================================================

10:30:15 🚀 FlowScribe Bookmarklet server listening on 127.0.0.1:8765
10:30:15 📁 Queue store: C:\Users\YourName\AppData\Local\FlowScribe\batch-queue.json
10:30:15 Press Ctrl+C to stop
10:30:15

# 用户在浏览器添加 URL
10:30:45 ✅ Added to queue (position 1): https://www.youtube.com/watch?v=abc123 - Tutorial Video...
10:31:02 ✅ Added to queue (position 2): https://www.bilibili.com/video/BV1xx411c7mD - 中文视频标题...
10:31:15 ⚠️  Duplicate URL (status: pending): https://www.youtube.com/watch?v=abc123...

# 第一次状态报告（30秒后）
10:31:45 📊 Queue Status: 2 total | 2 pending | 0 running | 0 completed | 0 failed

# 用户在 GUI 中启动队列处理
10:32:10 ✅ Added to queue (position 3): https://example.com/video3 - Another Video...

# 第二次状态报告
10:32:15 📊 Queue Status: 3 total | 2 pending | 1 running | 0 completed | 0 failed

# 继续添加和处理
10:32:30 ✅ Added to queue (position 4): https://example.com/video4...
10:32:45 📊 Queue Status: 4 total | 2 pending | 1 running | 1 completed | 0 failed

# 用户停止服务器
^C
10:33:00 ⏹️  Shutting down server...

✓ Server stopped
```

## 日志符号说明

- 🚀 服务器启动
- 📁 队列文件路径
- ✅ 成功添加 URL
- ⚠️  警告（重复 URL）
- ❌ 错误（无效 URL、请求失败）
- 📦 批量操作完成
- 📊 状态报告/查询
- 📜 Bookmarklet 脚本请求
- ⏹️  服务器关闭
