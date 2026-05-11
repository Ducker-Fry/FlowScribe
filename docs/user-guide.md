# FlowScribe User Guide

FlowScribe is a local-first command-line tool that turns local audio and video files into raw transcripts. It currently exports TXT and Markdown files. It does not summarize, extract opinions, or bypass protected media.

中文说明见下半部分。

## English Guide

### 1. What FlowScribe Does

FlowScribe helps you convert local media into readable text:

```text
local audio/video file -> prepared audio -> local transcription -> TXT/Markdown output
```

Current supported inputs:

- Single local audio or video file.
- Multiple local files.
- Local folder.
- Local folder scanned recursively.

Common supported formats include:

```text
mp4, mkv, mov, avi, mp3, wav, m4a, flac, webm
```

### 2. Requirements

You need:

- Windows PowerShell or another terminal.
- Python 3.10 or newer.
- `ffmpeg` and `ffprobe` available on `PATH`.
- FlowScribe installed in editable mode.

Install the project dependencies:

```powershell
cd E:\Draft\FlowScribe
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
```

Check that the command is available:

```powershell
flowscribe --help
```

Check whether your local environment is ready:

```powershell
flowscribe doctor
```

### 3. Basic Usage

Transcribe one video:

```powershell
flowscribe "D:\media\lecture.mp4" -o outputs
```

Transcribe one audio file:

```powershell
flowscribe "D:\media\recording.wav" -o outputs
```

Transcribe all supported files in a folder:

```powershell
flowscribe "D:\media" -o outputs
```

Scan folders recursively:

```powershell
flowscribe "D:\media" -o outputs --recursive
```

### 4. Language Usage

Automatic language detection:

```powershell
flowscribe "D:\media\speech.mp4" -o outputs
```

English hint:

```powershell
flowscribe "D:\media\english.mp4" -o outputs --language en
```

Chinese hint:

```powershell
flowscribe "D:\media\chinese.mp4" -o outputs --language zh
```

Chinese-oriented preset:

```powershell
flowscribe "D:\media\lecture.mp4" -o outputs --preset zh
```

The Chinese preset currently applies:

```text
language = zh
vad_filter = true
beam_size = 5
task = transcribe
initial_prompt = preserve Chinese and English as spoken, do not translate
```

For mixed Chinese and English media, try automatic detection first. If the result is poor, use `--preset zh` or provide a custom prompt.

### 5. Model Choice

Use `tiny` only for quick smoke tests:

```powershell
flowscribe "D:\media\short.mp4" -o outputs --model tiny
```

Recommended starting point:

```powershell
flowscribe "D:\media\lecture.mp4" -o outputs --model small
```

For better accuracy:

```powershell
flowscribe "D:\media\lecture.mp4" -o outputs --model medium
```

Larger models are usually more accurate but slower and heavier.

### 6. Accuracy Options

Increase beam size:

```powershell
flowscribe "D:\media\lecture.mp4" -o outputs --beam-size 8
```

Enable voice activity detection:

```powershell
flowscribe "D:\media\lecture.mp4" -o outputs --vad-filter
```

Add an initial prompt:

```powershell
flowscribe "D:\media\lecture.mp4" -o outputs --initial-prompt "This is a computer science lecture. Preserve English terms and Chinese speech as spoken."
```

Make sure transcription does not translate the content:

```powershell
flowscribe "D:\media\lecture.mp4" -o outputs --task transcribe
```

### 7. Output Files

For an input file named:

```text
lecture.mp4
```

FlowScribe creates:

```text
outputs/
├── lecture.txt
└── lecture.md
```

The TXT file contains the raw transcript. The Markdown file contains metadata and the transcript. Metadata includes the model, language, task, beam size, VAD setting, preset, and initial prompt.

### 8. Troubleshooting

Run the built-in environment check first:

```powershell
flowscribe doctor -o outputs --model small
```

It checks Python, `ffmpeg`, `ffprobe`, `faster-whisper`, output directory writes, and whether the selected model appears reachable for download.

No audio stream found:

The file contains video only. This is common with some DASH downloads where audio and video are stored separately. Use a file that includes audio, or merge the audio and video first.

`ffmpeg was not found`:

Install ffmpeg and make sure `ffmpeg` and `ffprobe` are available on `PATH`.

Chinese output has many mistakes:

Avoid `tiny` for real Chinese transcription. Try:

```powershell
flowscribe "D:\media\chinese.mp4" -o outputs --model small --preset zh
```

If quality is still poor, try `medium`.

First run is slow:

The first run may download the selected local model. Later runs should start faster.

### 9. Boundaries

FlowScribe is intended for personal learning, accessibility, research notes, and lawful information processing. It should not be used to bypass DRM, crack applications, or redistribute copyrighted transcripts without permission.

## 中文指南

### 1. FlowScribe 是什么

