[中文](vad-guide.md) | English

# VAD Guide

VAD means voice activity detection. In FlowScribe, `--vad-filter` asks the transcription backend to ignore audio that looks like silence or non-speech.

## Commands

Enable VAD:

```powershell
flowscribe transcribe "D:\media\meeting.mp4" -o outputs --vad-filter
```

Disable VAD explicitly:

```powershell
flowscribe transcribe "D:\media\news.mp4" -o outputs --no-vad-filter
```

URL input uses the same flags:

```powershell
flowscribe url "https://example.com/video" -o outputs --no-vad-filter
```

## When To Use `--vad-filter`

- long silence sections
- background noise between speech
- meetings, lectures, or interviews where speed matters
- when some non-speech filtering is more valuable than keeping every weak fragment

## When Not To Use `--vad-filter`

- missing or weak opening minute
- low-volume narration
- mixed music and speech
- distant speakers
- edited videos with background beds
- cases where you prefer completeness over speed

## Why Intros Can Be Over-Filtered

News clips, documentaries, and edited videos often begin with music beds, compressed audio, or weak narration. VAD can remove real speech before the model sees it.

## Recommended Defaults

FlowScribe does not enable VAD by default.

The Chinese preset also does not force VAD. In current builds, `--preset zh` auto-selects `paraformer` when `--provider` is omitted.

```powershell
flowscribe transcribe "D:\media\chinese.mp4" -o outputs --preset zh
```

If you want the older faster-whisper style explicitly:

```powershell
flowscribe transcribe "D:\media\chinese.mp4" -o outputs --provider local-whisper --model small --preset zh
```

If you suspect VAD is removing text:

```powershell
flowscribe transcribe "D:\media\chinese.mp4" -o outputs --preset zh --no-vad-filter --overwrite
```

If the transcript contains too much silence-related noise:

```powershell
flowscribe transcribe "D:\media\chinese.mp4" -o outputs --preset zh --vad-filter --overwrite
```

## Practical Debugging

1. run once without VAD
2. inspect the first minute and quiet parts
3. run again with VAD
4. compare the differences
5. keep the result that preserves the content you care about
