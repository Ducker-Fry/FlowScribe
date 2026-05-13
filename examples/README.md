# FlowScribe Examples

This directory contains copyable commands for common FlowScribe workflows.

## Public URL Demo

Run the CCTV public URL demo with a Chinese-oriented model:

```powershell
.\examples\url-cctv-demo.ps1
```

Use a faster smoke-test model:

```powershell
.\examples\url-cctv-demo.ps1 -Model tiny -OutputDir outputs\demo-cctv-tiny
```

## Local File

Transcribe one local media file:

```powershell
.\examples\local-file-basic.ps1 -InputPath "D:\media\lecture.mp4"
```

Write timestamped transcript, JSON, SRT, and VTT:

```powershell
.\examples\local-file-timestamps.ps1 -InputPath "D:\media\lecture.mp4"
```

## Search

After producing JSON output, search for a keyword and locate its timestamp:

```powershell
.\examples\search-json.ps1 -TranscriptPath "outputs\lecture.json" -Query "机器学习"
```

These examples assume FlowScribe is installed from source or the `flowscribe` console command
is available on `PATH`.
