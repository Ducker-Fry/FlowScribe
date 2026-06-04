# FlowScribe

[![CI](https://github.com/Ducker-Fry/FlowScribe/actions/workflows/ci.yml/badge.svg)](https://github.com/Ducker-Fry/FlowScribe/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/Ducker-Fry/FlowScribe?display_name=tag)](https://github.com/Ducker-Fry/FlowScribe/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)
[![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)](docs/packaging.md)

FlowScribe 是一个本地优先的音视频转录工具，支持本地媒体文件和公开URL音频转录。提供命令行工具（CLI）用于批处理工作流，以及 PySide6 桌面图形界面（GUI）用于交互式转录查看、搜索和媒体同步播放。

**当前版本**: v0.3.0  
**下一版本**: v0.3.x / v0.9 规划中（性能优化、中文转录加速、原生 `whisper.cpp` 常驻推理引擎）

---

## 核心特性

### 转录功能
- ✅ 转录本地音频和视频文件
- ✅ 转录公开URL音频（基于 yt-dlp）
- ✅ 单文件、多文件、文件夹批处理
- ✅ 递归扫描子文件夹
- ✅ 长音频渐进式转录（分块处理、中断恢复）
- ✅ 系统音频捕获（WASAPI）

### 输出格式
- ✅ 纯文本（`.txt`）
- ✅ Markdown（`.md`，带元信息）
- ✅ 结构化JSON（`.json`，包含时间戳）
- ✅ 字幕文件（`.srt`, `.vtt`）
- ✅ 词级时间戳（中文自然词对齐）

### 桌面GUI（v0.3.0架构）
- ✅ **单任务视图**：本地文件、URL、系统音频捕获
- ✅ **转录库**：管理所有历史转录，支持过滤和排序
- ✅ **批处理队列**：从文本/CSV/Excel导入URL，顺序处理，自动重试
- ✅ **书签服务器**：浏览器一键添加URL到队列
- ✅ **转录编辑**：编辑转录文本并重新导出
- ✅ **媒体同步播放**：点击分段跳转，播放进度高亮
- ✅ **关键词搜索**：搜索并跳转到匹配位置

### 语言支持
- ✅ 中文（简体/繁体，自然词对齐）
- ✅ 英文
- ✅ 中英混合
- ✅ 其他语言（Whisper支持的所有语言）
- ✅ 中文优化预设（`--preset zh`）

---

## 系统要求

- **操作系统**: Windows 10/11
- **Python**: 3.10 或更新版本
- **依赖**: `ffmpeg` 和 `ffprobe` 需在系统PATH中
- **可选**: NVIDIA GPU（CUDA支持，加速转录）

---

## 安装

### 方式1：通过 pip 安装（推荐）

安装CLI：

```powershell
pip install flowscribe
```

安装CLI + GUI：

```powershell
pip install flowscribe[gui]
```

验证安装：

```powershell
flowscribe doctor
```

### 方式2：自动化环境配置

使用配置脚本自动创建虚拟环境、安装依赖、检测或安装 `ffmpeg`：

```powershell
# 仅CLI
powershell -ExecutionPolicy Bypass -File scripts\setup_env.ps1

# CLI + GUI
powershell -ExecutionPolicy Bypass -File scripts\setup_env.ps1 -Gui

# CLI + GUI + 开发依赖
powershell -ExecutionPolicy Bypass -File scripts\setup_env.ps1 -Gui -Dev
```

脚本会通过 `winget` 自动安装 `ffmpeg`（如果可用）。

### 方式3：从源码安装（开发者）

```powershell
git clone https://github.com/Ducker-Fry/FlowScribe.git
cd FlowScribe
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[gui,dev]
```

检查CLI：

```powershell
flowscribe --help
```

运行GUI：

```powershell
flowscribe gui
```

### 方式4：便携版（免安装）

从 [Releases](https://github.com/Ducker-Fry/FlowScribe/releases) 页面下载并解压：

- `FlowScribe-vX.X.X-windows-x64.zip` - CLI便携版
- `FlowScribeGUI-vX.X.X-windows-x64.zip` - GUI便携版

便携版已包含 `ffmpeg.exe` 和 `ffprobe.exe`，无需额外安装。

**注意**: Whisper模型不包含在便携版中，首次运行时会自动下载。

---

## 快速开始

### CLI 基础用法

转录单个文件：

```powershell
flowscribe transcribe "D:\media\lecture.mp4" -o outputs
```

转录文件夹（递归）：

```powershell
flowscribe transcribe "D:\media" -o outputs --recursive
```

转录公开URL：

```powershell
flowscribe url "https://www.youtube.com/watch?v=VIDEO_ID" -o outputs
```

使用中文优化预设：

```powershell
flowscribe transcribe "D:\media\lecture.mp4" -o outputs --preset zh
```

指定输出格式：

```powershell
flowscribe transcribe "D:\media\lecture.mp4" -o outputs --format txt,md,json,srt,vtt
```

### 长音频渐进式转录

对于长音频（如2小时讲座），FlowScribe 支持分块处理和中断恢复：

```powershell
# 自动启用渐进式（推荐）
flowscribe transcribe "D:\media\long-lecture.mp4" -o outputs

# 强制启用渐进式
flowscribe transcribe "D:\media\lecture.mp4" -o outputs --progressive

# 恢复中断的转录
flowscribe transcribe "D:\media\lecture.mp4" -o outputs --resume
```

### 转录搜索

在已生成的转录JSON中搜索关键词：

```powershell
flowscribe search "outputs\lecture.json" "机器学习"
```

限制结果和时间范围：

```powershell
flowscribe search "outputs\lecture.json" "机器学习" --limit 10 --after 00:10:00 --before 00:30:00
```

### 书签服务器

启动HTTP服务器，支持从浏览器一键添加URL：

```powershell
flowscribe serve
```

在浏览器中创建书签，URL设置为：

```javascript
javascript:(function(){fetch('http://localhost:5000/add-url',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:window.location.href,title:document.title})});alert('已添加到FlowScribe队列');})();
```

浏览视频页面时，点击书签即可添加到队列。

### 环境检查

运行内置诊断工具：

```powershell
flowscribe doctor
```

检查项目：
- Python版本
- `ffmpeg` 和 `ffprobe` 可用性
- `faster-whisper` 安装状态
- 输出目录写入权限
- 模型下载可达性

---

## 桌面GUI

### 启动GUI

从源码运行：

```powershell
flowscribe gui
```

或：

```powershell
python -m flowscribe.gui
```

便携版直接运行 `FlowScribeGUI.exe`。

### GUI主要功能

**单任务视图**：
- 拖放本地文件/文件夹
- 输入URL转录
- 系统音频捕获（WASAPI）
- 配置转录参数（模型、语言、输出格式等）
- 实时进度显示和ETA

**转录库**：
- 查看所有历史转录
- 按来源类型、状态、打开状态过滤
- 按时间、标签排序
- 重新打开、编辑、重新导出

**批处理队列**：
- 添加本地文件和URL
- 从文本/CSV/Excel导入URL
- 拖放重新排序
- 顺序处理，自动重试
- 书签服务器集成

**转录查看与编辑**：
- 分段显示转录文本
- 编辑并保存
- 重新导出为其他格式
- 媒体同步播放
- 关键词搜索和跳转

详细GUI使用说明请参见：[GUI用户指南](docs/gui-user-guide.md)

---

## 常用选项

### 基础选项

```text
--model small           模型选择：tiny, base, small, medium, large-v2
--language zh           语言提示：zh（中文）, en（英文）, ja（日文）等
--preset zh             中文优化预设
--beam-size 5           解码beam size，越大越准确但越慢
--vad-filter            启用语音活动检测（过滤静音段）
--no-vad-filter         禁用语音活动检测
--initial-prompt "..."  初始提示词，引导术语和语言行为
--task transcribe       保持原语言（默认），不翻译
--timestamps            在输出中包含时间戳
--word-timestamps       在JSON中包含词级时间戳
--format txt,md,json    输出格式：txt, md, json, srt, vtt
--overwrite             覆盖已存在的文件
```

### URL选项

```text
--max-download-mb 2048      限制下载大小（MB）
--max-duration 04:00:00     限制媒体时长
--download-timeout 30       下载超时（秒）
--network-family ipv4       网络协议：auto, ipv4, ipv6
--cookies cookies.txt       Cookies文件路径（需要登录的媒体）
--proxy http://127.0.0.1:7890  代理服务器地址
--keep-media                保留下载的媒体文件
```

### 渐进式转录选项

```text
--progressive               启用渐进式转录
--no-progressive            禁用渐进式转录
--chunk-seconds 30          每块时长（秒）
--chunk-overlap-seconds 3   重叠时长（秒）
--resume                    恢复中断的转录
--max-workers 2             并行工作线程数
```

---

## 输出文件结构

假设输入文件是 `lecture.mp4`，输出目录是 `outputs`：

```text
outputs/
├── lecture.txt          # 纯文本转录
├── lecture.md           # Markdown格式（带元信息和时间戳）
├── lecture.json         # 结构化JSON（包含分段、时间戳、词级数据）
├── lecture.srt          # SRT字幕文件
└── lecture.vtt          # WebVTT字幕文件
```

**JSON文件内容**：
- `segments` - 分段列表（文本、开始/结束时间）
- `words` - 词级时间戳（中文自然词对齐）
- `raw_words` - 原始提供商词单元
- `language` - 检测到的语言
- `duration` - 音频总时长
- 元信息（模型、参数等）

---

## 便携版构建

### 构建CLI便携版

```powershell
.\scripts\build_exe.ps1
```

输出目录：

```text
dist/FlowScribe/
├── FlowScribe.exe
├── ffmpeg.exe
├── ffprobe.exe
├── README-USER.txt
└── _internal/
```

测试：

```powershell
.\dist\FlowScribe\FlowScribe.exe doctor
```

### 构建GUI便携版

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_gui_exe.ps1 -Python python
```

输出目录：

```text
dist/FlowScribeGUI/
├── FlowScribeGUI.exe
├── WasapiCaptureHelper.exe
├── NAudio*.dll
└── _internal/
```

测试：

```powershell
.\dist\FlowScribeGUI\FlowScribeGUI.exe --self-test
```

详见：[打包文档](docs/packaging.md)

---

## 文档

### 用户文档
- [用户指南](docs/user-guide.md) - CLI完整使用指南
- [GUI用户指南](docs/gui-user-guide.md) - GUI完整使用指南
- [VAD指南](docs/vad-guide.md) - 语音活动检测使用说明
- [Inspect命令](docs/inspect.md) - 媒体检查工具
- [Cookies使用](docs/cookies.md) - 需要登录的媒体访问
- [代理配置](docs/proxy.md) - 代理服务器配置

### 开发文档
- [Agent API Guide](docs/agent-api.md) - 面向 AI agent / 自动化 / RAG 的 CLI 和 HTTP 集成说明
- [开发状态](docs/dev-state.md) - 当前开发状态和v1.0.0路线图
- [Whisper.cpp 引擎规划](docs/whispercpp-engine-plan.md) - 常驻推理引擎设计、目录结构和开发任务
- [打包文档](docs/packaging.md) - 便携版构建说明
- [发布自动化](docs/release-automation.md) - GitHub Actions发布流程
- [项目路线图](docs/roadmap.md) - 长期规划
- [JSON格式](docs/json-format.md) - 转录JSON格式说明
- [测试计划](docs/test-plan.md) - 测试策略

### 其他
- [伦理与边界](docs/ethics-and-boundaries.md) - 使用边界和法律考虑
- [发布安装](docs/release-installation.md) - 便携版安装说明

---

## 项目结构

```text
FlowScribe/
├── docs/                       项目文档
├── examples/                   示例命令
├── scripts/                    开发脚本
├── src/flowscribe/             应用源码
│   ├── app/                    服务层（TranscriptionService）
│   ├── cli/                    命令行接口
│   ├── config/                 运行时设置和预设
│   ├── core/                   领域模型、管道、渐进式转录
│   ├── gui/                    PySide6 GUI
│   │   ├── dialogs/            对话框（设置、队列项目设置）
│   │   ├── views/              视图（单任务、库、队列）
│   │   ├── widgets/            自定义组件
│   │   ├── workers/            QThread工作线程
│   │   └── utils/              工具函数
│   ├── input/                  本地文件发现和URL处理
│   ├── library/                转录库管理
│   ├── media/                  ffmpeg集成、WASAPI捕获
│   ├── nlp/                    中文分词和转换
│   ├── output/                 输出格式写入器
│   ├── queue/                  批处理队列系统
│   ├── search/                 全文搜索
│   ├── server/                 书签服务器
│   ├── transcript/             转录编辑和重新导出
│   └── transcription/          faster-whisper提供商
├── tests/                      自动化测试（44个测试文件）
└── tools/                      WASAPI捕获助手（.NET 8 C#）
```

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

详见：[伦理与边界](docs/ethics-and-boundaries.md)

---

## 常见问题

### 提示找不到 ffmpeg

安装 ffmpeg：https://ffmpeg.org/download.html

或使用自动配置脚本：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_env.ps1
```

### 中文识别错误很多

不要使用 `tiny` 模型做正式转录，使用中文预设：

```powershell
flowscribe transcribe "D:\media\chinese.mp4" -o outputs --model small --preset zh
```

### 第一次运行很慢

首次使用某个模型时需要下载模型文件（几百MB到几GB），后续运行会快很多。

### URL下载失败

常见解决方法：
- DNS问题：使用 `--network-family ipv4`
- 需要代理：使用 `--proxy "http://127.0.0.1:7890"`
- 需要登录：使用 `--cookies cookies.txt`

更多问题请参见：[用户指南](docs/user-guide.md)

---

## 贡献

欢迎提交Issue和Pull Request！

开发环境配置：

```powershell
git clone https://github.com/Ducker-Fry/FlowScribe.git
cd FlowScribe
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[gui,dev]
```

运行测试：

```powershell
python -m pytest
```

代码检查：

```powershell
python -m ruff check src tests
```

---

## 许可证

FlowScribe 采用 MIT 许可证。详见 [LICENSE](LICENSE)。

---

## 更新日志

查看 [Releases](https://github.com/Ducker-Fry/FlowScribe/releases) 页面获取完整更新日志。

**v0.3.0** (当前版本)
- GUI架构重构（QStackedWidget）
- 批处理队列增强
- 书签服务器集成
- 转录库改进

**v0.3.x** (准备中)
- CLI性能优化
- GUI UI美化
- 中文转录优化

**v0.9** (规划中)
- 原生 `whisper.cpp` 常驻推理引擎
- Windows Named Pipe 本地 IPC
- CLI 先行接入的模型常驻与长音频吞吐优化

---

**项目主页**: https://github.com/Ducker-Fry/FlowScribe  
**问题反馈**: https://github.com/Ducker-Fry/FlowScribe/issues  
**版本**: v0.3.0  
**更新日期**: 2026-05-23
