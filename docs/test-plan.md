# Test Plan

## Purpose

The test plan ensures FlowScribe works for real transcription workflows rather than only for ideal sample files.

## v0.1 Test Matrix

| Case | Input | Expected Result |
| --- | --- | --- |
| Local video | MP4 with speech | TXT and Markdown transcripts are created |
| Local audio | MP3 or WAV | TXT and Markdown transcripts are created |
| Chinese speech | Chinese media sample | Transcript contains recognizable Chinese text |
| English speech | English media sample | Transcript contains recognizable English text |
| Mixed language | Chinese and English media sample | Both languages are recognized reasonably |
| Batch folder | Folder with multiple media files | All valid files are processed |
| Invalid file | Unsupported or damaged file | Error is reported and batch continues |
| No audio | Video without audio track | Clear failure message is produced |

## Manual Acceptance Criteria

- The CLI command is understandable.
- Output files are easy to find.
- Transcript text can be copied into an AI assistant.
- Errors are readable by a non-expert user.
- Batch processing does not stop because one file fails.

## Automated Test Targets

- File discovery.
- Output path generation.
- Transcript writer formatting.
- Job orchestration behavior.
- Error handling behavior.
