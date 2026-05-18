# Transcript Deduplication

## Overview

The transcript deduplication feature automatically removes duplicate segments that can occur at chunk boundaries during progressive transcription. This is especially important for long audio files that are processed in overlapping chunks.

## How It Works

1. **During transcription**: Chunks are processed with overlap (default 3 seconds) to ensure no content is lost at boundaries
2. **After transcription completes**: The `TranscriptDeduplicator` removes duplicate segments based on:
   - Text similarity (exact match or substring)
   - Temporal proximity (segments close in time)
   - Timing quality (prefers segments with better timestamp information)

## Usage

### Automatic (Default)

Deduplication is enabled by default in `LocalTranscriptionPipeline`:

```python
from flowscribe.core.pipeline import LocalTranscriptionPipeline

pipeline = LocalTranscriptionPipeline(
    media_preparer=preparer,
    transcriber=transcriber,
    artifact_writer=writer,
    work_dir=work_dir,
    output_dir=output_dir,
    enable_deduplication=True,  # Default
)
```

### Manual

You can also use `TranscriptDeduplicator` directly:

```python
from flowscribe.core.deduplication import TranscriptDeduplicator

deduplicator = TranscriptDeduplicator(
    text_similarity_threshold=0.9,  # 90% similarity to consider duplicate
    time_overlap_threshold_seconds=2.0,  # Max time gap for overlapping segments
)

deduplicated_transcript = deduplicator.deduplicate(transcript)
```

### Disable Deduplication

If you need to disable deduplication:

```python
pipeline = LocalTranscriptionPipeline(
    # ... other parameters
    enable_deduplication=False,
)
```

## Configuration

### `text_similarity_threshold` (default: 0.9)

Minimum similarity ratio (0.0 to 1.0) to consider two segments as duplicates. Higher values are more strict.

### `time_overlap_threshold_seconds` (default: 2.0)

Maximum time gap in seconds between segment start times to consider them as overlapping. Segments with the same text but far apart in time are kept.

## Example

See [examples/deduplication_example.py](../examples/deduplication_example.py) for a complete example.

## Design Rationale

**Why not deduplicate during chunk merging?**

The deduplication happens *after* all chunks are merged and consistency checks are complete, not during the merge process. This approach:

1. Keeps the merge logic simple and focused on temporal ordering
2. Allows the consistency checker to validate the full transcript first
3. Provides a clean separation of concerns
4. Makes it easy to disable or customize deduplication independently

**Why keep overlaps during transcription?**

Overlapping chunks ensure that:
- No speech is lost at chunk boundaries
- Context is preserved for better transcription accuracy
- Timestamp alignment is more reliable

The deduplication step then cleans up the redundancy in the final output.

## Testing

Run the deduplication tests:

```powershell
python -m pytest tests/test_deduplication.py tests/test_deduplication_integration.py -v
```
