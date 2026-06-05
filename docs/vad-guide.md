# VAD Guide

VAD means voice activity detection. In FlowScribe, `--vad-filter` asks the
transcription backend to ignore parts that look like silence or non-speech.

It can improve speed and reduce noise, but it can also remove real speech when
the audio is difficult.

## Commands

Enable VAD:

```powershell
flowscribe transcribe "D:\media\meeting.mp4" -o outputs --vad-filter
```

Explicitly disable VAD:

```powershell
flowscribe transcribe "D:\media\news.mp4" -o outputs --no-vad-filter
```

URL input uses the same flags:

```powershell
flowscribe url "https://example.com/video" -o outputs --no-vad-filter
```

`--vad-filter` and `--no-vad-filter` are mutually exclusive.

## When To Use `--vad-filter`

Use VAD when:

- The file has long silent sections.
- The recording has background noise between speech sections.
- You want to reduce obvious non-speech parts in meetings, lectures, or interviews.
- Speed matters more than preserving every possible spoken fragment.

## When Not To Use `--vad-filter`

Avoid VAD when:

- The first minute of a video is missing or inaccurate.
- The video starts with music, intro sound, or low-volume narration.
- Speech is mixed with background music.
- The speaker is far from the microphone.
- You are processing news clips, documentaries, or edited videos with sound beds.
- You need a nearly complete transcript and can tolerate some extra noise.

## Why News Intros Can Be Over-Filtered

News clips often start with a short title, music bed, compressed audio, or quiet
anchor narration. VAD may classify these segments as non-speech because the voice
is mixed with other audio or has a weak signal. The result can look like this:

```text
00:00 - 00:03 recognized
00:03 - 00:30 missing
00:30 onward recognized normally
```

This does not necessarily mean the model cannot understand the language. It may
mean the VAD step removed the audio before the model had a chance to transcribe it.

## Recommended Defaults

FlowScribe does not enable VAD by default.

The Chinese preset also does not force VAD. In current builds, `--preset zh`
also auto-selects the `paraformer` provider when you do not pass `--provider`
explicitly. Use:

```powershell
flowscribe transcribe "D:\media\chinese.mp4" -o outputs --preset zh
```

If you want to keep the older faster-whisper style explicitly, use:

```powershell
flowscribe transcribe "D:\media\chinese.mp4" -o outputs --provider local-whisper --model small --preset zh
```

If you suspect VAD is causing missing text, rerun with:

```powershell
flowscribe transcribe "D:\media\chinese.mp4" -o outputs --preset zh --no-vad-filter --overwrite
```

If the transcript contains too much silence-related noise, rerun with:

```powershell
flowscribe transcribe "D:\media\chinese.mp4" -o outputs --preset zh --vad-filter --overwrite
```

## Practical Debugging

1. Run once without VAD.
2. Check whether the opening and quiet sections are present.
3. Run again with `--vad-filter`.
4. Compare the first minute and low-volume sections.
5. Keep the version that preserves the content you care about.

For short videos, disabling VAD is usually safer. For long recordings with many
silent sections, VAD may be useful.
