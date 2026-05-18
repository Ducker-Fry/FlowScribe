# Server 配置选项

## 基本使用

**使用默认设置**：
```powershell
python -m flowscribe serve
```

默认配置：
- 输出目录：`~/Documents/FlowScribe`
- 输出格式：`json`
- 模型：`small`
- 语言：自动检测

## 自定义配置

### 1. 自定义输出目录

```powershell
python -m flowscribe serve -o E:\Transcripts
```

或：
```powershell
python -m flowscribe serve --output-dir E:\Transcripts
```

### 2. 自定义输出格式

**单个格式**：
```powershell
python -m flowscribe serve --format txt
```

**多个格式**（逗号分隔）：
```powershell
python -m flowscribe serve --format txt,md,json
```

### 3. 自定义模型

```powershell
python -m flowscribe serve -m medium
```

可选模型：`tiny`, `small`, `medium`, `large-v3`

### 4. 指定语言

**中文**：
```powershell
python -m flowscribe serve -l zh
```

**英文**：
```powershell
python -m flowscribe serve -l en
```

**自动检测**（默认）：
```powershell
python -m flowscribe serve
```

### 5. 组合配置

```powershell
python -m flowscribe serve \
  -o E:\Transcripts \
  --format txt,md,json,srt \
  -m medium \
  -l zh \
  --port 9000
```

## 完整示例

**场景：中文视频转录，输出到自定义目录**

```powershell
python -m flowscribe serve \
  --output-dir E:\Videos\Transcripts \
  --format txt,srt \
  --model small \
  --language zh
```

启动后显示：
```
======================================================================
FlowScribe Bookmarklet Server
======================================================================
Listening on: http://127.0.0.1:8765
Queue store:  C:\Users\...\AppData\Local\FlowScribe\batch-queue.json

Default Settings:
  Output dir:  E:\Videos\Transcripts
  Formats:     txt, srt
  Model:       small
  Language:    zh

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
```

## 配置优先级

1. **命令行参数**（最高优先级）
2. **默认值**

## 常用配置组合

### 快速测试（最快速度）
```powershell
python -m flowscribe serve -m tiny --format txt
```

### 高质量中文转录
```powershell
python -m flowscribe serve \
  -o E:\Transcripts \
  --format txt,md,srt \
  -m medium \
  -l zh
```

### 英文视频带字幕
```powershell
python -m flowscribe serve \
  -o E:\English\Transcripts \
  --format txt,srt,vtt \
  -m small \
  -l en
```

### 多语言自动检测
```powershell
python -m flowscribe serve \
  -o E:\Mixed\Transcripts \
  --format txt,md,json \
  -m small
```

## 验证配置

启动服务器后，查看 "Default Settings" 部分确认配置正确。

或者通过 API 查询：
```powershell
Invoke-WebRequest http://127.0.0.1:8765/status | Select-Object -ExpandProperty Content
```

## 注意事项

1. **输出目录**会自动创建（如果不存在）
2. **格式**必须是支持的格式：`txt`, `md`, `json`, `srt`, `vtt`
3. **模型**首次使用会自动下载
4. **语言代码**使用 ISO 639-1 标准（如 `zh`, `en`, `ja`, `ko`）
5. 配置只影响**通过 Bookmarklet 添加的新 URL**，不影响已在队列中的项目
