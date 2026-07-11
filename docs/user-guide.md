# 中文 | [English](user-guide-en.md)

# FlowScribe 用户指南

> 版本：v0.3.4  
> 更新日期：2026-06-05  
> 适用平台：Windows 10/11

## 1. FlowScribe 能做什么

FlowScribe 是一个本地优先的音视频转录工具，当前主要覆盖 4 类使用方式：

- 转录本地音频或视频文件
- 从公开 URL 下载音频 / 视频后转录
- 对长音频做渐进式分块转录与恢复
- 在 GUI 中查看、搜索、编辑和重新导出转录结果

当前工程里最稳的主路径是：

- CLI：`transcribe`、`url`、`search`、`inspect`、`model`
- GUI：`Single Task`、`Library`、`Queue`、`Open View`

> ![占位图：FlowScribe CLI 与 GUI 总览](assets/p0.png)
> ![占位图：FlowScribe CLI 与 GUI 总览](assets/p1.png)

## 2. 快速开始

### 2.1 从源码运行

```powershell
cd FlowScribe
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[gui,dev]
```

验证 CLI：

```powershell
flowscribe --help
flowscribe doctor
```

启动 GUI：

```powershell
flowscribe gui
```

也可以直接运行：

```powershell
python -m flowscribe.gui
```

### 2.2 第一次建议做的事情

1. 运行 `flowscribe doctor`，确认本地环境可用。
2. 运行 `flowscribe model list-available` 看可下载模型。
3. 先下载一个模型，再开始正式转录。

推荐起点：

- 日常使用：`small`
- 中文优先：`paraformer-zh`
- 快速试跑：`tiny`

```powershell
flowscribe model download small
```

> ![占位图：CLI doctor 与 model list-available 示例](assets/p7.png)
> ![占位 GIF：从安装完成到第一次转录的完整流程](assets/p8.png)

## 3. CLI 主工作流

## 3.1 转录本地文件

转录单个文件：

```powershell
flowscribe transcribe "D:\media\lecture.mp4" -o outputs
```

转录多个文件：

```powershell
flowscribe transcribe "D:\media\a.mp4" "D:\media\b.mp3" -o outputs
```

递归扫描文件夹：

```powershell
flowscribe transcribe "D:\media" -o outputs --recursive
```

当前常见本地输入格式可以通过下面命令查看：

```powershell
flowscribe formats
```


## 3.2 转录公开 URL

基础 URL 转录：

```powershell
flowscribe url "https://www.youtube.com/watch?v=VIDEO_ID" -o outputs
```

如果你只想先检查资源是否可转录：

```powershell
flowscribe inspect "https://www.youtube.com/watch?v=VIDEO_ID"
```

常见 URL 选项：

```powershell
flowscribe url "https://example.com/video" -o outputs --keep-media
flowscribe url "https://example.com/video" -o outputs --proxy "http://127.0.0.1:7890"
flowscribe url "https://example.com/video" -o outputs --network-family ipv4
flowscribe url "https://example.com/video" -o outputs --download-quality high
flowscribe url "https://example.com/video" -o outputs --download-format mp3
```

需要登录态时可传入 cookies：

```powershell
flowscribe url "https://example.com/video" -o outputs --cookies "D:\private\cookies.txt"
```

只应用于你有合法访问权限的内容。更多细节见 [cookies.md](cookies.md) 和 [proxy.md](proxy.md)。


## 3.3 长音频渐进式转录

FlowScribe 支持 progressive 分块转录，适合长讲座、会议、播客。

显式启用：

```powershell
flowscribe transcribe "D:\media\long.mp4" -o outputs --progressive
```

自定义参数：

```powershell
flowscribe transcribe "D:\media\long.mp4" -o outputs --progressive --chunk-seconds 60 --chunk-overlap-seconds 5
```

从缓存恢复：

```powershell
flowscribe transcribe "D:\media\long.mp4" -o outputs --resume
```

并行 worker：

```powershell
flowscribe transcribe "D:\media\long.mp4" -o outputs --progressive --max-workers 2
```

禁用渐进式：

```powershell
flowscribe transcribe "D:\media\long.mp4" -o outputs --no-progressive
```

当前默认值：

- `--chunk-seconds 30`
- `--chunk-overlap-seconds 3`
- `--max-workers 1`


