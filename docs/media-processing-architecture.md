# FlowScribe Media Processing Architecture

## 定位

FlowScribe 的长期定位不是单一的音视频转写工具，而是一个本地优先、可扩展、可私有化部署的音视频结构化数据处理引擎。

它的核心目标是把音频、视频、URL、实时流、文件夹和批量素材转成可被人、应用、AI 工具链和知识库消费的结构化数据。

转写是第一能力，字幕是第一应用，面向 AI 和知识库的数据抽取是长期价值。

## 设计原则

- 应用层不直接关心模型协议。
- 任务层不绑定单一转写实现。
- 编排层负责把多个能力组合成稳定流程。
- 能力层定义 FlowScribe 能做什么。
- 适配层负责把统一请求翻译成不同后端能理解的调用。
- 执行层只负责真正运行模型、SDK、外部进程或远程 API。
- 当前实现保持薄切片，目标架构用于定义边界，不要求一次性完整实现。

## 分层架构

```text
应用层 App Layer
  CLI / GUI / API Server / 实时字幕 / 知识库导入器 / 会议助手 / 第三方工具

任务层 Task Layer
  Job / Batch / Queue / Progress / Cancel / Resume / Cache / Export

编排层 Orchestration Layer
  Pipeline / Router / Scheduler / RuntimeManager / ModelManager

能力层 Capability Layer
  Transcribe / Diarize / Subtitle / Summarize / Translate / ExtractKeywords / Chunk / Clean / Index

适配层 Adapter Layer
  local-whisper / native-engine / Paraformer / SenseVoice / Cloud ASR / LLM / OCR / ffmpeg

执行层 Runtime Layer
  Python SDK / C++ Engine / ONNX Runtime / whisper.cpp / API Client / External Process
```

## 各层职责

### 应用层 App Layer

应用层是用户和外部系统接触 FlowScribe 的入口。

典型入口包括：

- CLI
- GUI
- API Server
- 实时字幕
- 知识库导入器
- 会议助手
- 第三方工具

应用层只负责交互、展示、参数收集和结果消费。它不应该知道底层使用的是 faster-whisper、native-engine、Paraformer、SenseVoice 还是云端 API。

应用层提交的是任务请求，而不是直接调用模型。

示例：

```json
{
  "input": "lecture.mp4",
  "task": "extract_knowledge",
  "outputs": ["json", "md", "srt"],
  "profile": "zh-knowledge"
}
```

### 任务层 Task Layer

任务层负责把用户意图变成可追踪、可取消、可恢复、可导出的任务。

核心职责：

- Job：单个处理任务。
- Batch：批量任务。
- Queue：任务队列。
- Progress：进度事件。
- Cancel：取消任务。
- Resume：断点恢复。
- Cache：缓存中间结果。
- Export：统一输出文件。

这层解决的是“如何管理一次处理过程”，不是“具体怎么跑模型”。

### 编排层 Orchestration Layer

编排层负责决定一个任务应该由哪些步骤完成，以及这些步骤如何连接。

例如 `extract_knowledge` 可以被编排为：

```text
prepare_media -> transcribe -> clean_text -> chunk -> summarize -> export
```

核心组件：

- Pipeline：定义处理步骤。
- Router：根据任务类型、语言、模型能力和用户配置选择路径。
- Scheduler：调度任务、并发和资源。
- RuntimeManager：管理外部运行时进程或服务。
- ModelManager：管理模型下载、校验、加载、卸载和健康状态。

模型下载、检测、启动、关闭不应散落在 CLI、GUI 或某个 provider 中，而应逐步收敛到 RuntimeManager 和 ModelManager。

### 能力层 Capability Layer

能力层定义 FlowScribe 能做什么。

第一阶段只需要稳定 `Transcribe`，后续可以扩展：

- Transcribe：音视频转文字。
- Diarize：说话人分离。
- Subtitle：字幕生成。
- Summarize：摘要。
- Translate：翻译。
- ExtractKeywords：关键词提取。
- Chunk：文本切片。
- Clean：文本清洗和规范化。
- Index：知识库入库、向量化或索引导出。

能力层不关心具体由哪个模型实现。比如 `Transcribe` 可以由 local-whisper、native-engine、Paraformer、SenseVoice 或云 ASR 实现。

### 适配层 Adapter Layer

适配层负责把 FlowScribe 的统一任务请求翻译成不同后端能理解的调用。

典型适配器：

- local-whisper adapter：调用 faster-whisper Python SDK。
- native-engine adapter：把请求翻译成 FlowScribe named-pipe 协议。
- Paraformer adapter：调用 FunASR SDK 或 ONNX Runtime。
- SenseVoice adapter：调用对应本地推理实现。
- Cloud ASR adapter：调用远程 HTTP API。
- LLM adapter：执行摘要、清洗、关键词提取等文本处理。
- OCR adapter：处理视频画面文字。
- ffmpeg adapter：抽音频、转码、切片、探测媒体信息。

适配层是解耦的关键。应用层不应为每个底层模型设计一套协议。

### 执行层 Runtime Layer

执行层是真正干活的底层运行环境。

它包括：

- Python SDK
- C++ Engine
- ONNX Runtime
- whisper.cpp
- API Client
- External Process

执行层不表达 FlowScribe 的业务语义，只提供运行能力。比如 native C++ engine 只需要接收协议消息、执行模型推理、返回事件和结果。

## 统一数据模型

