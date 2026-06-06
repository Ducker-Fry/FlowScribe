# 中文 | [English](release-installation-en.md)

# 发布安装说明

这份文档面向不想配置 Python、也不想直接从源码运行的用户。

## 下载

打开最新发布页：

```text
https://github.com/Ducker-Fry/FlowScribe/releases
```

根据需要下载：

```text
FlowScribe-vX.Y.Z-windows-x64.zip
FlowScribeGUI-vX.Y.Z-windows-x64.zip
FlowScribeSetup-online-x64.exe
FlowScribeSetup-offline-x64.exe
```

- `FlowScribe-vX.Y.Z-windows-x64.zip`：CLI 便携版
- `FlowScribeGUI-vX.Y.Z-windows-x64.zip`：GUI 便携版
- `FlowScribeSetup-online-x64.exe`：在线安装器，安装时下载打包文件
- `FlowScribeSetup-offline-x64.exe`：离线安装器，安装包内已包含打包文件

## 安装

把压缩包解压到你可控的目录，例如：

```text
D:\Tools\FlowScribe
```

CLI 解压后目录应类似：

```text
FlowScribe/
|-- FlowScribe.exe
|-- ffmpeg.exe
|-- ffprobe.exe
|-- README-USER.txt
`-- _internal/
```

不要只单独移动 `FlowScribe.exe`。

GUI 解压后目录应类似：

```text
FlowScribeGUI/
|-- FlowScribeGUI.exe
|-- WasapiCaptureHelper.exe
|-- NAudio*.dll
`-- _internal/
```

也不要只单独移动 `FlowScribeGUI.exe`。

## 首次检查

在解压后的目录中打开 PowerShell，运行：

```powershell
.\FlowScribe\FlowScribe.exe doctor
```

GUI 包则直接运行：

```powershell
.\FlowScribeGUI\FlowScribeGUI.exe
```

打包后的 GUI 会使用安静的 `user` 日志模式，正常使用时不会额外弹出控制台窗口。

你应当能看到这些检查项：

- 包内运行时组件
- 内置 `ffmpeg.exe`
- 内置 `ffprobe.exe`
- `faster-whisper`
- 输出目录写权限
- 模型下载访问能力

如果你使用安装版，安装过程会把本地帮助文档复制到受管 docs 目录中，GUI 的 `Help` 和 `Open Model Guide` 会指向那里。安装版默认也不会在首次使用时静默自动下载模型，因此第一次启动时可能会提示你先打开 `Model Center` 或本地模型指南。

## 转录一个文件

中文优先写法：

```powershell
.\FlowScribe\FlowScribe.exe transcribe "D:\media\lecture.mp4" -o outputs --preset zh
```

推荐通用写法：

```powershell
.\FlowScribe\FlowScribe.exe transcribe "D:\media\lecture.mp4" -o outputs --model small --preset zh
```

英文示例：

```powershell
.\FlowScribe\FlowScribe.exe transcribe "D:\media\english.mp4" -o outputs --model small --language en
```

快速试跑：

```powershell
.\FlowScribe\FlowScribe.exe transcribe "D:\media\short.wav" -o outputs --model tiny --overwrite
```

## 使用桌面 GUI

当前 GUI 的主线围绕这些入口：

- `Single Task`：单个本地文件或单个 URL
- `Queue`：批量任务、URL 队列、书签服务器入口
- `Library`：历史转录库
- `Open View`：日志、搜索、分段编辑、重新导出

目前你可以：

- 添加本地文件和文件夹
- 粘贴公开 URL
- 打开现有 transcript JSON
- 浏览 transcript 库
- 搜索 transcript 关键词
- 编辑 segment 文本
- 覆盖保存或另存修订后的 JSON
- 重新导出为 TXT、Markdown、JSON、SRT、VTT
- 绑定本地媒体并做播放同步

GUI 里也有 `System Audio Capture` 入口，但这条路径仍在完善中，现阶段不要把它当成最稳的正式主流程。

## 输出

如果输入文件名是：

```text
lecture.mp4
```

FlowScribe 常见会生成：

```text
outputs/
|-- lecture.txt
|-- lecture.md
|-- lecture.json
|-- lecture.srt
`-- lecture.vtt
```

## 模型下载

转录模型不会预置在便携包中。

- 源码运行和便携运行时，选中某个模型后可能触发下载
- 安装版默认关闭首次自动下载，需要你手动先准备模型

推荐模型：

- `tiny`：只适合快速冒烟测试
- `small`：最推荐的起点
- `medium`：更准但更慢
- `paraformer-zh`：面向中文优先的 `paraformer` 模型包

常用命令：

```powershell
flowscribe model list-available
flowscribe model list-installed
flowscribe model download small
flowscribe model download paraformer-zh
```

## 故障排除

如果 `doctor` 通过了但 `outputs` 还是空的，这是正常现象。`doctor` 只做环境检查，不生成转录结果。

如果文件提示 `No audio stream found`，先用 `inspect` 检查。部分媒体可能只有视频流，或音视频分离存储。

如果模型访问失败，先检查网络访问，打开 `Model Center`，或在支持的 provider 下使用本地模型路径。

如果 GUI 报告 `WasapiCaptureHelper.exe` 缺失，说明 GUI 包不完整。请重新完整解压整个 `FlowScribeGUI` 文件夹，不要只拷贝单个 exe。

如果系统音频捕获显示已开始，但长时间没有新音频数据，请确认系统确实正在播放声音，并确认当前默认播放设备就是你想录制的输出设备。