## 3.4 搜索已有转录

搜索转录 JSON：

```powershell
flowscribe search "outputs\lecture.json" "机器学习"
```

限制结果数和时间范围：

```powershell
flowscribe search "outputs\lecture.json" "机器学习" --limit 10 --after 00:10:00 --before 00:30:00
```

输出 JSON 结果：

```powershell
flowscribe search "outputs\lecture.json" "机器学习" --json
```

## 3.5 检查本地媒体

检查本地文件：

```powershell
flowscribe inspect "D:\media\lecture.mp4"
```

这条命令适合先确认：

- 文件是否存在
- 是否有音频流
- 大概时长
- 文件格式

如果返回 `No audio stream` 之类的结论，就先不要直接跑转录。

## 4. 语言、provider 与模型

## 4.1 当前 provider

当前 CLI 暴露 3 个转录 provider：

- `local-whisper`
- `native-engine`
- `paraformer`

默认情况下：

- 普通任务默认走 `local-whisper`
- 当你使用 `--preset zh` 且没有显式指定 `--provider` 时，会自动切到 `paraformer`

## 4.2 常见模型

当前模型目录与命令中最常见的是：

- `tiny`
- `base`
- `small`
- `medium`
- `large-v3-turbo`
- `large-v3`
- `paraformer-zh`

查看模型概览：

```powershell
flowscribe models
```

查看可下载和已安装模型：

```powershell
flowscribe model list-available
flowscribe model list-installed
```

下载模型：

```powershell
flowscribe model download small
flowscribe model download paraformer-zh
```

删除模型：

```powershell
flowscribe model remove small
```

导入 `whisper.cpp` 本地 `.bin`：

```powershell
flowscribe model import-native "D:\models\ggml-base.en.bin"
```


## 4.3 中文工作流

最简单的中文优先写法：

```powershell
flowscribe transcribe "D:\media\lecture.mp4" -o outputs --preset zh
```

如果你想显式指定 `paraformer`：

```powershell
flowscribe transcribe "D:\media\lecture.mp4" -o outputs --provider paraformer --model paraformer-zh
```

如果你想保留 faster-whisper 风格：

```powershell
flowscribe transcribe "D:\media\lecture.mp4" -o outputs --provider local-whisper --model medium --preset zh
```

## 4.4 英文或多语言工作流

英文示例：

```powershell
flowscribe transcribe "D:\media\english.mp4" -o outputs --model medium --language en
```

保留原语言而不翻译：

```powershell
flowscribe transcribe "D:\media\mix.mp4" -o outputs --task transcribe
```

显式翻译到英文：

```powershell
flowscribe transcribe "D:\media\speech.mp4" -o outputs --task translate
```

## 5. 输出格式与结果

默认输出格式：

```text
txt,md
```

显式输出多种格式：

```powershell
flowscribe transcribe "D:\media\lecture.mp4" -o outputs --format txt,md,json,srt,vtt
```

启用段级时间戳：

```powershell
flowscribe transcribe "D:\media\lecture.mp4" -o outputs --timestamps
```

启用词级时间戳：

```powershell
flowscribe transcribe "D:\media\lecture.mp4" -o outputs --format json --word-timestamps
```

覆盖已有输出：

```powershell
flowscribe transcribe "D:\media\lecture.mp4" -o outputs --overwrite
```

典型输出目录：

```text
outputs/
|-- lecture.txt
|-- lecture.md
|-- lecture.json
|-- lecture.srt
`-- lecture.vtt
```

`json` 通常最重要，因为它是后续搜索、GUI 编辑、重新导出的基础。

默认情况下，输出文件名会基于输入源文件名或 URL 解析结果生成。

> ![占位图：输出目录结构示意](assets/p9.png)

## 6. 书签服务器与本地服务

FlowScribe 提供本地 HTTP 服务，既可配合浏览器书签，也可供自动化使用。

启动服务：

```powershell
flowscribe serve
```

默认行为：

- 监听 `http://127.0.0.1:8765`
- 默认输出目录：`~/Documents/FlowScribe`
- 默认输出格式：`json`
- 默认模型：`small`

自定义端口与输出目录：

```powershell
flowscribe serve --port 8080 -o D:\Transcripts
```

有用的端点包括：