长期目标是把当前的 `Transcript` 升级或包裹成更通用的 `MediaDocument`。

`MediaDocument` 不只保存转写文本，还可以保存源信息、时间戳、说话人、关键词、摘要、章节、字幕和导出物。

示例结构：

```json
{
  "source": {
    "path": "lecture.mp4",
    "duration_seconds": 3600.0
  },
  "segments": [
    {
      "start_seconds": 12.3,
      "end_seconds": 18.7,
      "speaker": "SPEAKER_1",
      "text": "今天我们讲本地知识库的构建。"
    }
  ],
  "derived": {
    "summary": "本节介绍本地知识库和 RAG 的基础流程。",
    "keywords": ["本地知识库", "RAG", "音视频转写"],
    "outline": []
  },
  "artifacts": [
    {
      "format": "json",
      "path": "outputs/lecture.json"
    }
  ]
}
```

当前的 `Transcript`、`TranscriptSegment`、`TranscriptWord` 可以继续保留，并作为 `MediaDocument` 的转写部分。不要为了新抽象一次性打断现有 CLI 和 GUI。

## 当前仓库的自然映射

当前代码已经有目标架构的雏形：

- `src/flowscribe/transcription/providers.py`：转写 provider 注册和能力元数据雏形。
- `src/flowscribe/transcription/local_whisper.py`：local-whisper adapter。
- `src/flowscribe/transcription/native_engine.py`：native-engine adapter，负责应用请求到 named-pipe 协议的翻译。
- `src/flowscribe/engine/pipe_client.py`：native engine 协议客户端。
- `src/flowscribe/core/ports.py`：`Transcriber` 等端口抽象。
- `src/flowscribe/core/models.py`：`PreparedAudio`、`Transcript`、`OutputArtifacts` 等领域模型。
- `native/flowscribe-engine/include/flowscribe/engine/protocol/message.h`：C++ engine 协议边界。

因此，下一步不需要重写，而是给已有边界更稳定的命名和更通用的上层抽象。

## 是否过度设计

这套架构如果一次性完整实现，就是过度设计。

它应该作为目标架构和边界地图存在。当前实现只需要做薄切片：

```text
App Layer
  CLI / GUI

Service + Task Layer
  JobService / TranscriptionJob / Progress / Export

Pipeline Layer
  prepare_audio -> transcribe -> export

Capability Layer
  Transcribe

Adapter Layer
  local-whisper / native-engine / Paraformer

Runtime Layer
  model path check / engine start-stop / SDK call
```

也就是说，文档中保留六层概念，代码中先实现最少必要路径。

## 落地路线

### 阶段 1：稳定现有转写能力

目标：不破坏 CLI 和 GUI，整理已有边界。

- 保留现有 `Transcriber`。
- 整理 provider capabilities。
- 明确 local-whisper 和 native-engine 都是 `Transcribe` capability 的 provider。
- 把模型路径检查、engine 查找、启动和关闭逻辑逐步收敛。

### 阶段 2：引入通用任务模型

目标：为非转写任务留出位置。

新增轻量抽象：

- `MediaTask`
- `MediaTaskSpec`
- `MediaResult`
- `CapabilityProvider`

先让 `transcribe` 成为第一个 capability，不急于实现所有能力。

### 阶段 3：接入中文优先模型

目标：解决中文转写准确率和速度问题。

- 新增 Paraformer provider。
- 保持 CLI/GUI 参数不直接绑定 FunASR 细节。
- 输出继续统一到 `Transcript` 或 `MediaDocument`。
- 允许后续替换为 ONNX Runtime 或 native 常驻推理。

### 阶段 4：扩展结构化处理流水线

目标：从“转写”升级到“结构化信息抽取”。

可选 pipeline：

```text
transcribe -> clean -> chunk -> summarize -> export
transcribe -> subtitle -> translate -> export
transcribe -> diarize -> speaker_labeled_json
```

### 阶段 5：AI 数据层能力

目标：面向知识库、RAG 和批量数据处理。

- 批量处理音视频库。
- 输出标准结构化 JSON。
- 支持文本清洗、切片和元数据保留。
- 提供 API Server 或 CLI 自动化接口。
- 为向量库、知识库、企业内部系统提供可消费数据。

## 推荐模块演进

长期可以演进为：

```text
src/flowscribe/
  app/              CLI/GUI 调用服务
  tasks/            Job、TaskSpec、Batch、Queue
  pipeline/         Pipeline、Step、Router、Scheduler
  capabilities/     transcribe、summarize、translate、diarize、index
  providers/        whisper、native_engine、paraformer、cloud
  runtime/          ModelManager、RuntimeManager、DownloadManager
  media/            ffmpeg、audio/video prepare、metadata
  document/         MediaDocument、Segment、Word、Speaker、Artifact
  export/           txt、md、json、srt、vtt
  engine/           native pipe protocol client
```

不要马上按这个目录大搬家。优先在现有结构上新增薄抽象，等边界稳定后再迁移。

## 结论

FlowScribe 的核心价值不是“调用某个 ASR 模型”，而是把音视频中的信息转成稳定、标准、可自动化处理的结构化数据。

这套架构的作用是让项目从字幕工具自然生长为音视频结构化数据引擎，同时避免 CLI、GUI、模型协议、任务队列和输出格式互相纠缠。

实现上应坚持薄切片：先把 `Transcribe` 做稳，再逐步扩展到摘要、清洗、切片、说话人、翻译和知识库入库。