FlowScribe 是一个本地优先的命令行工具，用来把本地音频或视频转换成原始文字稿：

```text
本地音视频文件 -> 音频准备 -> 本地语音识别 -> TXT/Markdown 输出
```

当前支持：

- 单个本地音频或视频文件。
- 多个本地文件。
- 本地文件夹。
- 递归扫描本地文件夹。

常见支持格式包括：

```text
mp4, mkv, mov, avi, mp3, wav, m4a, flac, webm
```

### 2. 使用前准备

你需要：

- Windows PowerShell 或其他终端。
- Python 3.10 或更新版本。
- 已安装 `ffmpeg`，并且 `ffmpeg`、`ffprobe` 能在命令行中直接使用。
- 已安装 FlowScribe 项目依赖。

安装依赖：

```powershell
cd E:\Draft\FlowScribe
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
```

检查命令是否可用：

```powershell
flowscribe --help
```

检查本地环境是否准备好：

```powershell
flowscribe doctor
```

### 3. 基础用法

转写单个视频：

```powershell
flowscribe "D:\media\lecture.mp4" -o outputs
```

转写单个音频：

```powershell
flowscribe "D:\media\recording.wav" -o outputs
```

转写文件夹中的所有支持文件：

```powershell
flowscribe "D:\media" -o outputs
```

递归扫描子文件夹：

```powershell
flowscribe "D:\media" -o outputs --recursive
```

### 4. 语言设置

自动识别语言：

```powershell
flowscribe "D:\media\speech.mp4" -o outputs
```

明确提示英文：

```powershell
flowscribe "D:\media\english.mp4" -o outputs --language en
```

明确提示中文：

```powershell
flowscribe "D:\media\chinese.mp4" -o outputs --language zh
```

中文优化预设：

```powershell
flowscribe "D:\media\lecture.mp4" -o outputs --preset zh
```

当前中文预设会应用：

```text
language = zh
vad_filter = true
beam_size = 5
task = transcribe
initial_prompt = 保留中英文原语言，不翻译
```

如果视频是中英混合，可以先试自动识别；如果效果不好，再试 `--preset zh` 或自定义 `--initial-prompt`。

### 5. 模型选择

`tiny` 适合快速测试功能是否跑通：

```powershell
flowscribe "D:\media\short.mp4" -o outputs --model tiny
```

日常建议从 `small` 开始：

```powershell
flowscribe "D:\media\lecture.mp4" -o outputs --model small
```

如果更重视准确率，可以试 `medium`：

```powershell
flowscribe "D:\media\lecture.mp4" -o outputs --model medium
```

模型越大，通常越准确，但速度更慢，也更占资源。

### 6. 提升准确率的参数

提高 beam size：

```powershell
flowscribe "D:\media\lecture.mp4" -o outputs --beam-size 8
```

启用语音活动检测：

```powershell
flowscribe "D:\media\lecture.mp4" -o outputs --vad-filter
```

添加初始提示词：

```powershell
flowscribe "D:\media\lecture.mp4" -o outputs --initial-prompt "这是一段计算机课程录音，请保留英文术语，不要翻译。"
```

明确只转写、不翻译：

```powershell
flowscribe "D:\media\lecture.mp4" -o outputs --task transcribe
```

### 7. 输出文件

假设输入文件是：

```text
lecture.mp4
```

输出结果会是：

```text
outputs/
├── lecture.txt
└── lecture.md
```

TXT 文件是原始文字稿。Markdown 文件包含元信息和文字稿。元信息会记录模型、语言、任务类型、beam size、VAD 设置、预设和初始提示词。

### 8. 常见问题

先运行内置环境检查：

```powershell
flowscribe doctor -o outputs --model small
```

它会检查 Python、`ffmpeg`、`ffprobe`、`faster-whisper`、输出目录写入能力，以及所选模型是否看起来可以下载。

提示没有音频流：

这个文件可能只有视频轨，没有音频轨。一些 DASH 下载会把视频和音频分开保存。请换一个包含音频的视频文件，或先把音频和视频合并。

提示找不到 ffmpeg：

请安装 ffmpeg，并确认命令行中可以直接运行：

```powershell
ffmpeg -version
ffprobe -version
```

中文识别错误很多：

不要用 `tiny` 做正式中文转写。建议：

```powershell
flowscribe "D:\media\chinese.mp4" -o outputs --model small --preset zh
```

如果仍然不够好，可以试 `medium`。

第一次运行很慢：

第一次运行某个模型时，可能需要下载模型文件。后续再用同一个模型会快一些。

### 9. 使用边界

FlowScribe 面向个人学习、无障碍阅读、研究笔记和合法的信息处理。不要用它绕过 DRM、破解客户端应用，或在没有授权的情况下公开分发受版权保护的字幕或文字稿。
