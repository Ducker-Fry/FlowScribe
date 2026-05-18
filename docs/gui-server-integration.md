# GUI 内置 Server 功能

## 功能说明

GUI 的 Queue 标签现在包含内置的 Bookmarklet Server 控制，无需单独运行命令行。

## 使用步骤

### 1. 启动 GUI

```powershell
python -m flowscribe.gui
```

### 2. 打开 Queue 标签

点击 **Views** → **Queue**

### 3. 启用 Server

在 Queue 标签顶部的 "Bookmarklet Server" 区域：

1. **勾选 "Enable Server"** 复选框
2. **设置端口**（可选，默认 8765）
3. 服务器自动启动

**界面显示**：
```
☑ Enable Server    Port: [8765]    Server: Running on port 8765

Server running. Visit http://127.0.0.1:8765/bookmarklet.js for installation.
```

### 4. 安装 Bookmarklet

1. 访问 http://127.0.0.1:8765/bookmarklet.js
2. 复制显示的 JavaScript 代码
3. 在浏览器中创建书签，URL 填写复制的代码

### 5. 使用

1. 浏览任意视频网页
2. 点击 Bookmarklet 书签
3. URL 自动添加到 GUI 队列（实时刷新）
4. 点击 "Start Queue" 开始转录

### 6. 停止 Server

取消勾选 "Enable Server" 复选框

## 功能特点

### ✅ 自动配置

Server 使用 GUI 当前的设置：
- **输出目录**：从主界面的输出目录设置读取
- **输出格式**：从格式复选框读取（txt, md, json, srt, vtt）
- **模型**：从模型下拉框读取
- **语言**：从语言下拉框读取

### ✅ 实时同步

- Bookmarklet 添加 URL → 队列自动刷新
- 修改 GUI 设置 → 新添加的 URL 使用新设置
- 无需重启 server

### ✅ 状态显示

**Server 运行中**：
```
Server: Running on port 8765  (绿色)
Server running. Visit http://127.0.0.1:8765/bookmarklet.js for installation.
```

**Server 停止**：
```
Server: Stopped  (灰色)
Enable server to add URLs from browser. Visit http://127.0.0.1:8765/bookmarklet.js for installation.
```

**Server 错误**：
```
Server: Stopped  (灰色)
状态栏显示：Server error: Port 8765 is already in use
```

## 完整工作流程

```
1. 启动 GUI
   python -m flowscribe.gui

2. 打开 Views → Queue

3. 配置转录设置
   - 输出目录：E:\Transcripts
   - 格式：勾选 txt, srt
   - 模型：选择 small
   - 语言：选择 zh

4. 启用 Server
   ☑ Enable Server

5. 浏览器中使用 Bookmarklet
   - 打开 YouTube/Bilibili 视频
   - 点击 FlowScribe 书签
   - 弹出：✓ Added to FlowScribe queue Position: 1

6. GUI 自动刷新
   Queue 列表显示新添加的 URL

7. 开始转录
   点击 "Start Queue"

8. 完成后
   取消勾选 "Enable Server"（可选）
```

## 端口设置

**默认端口**：8765

**自定义端口**：
1. 在 "Port:" 输入框修改端口号（1024-65535）
2. 勾选 "Enable Server"
3. Server 在新端口启动

**端口冲突**：
- 如果端口被占用，状态栏显示错误
- 修改端口号后重新启用

## 与命令行 Server 的区别

| 功能 | GUI 内置 Server | 命令行 Server |
|------|----------------|--------------|
| 启动方式 | GUI 内勾选复选框 | `flowscribe serve` |
| 配置 | 自动读取 GUI 设置 | 命令行参数 |
| 日志 | 静默运行 | 详细日志输出 |
| 状态报告 | 无 | 每 30 秒报告 |
| 适用场景 | GUI 用户 | 命令行用户/服务器部署 |

## 注意事项

1. **Server 运行时不能修改端口**
   - 需要先停止 server，修改端口，再重新启用

2. **GUI 关闭时 Server 自动停止**
   - 如需持续运行，使用命令行 `flowscribe serve`

3. **设置实时生效**
   - 修改输出目录、格式、模型等设置后
   - 新添加的 URL 立即使用新设置
   - 已在队列中的 URL 不受影响

4. **队列文件共享**
   - GUI 和命令行 server 使用同一个队列文件
   - 可以混合使用（但不推荐同时运行两个 server）

## 故障排除

**问题：勾选后立即取消勾选**
- 原因：端口被占用
- 解决：修改端口号或关闭占用端口的程序

**问题：Bookmarklet 无反应**
- 检查：Server 状态是否显示 "Running"
- 检查：浏览器控制台（F12）是否有错误
- 解决：重新启用 Server

**问题：URL 添加后 GUI 不刷新**
- 原因：文件监听可能失效
- 解决：手动点击 "Add URLs" 或重启 GUI
