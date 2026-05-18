# Bookmarklet 集成指南

FlowScribe 支持通过浏览器 Bookmarklet 快速添加网页视频/音频到转录队列。

## 快速开始

### 方式 1：GUI 内置 Server（推荐）

**最简单的方式，无需命令行**

1. **启动 GUI**
   ```powershell
   python -m flowscribe.gui
   ```

2. **打开 Queue 标签**
   - 点击 **Views** → **Queue**

3. **启用 Server**
   - 勾选 **"Enable Server"** 复选框
   - 可选：修改端口（默认 8765）
   - 状态显示：`Server: Running on port 8765` (绿色)

4. **安装 Bookmarklet**
   - 访问 http://127.0.0.1:8765/bookmarklet.js
   - 复制显示的 JavaScript 代码
   - 在浏览器中创建书签，URL 填写复制的代码

5. **使用**
   - 浏览任意视频网页
   - 点击 Bookmarklet 书签
   - URL 自动添加到 GUI 队列
   - 点击 "Start Queue" 开始转录

### 方式 2：命令行 Server

**适合需要持续运行或自定义配置的场景**

1. **启动 Server**
   ```powershell
   python -m flowscribe serve
   ```

   或自定义配置：
   ```powershell
   python -m flowscribe serve -o E:\Transcripts --format txt,srt -m medium -l zh
   ```

2. **安装 Bookmarklet**（同上）

3. **启动 GUI**（可选）
   ```powershell
   python -m flowscribe.gui
   ```
   - 打开 Views → Queue 查看队列
   - 点击 "Start Queue" 开始转录

## Bookmarklet 脚本

### 获取脚本的方式

**自动获取（推荐）**：
1. 启动 Server（GUI 或命令行）
2. 访问 http://127.0.0.1:8765/bookmarklet.js
3. 复制显示的完整代码

**手动复制**：
```javascript
javascript:(function(){var url=window.location.href;var title=document.title;fetch('http://127.0.0.1:8765/add-url',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:url,title:title,timestamp:new Date().toISOString()})}).then(r=>r.json()).then(d=>{if(d.status==='queued'){alert('✓ Added to FlowScribe queue\nPosition: '+d.position);}else if(d.status==='duplicate'){alert('⚠ Already in queue: '+d.existing_status);}else{alert('✗ Error: '+d.message);}}).catch(e=>alert('✗ Connection failed. Is FlowScribe server running?'));})();
```

### 安装到浏览器

**Edge / Chrome**：
1. 按 `Ctrl+Shift+O` 打开收藏夹管理器
2. 右键点击收藏夹栏 → "添加收藏"
3. **名称**：`FlowScribe`
4. **URL**：粘贴上面的完整脚本（从 `javascript:` 开始）
5. 保存

**Firefox**：
1. 按 `Ctrl+Shift+B` 打开书签管理器
2. 右键点击书签工具栏 → "添加书签"
3. **名称**：`FlowScribe`
4. **位置**：粘贴脚本
5. 保存

### 脚本功能说明

这个脚本会：
1. ✅ 获取**当前页面的 URL**：`window.location.href`
2. ✅ 获取**当前页面的标题**：`document.title`
3. ✅ 发送到 FlowScribe Server：`http://127.0.0.1:8765/add-url`
4. ✅ 显示友好的结果提示

**成功添加**：
```
✓ Added to FlowScribe queue
Position: 1
```

**重复 URL**：
```
⚠ Already in queue: pending
```

**连接失败**：
```
✗ Connection failed. Is FlowScribe server running?
```

## 使用示例

### 场景 1：使用 GUI（最简单）

```
1. 启动 GUI
   python -m flowscribe.gui

2. 打开 Views → Queue
   勾选 "Enable Server"

3. 浏览器中访问 YouTube
   https://www.youtube.com/watch?v=dQw4w9WgXcQ

4. 点击 FlowScribe 书签
   弹出：✓ Added to FlowScribe queue Position: 1

5. 返回 GUI
   Queue 列表自动显示新 URL

6. 点击 "Start Queue"
   开始转录
```

### 场景 2：使用命令行 Server

```
终端 1 - 启动 Server：
python -m flowscribe serve -o E:\Transcripts --format txt,srt -l zh

终端 2 - 启动 GUI（可选）：
python -m flowscribe.gui

浏览器：
点击 Bookmarklet → URL 添加到队列

GUI：
打开 Views → Queue → Start Queue
```

### 场景 3：批量添加

```
1. 浏览多个视频页面
2. 每个页面点击 Bookmarklet
3. 所有 URL 自动添加到队列
4. 在 GUI 中一次性批量转录
```

## 配置说明

### GUI Server 配置

