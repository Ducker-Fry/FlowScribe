# Native Engine Smoke Test

This document records the current single-thread Python to C++ transcription loop.

## Model

Use a real whisper.cpp ggml model. Test models under `third_party/whisper.cpp/models/for-tests-*`
are too small for real transcription.

Recommended local path:

```powershell
E:\Draft\FlowScribe\models\ggml-base.en.bin
```

The `base.en` model is about 148 MB. If the file is only a few hundred KB, it is not a real
transcription model.

## Audio

The native engine currently expects a local audio file readable by whisper.cpp. For the most
reliable smoke test, use WAV:

```powershell
E:\Draft\FlowScribe\samples\english_test.wav
```

Python remains responsible for downloading media, extracting audio from video, and converting
other formats before submitting a job.

## Build

```powershell
cd E:\Draft\FlowScribe
cmake --build native\flowscribe-engine\build --config Debug
```

## Run

CLI path with the provider integration:

```powershell
cd E:\Draft\FlowScribe
$env:PYTHONPATH="E:\Draft\FlowScribe\src"
python -m flowscribe transcribe "E:\Draft\FlowScribe\samples\english_test.wav" --provider native-engine --model "E:\Draft\FlowScribe\models\ggml-base.en.bin" --format json --overwrite
```

URL path once a real public URL is available:

```powershell
cd E:\Draft\FlowScribe
$env:PYTHONPATH="E:\Draft\FlowScribe\src"
python -m flowscribe url "https://example.com/video" --provider native-engine --model "E:\Draft\FlowScribe\models\ggml-base.en.bin" --format json --overwrite
```

Low-level IPC smoke:

Start the native engine in one PowerShell window:

```powershell
cd E:\Draft\FlowScribe\native\flowscribe-engine\build\Debug
.\flowscribe-engine.exe
```

Run the Python smoke test in another PowerShell window:

```powershell
cd E:\Draft\FlowScribe
$env:PYTHONPATH="E:\Draft\FlowScribe\src"
python -m flowscribe.engine_smoke --extended --model-path "E:\Draft\FlowScribe\models\ggml-base.en.bin" --model-name "base.en" --audio-path "E:\Draft\FlowScribe\samples\english_test.wav" --query-after-result
```

The final `AsyncMessage kind=49` is `JobResult`. The smoke test also prints `Transcript:` with
the segment text joined into a readable transcript.

## Mock IPC Regression

Use this when you only want to validate IPC framing and message flow:

```powershell
cd E:\Draft\FlowScribe
$env:PYTHONPATH="E:\Draft\FlowScribe\src"
python -m flowscribe.engine_smoke --extended --mock-files --query-after-result
```

## Common Errors

`Connection failed`

The native engine is not running, or the named pipe is already held by another process.

`LoadModelResult(ok=false, error="model file does not exist")`

The `--model-path` argument is wrong.

`SubmitJobResult(ok=false, error="audio file does not exist")`

The `--audio-path` argument is wrong.

`JobError(code="job_failed")`

The model loaded, but transcription failed. Check whether the audio file is readable by
whisper.cpp. Start with a WAV file before testing other formats.

No real transcript, only `Sample transcription result...`

The smoke test is running with `--mock-files` or `--model-name "__mock__"`.
