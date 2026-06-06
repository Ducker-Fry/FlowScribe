# 中文 | [English](vad-guide-en.md)

# VAD 指南

VAD 是 voice activity detection，也就是语音活动检测。

在 FlowScribe 里，`--vad-filter` 会让转录后端尝试忽略看起来像静音或非语音的部分。

它可能提升速度、减少噪声，但也可能误删真实说话内容，尤其是在音频条件比较差的时候。

## 命令

启用 VAD：

```powershell
flowscribe transcribe "D:\media\meeting.mp4" -o outputs --vad-filter
```

显式关闭 VAD：

```powershell
flowscribe transcribe "D:\media\news.mp4" -o outputs --no-vad-filter
```

URL 工作流也一样：

```powershell
flowscribe url "https://example.com/video" -o outputs --no-vad-filter
```

`--vad-filter` 和 `--no-vad-filter` 不能同时使用。

## 什么时候适合开 `--vad-filter`

- 文件里有很多长静音
- 语音段之间有明显背景噪声
- 会议、讲座、访谈这类内容里，速度比完整保留弱语音更重要
- 你更想先减少明显的非语音片段

## 什么时候不适合开 `--vad-filter`

- 开头一分钟缺字或不准
- 开头有音乐、片头音效、很轻的旁白
- 语音和背景音乐混在一起
- 说话者离麦克风很远
- 新闻片、纪录片、剪辑视频存在持续声底
- 你更想保留完整内容，哪怕多一些噪声

## 为什么新闻片头容易被过筛掉

新闻片头常常有短标题、背景音乐、压缩严重的音频或很轻的主播旁白。VAD 可能把这些误判成非语音，导致模型根本没有机会去转录这些内容。

## 推荐默认做法

FlowScribe 默认不启用 VAD。

中文预设 `--preset zh` 当前也不会强制打开 VAD，而且在你没有显式指定 `--provider` 时，它还会自动切到 `paraformer`。

```powershell
flowscribe transcribe "D:\media\chinese.mp4" -o outputs --preset zh
```

如果你想明确保持 faster-whisper 风格：

```powershell
flowscribe transcribe "D:\media\chinese.mp4" -o outputs --provider local-whisper --model small --preset zh
```

如果你怀疑 VAD 导致缺字，可以重跑：

```powershell
flowscribe transcribe "D:\media\chinese.mp4" -o outputs --preset zh --no-vad-filter --overwrite
```

如果你觉得静音噪声太多，也可以反过来试：

```powershell
flowscribe transcribe "D:\media\chinese.mp4" -o outputs --preset zh --vad-filter --overwrite
```

## 实际排查方法

1. 先不带 VAD 跑一次
2. 看开头和轻声片段是否存在
3. 再带 `--vad-filter` 跑一次
4. 对比两份结果
5. 保留更符合你目标的那一份