Server 自动使用 GUI 当前设置：
- **输出目录**：主界面的输出目录
- **输出格式**：勾选的格式（txt, md, json, srt, vtt）
- **模型**：下拉框选择的模型
- **语言**：下拉框选择的语言

**修改配置**：
1. 在 GUI 主界面修改设置
2. 新添加的 URL 自动使用新设置
3. 无需重启 Server

### 命令行 Server 配置

```powershell
# 基本用法
python -m flowscribe serve

# 自定义输出目录
python -m flowscribe serve -o E:\Transcripts

# 自定义格式
python -m flowscribe serve --format txt,md,srt

# 自定义模型和语言
python -m flowscribe serve -m medium -l zh

# 完整配置
python -m flowscribe serve \
  -o E:\Videos\Transcripts \
  --format txt,srt \
  -m small \
  -l zh \
  --port 9000
```

## API 端点

### POST /add-url

添加单个 URL 到队列。

**请求体**：
```json
{
  "url": "https://example.com/video",
  "title": "Video Title",
  "timestamp": "2026-05-18T10:00:00Z"
}
```

**响应**：
```json
{
  "status": "queued",
  "position": 1,
  "item_id": "abc123def456"
}
```

### POST /add-urls

批量添加 URL。

**请求体**：
```json
{
  "urls": [
    "https://example.com/video1",
    {"url": "https://example.com/video2", "title": "Video 2"}
  ]
}
```

### GET /status

获取服务器和队列状态。

**响应**：
```json
{
  "status": "running",
  "queue": {
    "total": 5,
    "pending": 3,
    "running": 1,
    "completed": 1,
    "failed": 0
  }
}
```

### GET /bookmarklet.js

获取 Bookmarklet JavaScript 代码。

## 安全说明

- ✅ Server 默认仅监听 `127.0.0.1`（本地回环），不接受外部连接
- ✅ URL 验证会阻止私有 IP 地址（192.168.x.x, 10.x.x.x, 127.x.x.x）
- ✅ 支持 CORS 以允许浏览器跨域请求
- ✅ 仅接受 HTTP/HTTPS URL

## 故障排除

### 问题：点击 Bookmarklet 显示 "Connection failed"

**原因**：Server 未运行

**解决**：
1. GUI 方式：打开 Views → Queue，勾选 "Enable Server"
2. 命令行方式：运行 `python -m flowscribe serve`
3. 验证：访问 http://127.0.0.1:8765/status

### 问题：提示 "Port already in use"

**原因**：端口被占用

**解决**：
1. GUI：修改端口号后重新启用
2. 命令行：`python -m flowscribe serve --port 9000`
3. 或关闭占用端口的程序：`netstat -ano | findstr :8765`

### 问题：URL 被拒绝

**原因**：URL 不符合安全要求

**常见情况**：
- 私有 IP 地址（如 `http://192.168.1.1`）
- 非 HTTP/HTTPS 协议（如 `ftp://`）
- 无效的 URL 格式

**解决**：确保 URL 是公开的 HTTP/HTTPS 地址

### 问题：GUI 队列不刷新

**原因**：文件监听可能失效

**解决**：
1. 手动刷新：点击 "Add URLs" 按钮
2. 重启 GUI
3. 检查队列文件权限

### 问题：Bookmarklet 无反应

**检查**：
1. Server 状态是否显示 "Running"
2. 浏览器控制台（F12）是否有错误
3. 端口是否正确（默认 8765）

**解决**：
1. 重新启用 Server
2. 重新安装 Bookmarklet
3. 清除浏览器缓存

## 高级用法

### 自定义端口

**GUI**：
- 在 Port 输入框修改端口号
- 勾选 "Enable Server"

**命令行**：
```powershell
python -m flowscribe serve --port 9000
```

**更新 Bookmarklet**：
- 修改脚本中的端口号：`http://127.0.0.1:9000/add-url`

### 批量导入 + Bookmarklet 混合使用

```
1. 从文件导入一批 URL
   GUI: Import File → 选择 .txt/.csv/.xlsx

2. 浏览器中继续添加
   点击 Bookmarklet 添加新 URL

3. 统一处理
   Start Queue 批量转录所有 URL
```

### 与其他工具集成

**通过 API 调用**：
```powershell
# PowerShell
$body = @{url="https://example.com/video"; title="Test"} | ConvertTo-Json
Invoke-WebRequest -Uri http://127.0.0.1:8765/add-url -Method POST -Body $body -ContentType "application/json"

# Python
import requests
requests.post('http://127.0.0.1:8765/add-url', json={'url': 'https://example.com/video'})
```

## 相关文档

- [Server 配置选项](server-configuration.md) - 命令行 Server 详细配置
- [Server 输出示例](server-output-example.md) - 命令行 Server 日志示例
- [GUI Server 集成](gui-server-integration.md) - GUI 内置 Server 详细说明
