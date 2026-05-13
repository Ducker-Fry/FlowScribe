# FlowScribe Demo

This demo shows a real public URL transcription workflow using a CCTV video page.
It is intended as a quick proof that FlowScribe can process URL input without saving
high-resolution video files.

## Demo Source

Public URL:

```text
https://tv.cctv.com/2026/05/12/VIDEBtNAQbQRT5vvxRFP28FR260512.shtml
```

This page does not expose a standalone audio-only stream. FlowScribe handles it by
selecting the smallest combined media stream and asking `ffmpeg` to extract audio
directly. The saved intermediate file is audio, not the original video.

## Run The Demo

From the repository root:

```powershell
flowscribe url "https://tv.cctv.com/2026/05/12/VIDEBtNAQbQRT5vvxRFP28FR260512.shtml" -o outputs\demo-cctv --format txt,md,json --model small --language zh --preset zh --max-download-mb 500 --max-duration 00:30:00 --download-timeout 30 --overwrite
```

Or run the example script:

```powershell
.\examples\url-cctv-demo.ps1
```

For a faster smoke test, use `tiny`:

```powershell
.\examples\url-cctv-demo.ps1 -Model tiny -OutputDir outputs\demo-cctv-tiny
```

`tiny` is useful only for testing the pipeline. Use `small` or larger models for
real Chinese transcription.

## Expected Terminal Output

The exact paths may differ, but a successful run should look like this:

```text
Downloading/extracting remote audio...
Remote audio ready: E:\Draft\FlowScribe\outputs\demo-cctv\.flowscribe-work\.url-media\url-...\remote-audio.m4a
Wrote: E:\Draft\FlowScribe\outputs\demo-cctv\remote-audio.txt
Wrote: E:\Draft\FlowScribe\outputs\demo-cctv\remote-audio.md
Wrote: E:\Draft\FlowScribe\outputs\demo-cctv\remote-audio.json
Done. Succeeded: 1. Failed: 0.
```

## Expected Files

```text
outputs/demo-cctv/
|-- remote-audio.txt
|-- remote-audio.md
`-- remote-audio.json
```

Temporary files live under `.flowscribe-work`. URL media files are automatically
deleted unless `--keep-media` is used.

## Example Transcript Excerpt

With `small`, the transcript should contain readable Simplified Chinese, similar to:

```text
更多新闻资讯,来看一组简讯。
11号,两高联合发布《办理非法占用耕地案件司法》解释,强化对耕地的全链条保护。
2023年以来,全国检察机关共办理非法占用耕地公益诉讼案件1.7万余件,监督保护耕地46.87万亩。
2020年至2025年,全国法院共办结耕地保护领域执行案件14361件。
```

Speech recognition may still mishear proper nouns or technical terms. For better
quality, try `--model medium` and provide a more specific `--initial-prompt`.

## Search The Result

After JSON output is generated, locate a keyword:

```powershell
flowscribe search outputs\demo-cctv\remote-audio.json "耕地" --limit 5 --context-chars 40
```

Expected shape:

```text
[1]
File: outputs\demo-cctv\remote-audio.json
Match: 耕地
Time: 00:00:05.000 - 00:00:12.000
Context: 11号,两高联合发布《办理非法占用耕地案件司法》解释...
```

## Troubleshooting

- If the beginning is missing, retry without `--vad-filter`. VAD can over-filter
  news intros, music beds, or low-volume openings.
- If the URL fails, the site may require login, block automated access, or use DRM.
- If the first model run is slow, the Whisper model may be downloading.
- If terminal text looks garbled, open the generated `.txt` file as UTF-8.
