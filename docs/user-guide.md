# FlowScribe 用户指南

FlowScribe 是一个本地优先的音视频转录工具，支持本地文件、URL音频提取、结构化转录输出、关键词时间戳定位。提供命令行工具（CLI）和桌面图形界面（GUI）。

**当前版本**: v0.3.3  
**下一版本**: v1.0.0（准备中）

---

## 目录

- [CLI 命令行工具](#cli-命令行工具)
  - [1. 安装与环境检查](#1-安装与环境检查)
  - [2. 基础转录](#2-基础转录)
  - [3. URL 转录](#3-url-转录)
  - [4. 长音频渐进式转录](#4-长音频渐进式转录)
  - [5. 转录搜索](#5-转录搜索)
  - [6. 书签服务器](#6-书签服务器)
  - [7. 语言与模型](#7-语言与模型)
  - [8. 输出格式](#8-输出格式)
  - [9. 准确率优化](#9-准确率优化)
  - [10. 常见问题](#10-常见问题)
- [GUI 图形界面](#gui-图形界面)

---

## CLI 命令行工具

### 1. 安装与环境检查

#### 安装依赖

```powershell
cd E:\Draft\FlowScribe
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
```

#### 检查命令是否可用

```powershell
flowscribe --help
```

#### 环境检查

```powershell
flowscribe doctor
```

`doctor` 命令会检查：
- Python 版本
- `ffmpeg` 和 `ffprobe` 可用性
- `faster-whisper` 安装状态
- 输出目录写入权限
- 模型下载可达性

---

### 2. 基础转录

#### 转录单个文件

```powershell
flowscribe transcribe "D:\media\lecture.mp4" -o outputs
```

支持的常见格式：
```text
mp4, mkv, mov, avi, mp3, wav, m4a, flac, webm, ogg
```

#### 转录多个文件

```powershell
flowscribe transcribe "D:\media\file1.mp4" "D:\media\file2.mp3" -o outputs
```

#### 转录整个文件夹

```powershell
flowscribe transcribe "D:\media" -o outputs
```

#### 递归扫描子文件夹

```powershell
flowscribe transcribe "D:\media" -o outputs --recursive
```

#### 指定输出格式

```powershell
flowscribe transcribe "D:\media\lecture.mp4" -o outputs --format txt,md,json,srt,vtt
```

支持的输出格式：
- `txt` - 纯文本
- `md` - Markdown（带元信息）
- `json` - 结构化JSON（包含时间戳、分段信息）
- `srt` - 字幕文件
- `vtt` - WebVTT字幕文件

---

### 3. URL 转录

FlowScribe 支持从公开URL提取音频并转录（基于 yt-dlp）。

#### 基础URL转录

```powershell
flowscribe url "https://www.youtube.com/watch?v=VIDEO_ID" -o outputs
```

#### 检查URL信息

在转录前检查URL是否有音频流：

```powershell
flowscribe inspect "https://www.youtube.com/watch?v=VIDEO_ID"
```

#### 使用代理

如果使用 Clash 或其他本地代理：

```powershell
flowscribe url "https://www.youtube.com/watch?v=VIDEO_ID" --proxy "http://127.0.0.1:7890" -o outputs
```

#### 指定网络协议

如果DNS解析到被阻止的IPv6地址：

```powershell
flowscribe url "https://www.youtube.com/watch?v=VIDEO_ID" --network-family ipv4 -o outputs
```

#### 使用Cookies

对于需要登录的媒体（你有访问权限）：

```powershell
flowscribe url "https://example.com/video" --cookies "D:\private\cookies.txt" -o outputs
```

**注意**: 仅用于你有合法访问权限的内容。参见 [Cookies文档](cookies.md)。

#### 保留下载的媒体文件

默认情况下，URL转录完成后会删除临时音频文件。如需保留：

```powershell
flowscribe url "https://example.com/video" --keep-media -o outputs
```

#### 限制下载大小和时长

```powershell
# 限制最大下载100MB
flowscribe url "https://example.com/video" --max-download-mb 100 -o outputs

# 限制最大时长30分钟
flowscribe url "https://example.com/video" --max-duration 1800 -o outputs

# 设置下载超时（秒）
flowscribe url "https://example.com/video" --download-timeout 300 -o outputs
```

---

### 4. 长音频渐进式转录

对于长音频/视频（如2小时讲座、播客），FlowScribe 支持渐进式转录：
- 将音频分块处理
- 支持中断后恢复
- 显示实时进度和ETA
- 支持并行处理（实验性）

#### 自动模式（推荐）

FlowScribe 会自动判断是否使用渐进式转录：

```powershell
flowscribe transcribe "D:\media\long-lecture.mp4" -o outputs
```

- 单个长文件（>10分钟）：自动启用渐进式
- 多个文件批处理：使用经典模式

#### 强制启用渐进式转录

```powershell
flowscribe transcribe "D:\media\lecture.mp4" -o outputs --progressive
```

#### 自定义分块参数

```powershell
# 每块60秒，重叠5秒
flowscribe transcribe "D:\media\lecture.mp4" -o outputs --progressive --chunk-seconds 60 --chunk-overlap-seconds 5
```

默认值：
- `--chunk-seconds 30` - 每块30秒
- `--chunk-overlap-seconds 3` - 重叠3秒（用于边界去重）

#### 恢复中断的转录

如果转录中断（Ctrl+C、断电等），可以恢复：

```powershell
flowscribe transcribe "D:\media\lecture.mp4" -o outputs --resume
```

FlowScribe 会：
- 跳过已完成的分块
- 从上次中断处继续
- 使用缓存的中间结果

#### 并行处理（实验性）

```powershell
# 使用4个并行工作线程
flowscribe transcribe "D:\media\lecture.mp4" -o outputs --progressive --max-workers 4
```

**注意**: 并行处理会增加内存占用。建议从 `--max-workers 2` 开始测试。

#### 禁用渐进式转录

```powershell
flowscribe transcribe "D:\media\lecture.mp4" -o outputs --no-progressive
```

---

### 5. 转录搜索

在已生成的转录JSON文件中搜索关键词，并定位时间戳。

#### 基础搜索

```powershell
flowscribe search "outputs\lecture.json" "机器学习"
```

输出示例：
```text
Found 3 matches in outputs\lecture.json:

[00:05:23 - 00:05:45] Segment 12
  ...介绍一下机器学习的基本概念...

[00:15:30 - 00:16:02] Segment 34
  ...机器学习算法可以分为监督学习和无监督学习...

[00:42:18 - 00:42:55] Segment 89
  ...深度学习是机器学习的一个分支...
```

#### 限制结果数量

```powershell
flowscribe search "outputs\lecture.json" "机器学习" --limit 5
```

#### 显示上下文

```powershell
# 显示匹配段落前后各2个段落
flowscribe search "outputs\lecture.json" "机器学习" --context 2
```

#### 时间范围过滤

```powershell
# 只搜索前10分钟
flowscribe search "outputs\lecture.json" "机器学习" --start-time 0 --end-time 600

# 搜索15分钟到30分钟之间
flowscribe search "outputs\lecture.json" "机器学习" --start-time 900 --end-time 1800
```

#### JSON输出

```powershell
flowscribe search "outputs\lecture.json" "机器学习" --output-format json > results.json
```

JSON输出包含：
- 匹配的段落文本
- 精确时间戳
- 段落索引
- 上下文段落（如果指定）

---

### 6. 书签服务器

FlowScribe 提供HTTP服务器，支持从浏览器一键添加URL到转录队列。

#### 启动服务器

```powershell
flowscribe serve
```

默认监听 `http://127.0.0.1:8765`

#### 自定义端口

```powershell
flowscribe serve --port 8080
```

#### 书签工具使用

1. 启动服务器：`flowscribe serve`
2. 在浏览器中创建书签，URL设置为：
   ```javascript
   javascript:(function(){fetch('http://127.0.0.1:8765/add-url',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:window.location.href,title:document.title})}).then(r=>r.json()).then(d=>alert(d.message||'已添加到FlowScribe队列')).catch(e=>alert('添加失败：'+e));})();
   ```
3. 浏览视频页面时，点击书签即可添加到队列
4. 在GUI的"队列"视图中查看和管理

也可以直接打开：

```text
http://127.0.0.1:8765/bookmarklet.js
```

获取当前服务器生成的书签脚本。

**注意**: 书签服务器主要配合GUI使用。CLI用户可以直接使用 `flowscribe url` 命令。

---

### 7. 语言与模型

#### 自动语言检测

```powershell
flowscribe transcribe "D:\media\speech.mp4" -o outputs
```

#### 指定语言

```powershell
# 英文
flowscribe transcribe "D:\media\english.mp4" -o outputs --language en

# 中文
flowscribe transcribe "D:\media\chinese.mp4" -o outputs --language zh

# 日文
flowscribe transcribe "D:\media\japanese.mp4" -o outputs --language ja
```

支持的语言代码：`en`, `zh`, `ja`, `ko`, `es`, `fr`, `de`, `ru` 等（Whisper支持的所有语言）

#### 中文优化预设

```powershell
flowscribe transcribe "D:\media\lecture.mp4" -o outputs --preset zh
```

中文预设包含：
- `language = zh`
- `beam_size = 5`
- `task = transcribe`（不翻译）
- `initial_prompt = "使用简体中文，保留中英文原语言，不要翻译"`

当前版本中，如果没有显式传入 `--provider`，`--preset zh` 还会自动切换到
`paraformer` 提供器，并使用 `paraformer-zh` 作为中文优先模型。

#### 模型选择

```powershell
# 快速测试（准确率低）
flowscribe transcribe "D:\media\short.mp4" -o outputs --model tiny

# 推荐起点（平衡速度和准确率）
flowscribe transcribe "D:\media\lecture.mp4" -o outputs --model small

# 更高准确率（速度较慢）
flowscribe transcribe "D:\media\lecture.mp4" -o outputs --model medium

# 大模型高速方案
flowscribe transcribe "D:\media\lecture.mp4" -o outputs --model large-v3-turbo

# 最高本地准确率（速度最慢，资源占用大）
flowscribe transcribe "D:\media\lecture.mp4" -o outputs --model large-v3

# 中文优先方案
flowscribe transcribe "D:\media\lecture.mp4" -o outputs --provider paraformer --model paraformer-zh
```

可用模型：
- `tiny` - 最快，准确率最低
- `base` - 快速，准确率一般
- `small` - **推荐**，平衡速度和准确率
- `medium` - 准确率高，速度较慢
- `large-v3-turbo` - 大模型中速度更快
- `large-v3` - 本地准确率最高，资源占用最大
- `paraformer-zh` - 中文优先模型包，需要 `paraformer` 提供器

#### 查看可用模型

```powershell
flowscribe models
```

查看当前可下载和已安装模型：

```powershell
flowscribe model list-available
flowscribe model list-installed
```

下载模型：

```powershell
flowscribe model download small
flowscribe model download paraformer-zh
```

---

### 8. 输出格式

#### 查看支持的格式

```powershell
flowscribe formats
```

#### 指定多种格式

```powershell
flowscribe transcribe "D:\media\lecture.mp4" -o outputs --format txt,md,json,srt,vtt
```

#### 启用时间戳

```powershell
flowscribe transcribe "D:\media\lecture.mp4" -o outputs --timestamps
```

启用时间戳后：
- Markdown文件会显示段落时间范围
- JSON文件包含详细的词级时间戳（如果模型支持）
- SRT/VTT字幕文件自动包含时间戳

#### 自定义输出文件名

```powershell
flowscribe transcribe "D:\media\lecture.mp4" -o outputs --output-basename "my-lecture"
```

输出文件将是：
```text
outputs/
|-- my-lecture.txt
|-- my-lecture.md
|-- my-lecture.json
`-- my-lecture.srt
```

#### 输出文件结构

假设输入文件是 `lecture.mp4`，输出目录是 `outputs`：

```text
outputs/
├── lecture.txt          # 纯文本转录
├── lecture.md           # Markdown格式（带元信息）
├── lecture.json         # 结构化JSON（包含时间戳、分段）
├── lecture.srt          # SRT字幕文件
└── lecture.vtt          # WebVTT字幕文件
```

**JSON文件内容**：
- `segments` - 分段列表（文本、开始/结束时间）
- `words` - 词级时间戳（如果启用）
- `language` - 检测到的语言
- `duration` - 音频总时长
- 元信息（模型、参数等）

---

### 9. 准确率优化

#### 提高Beam Size

```powershell
flowscribe transcribe "D:\media\lecture.mp4" -o outputs --beam-size 8
```

- 默认值：`5`
- 更高的beam size通常提高准确率，但速度更慢
- 推荐范围：`5-10`

#### 语音活动检测（VAD）

```powershell
# 启用VAD（过滤静音段）
flowscribe transcribe "D:\media\lecture.mp4" -o outputs --vad-filter

# 禁用VAD
flowscribe transcribe "D:\media\lecture.mp4" -o outputs --no-vad-filter
```

**何时使用VAD**：
- ✅ 音频有大量静音段（如讲座、播客）
- ✅ 背景噪音较多
- ❌ 音乐开头或背景音乐（可能过度过滤）
- ❌ 新闻片段开头较安静

参见 [VAD指南](vad-guide.md)。

#### 初始提示词

```powershell
flowscribe transcribe "D:\media\lecture.mp4" -o outputs --initial-prompt "这是一段计算机科学讲座，请保留英文术语和中文原语言，不要翻译。"
```

提示词用途：
- 引导模型使用特定术语
- 保持语言一致性（不翻译）
- 提供上下文信息

#### 任务类型

```powershell
# 转录（保持原语言）
flowscribe transcribe "D:\media\lecture.mp4" -o outputs --task transcribe

# 翻译为英文
flowscribe transcribe "D:\media\chinese.mp4" -o outputs --task translate
```

**推荐**: 始终使用 `--task transcribe` 以避免意外翻译。

#### 温度参数

```powershell
flowscribe transcribe "D:\media\lecture.mp4" -o outputs --temperature 0.0
```

- `0.0` - 确定性输出（推荐）
- `0.2-0.8` - 增加随机性（可能提高创造性，但降低一致性）

---

### 10. 常见问题

#### 提示找不到 ffmpeg

**解决方法**：
1. 安装 ffmpeg：https://ffmpeg.org/download.html
2. 确保 `ffmpeg` 和 `ffprobe` 在系统PATH中
3. 验证安装：
   ```powershell
   ffmpeg -version
   ffprobe -version
   ```

#### 提示没有音频流

**原因**: 文件只有视频轨，没有音频轨（常见于DASH下载）

**解决方法**：
1. 使用包含音频的文件
2. 或先合并音视频：
   ```powershell
   ffmpeg -i video.mp4 -i audio.m4a -c copy output.mp4
   ```

#### 中文识别错误很多

**解决方法**：
1. 不要使用 `tiny` 模型做正式转录
2. 使用中文预设：
   ```powershell
   flowscribe transcribe "D:\media\chinese.mp4" -o outputs --preset zh
   ```
3. 如果想继续使用 faster-whisper，显式指定：
   ```powershell
   flowscribe transcribe "D:\media\chinese.mp4" -o outputs --provider local-whisper --model medium --preset zh
   ```
4. 如果是安装版且尚未下载模型，先打开 GUI 的 **Model Center**，或运行：
   ```powershell
   flowscribe model download small
   ```

#### 第一次运行很慢

**原因**: 首次使用某个模型时需要下载模型文件（几百MB到几GB）

**解决方法**:
1. 便携版或源码环境下，耐心等待下载完成，后续运行会快很多
2. 安装版默认不会在首次运行时静默自动下载模型，请先在 GUI 的 **Model Center** 下载，或运行：
   ```powershell
   flowscribe model download small
   ```

#### 转录速度太慢

**优化方法**：
1. 使用更小的模型（`small` 代替 `medium`）
2. 降低beam size（`--beam-size 1`）
3. 启用VAD过滤静音段（`--vad-filter`）
4. 使用GPU加速（需要CUDA支持的NVIDIA显卡）

#### URL下载失败

**常见原因和解决方法**：
1. **DNS解析问题**: 使用 `--network-family ipv4`
2. **需要代理**: 使用 `--proxy "http://127.0.0.1:7890"`
3. **需要登录**: 使用 `--cookies cookies.txt`
4. **地区限制**: 使用代理或VPN

#### 渐进式转录中断后如何恢复

```powershell
flowscribe transcribe "D:\media\lecture.mp4" -o outputs --resume
```

FlowScribe 会自动检测缓存并从中断处继续。

#### 如何查看版本信息

```powershell
flowscribe version
```

---

## GUI 图形界面

GUI用户指南请参见独立文档：[GUI用户指南](gui-user-guide.md)

GUI主要功能：
- **单任务视图**: 本地文件、URL、系统音频捕获
- **转录库**: 管理所有历史转录，支持过滤和排序
- **批处理队列**: 批量处理本地文件和URL
- **书签服务器**: 浏览器一键添加URL到队列
- **转录编辑**: 编辑转录文本并重新导出
- **媒体播放**: 同步播放原始媒体和转录文本

---

## 使用边界

FlowScribe 面向：
- ✅ 个人学习和研究
- ✅ 无障碍阅读（为听障人士生成字幕）
- ✅ 内容创作（播客、视频字幕）
- ✅ 会议记录和笔记整理
- ✅ 合法的信息处理

**不应用于**：
- ❌ 绕过DRM或版权保护
- ❌ 未经授权分发受版权保护的转录内容
- ❌ 破解或逆向工程应用程序
- ❌ 侵犯他人隐私或知识产权

---

## 更多资源

- [开发者文档](developer-handoff.md)
- [VAD指南](vad-guide.md)
- [代理配置](proxy.md)
- [Cookies使用](cookies.md)
- [Inspect命令](inspect.md)
- [发布说明](../CHANGELOG.md)
- [GitHub仓库](https://github.com/Ducker-Fry/FlowScribe)

---

**版本**: v0.3.3  
**更新日期**: 2026-05-23  
**下一版本**: v1.0.0（性能优化、UI美化、中文转录优化）