- `POST /add-url`
- `POST /add-urls`
- `GET /status`
- `GET /bookmarklet.js`
- `POST /v1/tasks`
- `GET /v1/tasks/{task_id}`
- `GET /v1/tasks/{task_id}/events`
- `GET /v1/tasks/{task_id}/result`

书签脚本安装地址默认是：

```text
http://127.0.0.1:8765/bookmarklet.js
```


## 7. GUI 怎么配合 CLI 使用

GUI 入口：

```powershell
flowscribe gui
```

或：

```powershell
python -m flowscribe.gui
```

当前 GUI 主线工作流见 [gui-user-guide.md](gui-user-guide.md)。这里先保留高层理解：

- `Single Task`：处理单个本地文件或单个 URL
- `Library`：管理历史转录
- `Queue`：批量任务与书签服务器入口
- `Open View`：查看运行日志、搜索 transcript、编辑 segment、重新导出

如果你已经有 CLI 生成的转录 JSON，也可以在 GUI 里打开并继续复核。


## 8. 推荐工作流

## 8.1 最稳的日常流程

1. `flowscribe model download small`
2. `flowscribe transcribe ... --format txt,md,json`
3. 用 `flowscribe search ...` 做关键词定位
4. 如需人工校对，再进入 GUI 的 `Open View`

## 8.2 中文优先流程

1. 先下载 `paraformer-zh`
2. 使用 `--preset zh`
3. 必要时额外导出 `json,srt,vtt`
4. 用 GUI 复核时间点和文本

## 8.3 URL 批量流程

1. 先用 `inspect` 检查个别 URL
2. 再用 `Queue` 或 `flowscribe serve`
3. 对重要结果保留 `json`
4. 需要时加 `--keep-media`

## 9. 当前边界

有几个边界最好明确知道：

### 9.1 `capture` CLI 还没实现

虽然 CLI 里有：

```powershell
flowscribe capture
```

这个入口，但当前实现仍然只是占位提示，不是正式可用功能。

### 9.2 GUI 的系统音频捕获入口仍在完善

当前 GUI 主界面里有 `System Audio Capture` 区块，但现阶段更稳妥的正式工作流依然是：

- 本地文件
- URL
- Queue
- JSON + Open View 复核

### 9.3 安装版首次使用可能需要先下载模型

安装版默认不会在首次运行时静默自动下载模型，所以第一次用前最好先准备好模型，或在 GUI 中先打开 `Model Center`。

## 10. 常见问题

### 10.1 `doctor` 通过了，但 outputs 是空的

这是正常的。`doctor` 只检查环境，不会生成转录文件。

### 10.2 提示找不到音频流

先用：

```powershell
flowscribe inspect "D:\media\video.mp4"
```

确认文件里是否真的有音频流。

### 10.3 第一次运行很慢

常见原因是首次下载模型。下载完成后，后续运行会快很多。

### 10.4 中文识别效果不理想

先试：

```powershell
flowscribe transcribe "D:\media\chinese.mp4" -o outputs --preset zh
```

如果仍不够好，再试更明确的写法：

```powershell
flowscribe transcribe "D:\media\chinese.mp4" -o outputs --provider local-whisper --model medium --preset zh
```

### 10.5 URL 下载失败

优先排查：

- 是否需要代理
- 是否需要 cookies
- 是否该强制 `ipv4`
- 原站点是否支持当前链接格式

## 11. 相关文档

- [gui-user-guide.md](gui-user-guide.md) - GUI 完整使用说明
- [gui-user-guide-en.md](gui-user-guide-en.md) - GUI user guide
- [vad-guide.md](vad-guide.md) - VAD 什么时候开、什么时候关
- [vad-guide-en.md](vad-guide-en.md) - VAD guide
- [release-installation.md](release-installation.md) - 便携版和安装版说明
- [release-installation-en.md](release-installation-en.md) - release installation guide
- [cookies.md](cookies.md) - 登录态媒体访问
- [cookies-en.md](cookies-en.md) - cookies for login-required media
- [proxy.md](proxy.md) - 代理配置
- [proxy-en.md](proxy-en.md) - proxy configuration
- [inspect.md](inspect.md) - inspect 命令说明
- [inspect-en.md](inspect-en.md) - inspect command guide
- [json-format.md](json-format.md) - 转录 JSON 结构（暂时仅英文）
