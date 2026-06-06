# FlowScribe JSON Format

FlowScribe JSON is the canonical structured artifact for search, GUI previews,
agent workflows, and RAG ingestion.

Current JSON output is a compatibility-first `MediaDocument`:

- it preserves older transcript fields
- it adds task-, provenance-, artifact-, and chunk-oriented fields
- new consumers should prefer the document-oriented fields

## Versioning

Each JSON file includes a schema version and generator metadata:

```json
{
  "schema_version": "1.1",
  "generator": {
    "name": "FlowScribe",
    "version": "0.3.3"
  }
}
```

Compatibility rules:

- readers should tolerate unknown fields
- older fields such as `source`, `text`, `start_seconds`, and `end_seconds`
  remain available
- newer consumers should prefer `document_id`, `task_id`, `chunks`,
  `artifacts`, and `resume`

## Top-Level Shape

Typical top-level fields:

- `schema_version`
- `document_id`
- `task_id`
- `generator`
- `source`
- `source_info`
- `language`
- `model`
- `provider`
- `created_at`
- `duration_seconds`
- `segment_count`
- `word_count`
- `raw_word_count`
- `provenance`
- `options`
- `text`
- `segments`
- `chunks`
- `artifacts`
- `media_binding`
- `resume`
- `metadata`

Example:

```json
{
  "schema_version": "1.1",
  "document_id": "4b5c4b7d1d8f8a0d3f2a4d86d16c6731",
  "task_id": "lecture-001",
  "generator": {
    "name": "FlowScribe",
    "version": "0.3.3"
  },
  "source": "D:\\media\\lecture.mp4",
  "source_info": {
    "path": "D:\\media\\lecture.mp4",
    "name": "lecture.mp4",
    "stem": "lecture",
    "suffix": ".mp4"
  },
  "language": "zh",
  "model": "small",
  "provider": "local-whisper",
  "created_at": "2026-06-04T10:00:12",
  "duration_seconds": 3600.0,
  "segment_count": 2,
  "word_count": 10,
  "raw_word_count": 12,
  "provenance": {
    "generator": "FlowScribe",
    "generator_version": "0.3.3",
    "provider": "local-whisper",
    "model": "small",
    "language": "zh",
    "created_at": "2026-06-04T10:00:12"
  },
  "text": "第一段\n第二段",
  "segments": [],
  "chunks": [],
  "artifacts": [],
  "resume": {
    "resume_token": "lecture-001",
    "checkpoint_id": "lecture-001",
    "cache_key": "v0_..."
  },
  "metadata": {}
}
```

## Document Identity Fields

### `document_id`

Stable identifier for the JSON artifact content shape. Use this as the primary
document key in downstream indexing systems.

### `task_id`

Stable task identifier for one FlowScribe execution request. This is the main
join key across:

- CLI result output
- CLI JSONL events
- HTTP `/v1/tasks`
- HTTP SSE events
- final `MediaDocument`

## Provenance And Resume Fields

### `provenance`

Tracks how the document was produced:

```json
{
  "generator": "FlowScribe",
  "generator_version": "0.3.3",
  "provider": "local-whisper",
  "model": "small",
  "language": "zh",
  "created_at": "2026-06-04T10:00:12"
}
```

### `resume`

Resume-oriented task metadata:

```json
{
  "resume_token": "lecture-001",
  "checkpoint_id": "lecture-001",
  "cache_key": "v0_..."
}
```

Use these fields when coordinating retries or resumable workflows outside the
FlowScribe process.

## Segment Fields

Each segment preserves transcript compatibility fields:

```json
{
  "id": "seg-0001",
  "index": 1,
  "text": "...",
  "start": 3.2,
  "end": 10.5,
  "start_seconds": 3.2,
  "end_seconds": 10.5,
  "duration_seconds": 7.3,
  "raw_words": [],
  "words": []
}
```

Notes:

- `raw_words` stores provider timing units
- `words` stores aligned natural words, especially useful for Chinese search
  and navigation
- `start` / `end` are preferred aliases for new consumers
- `start_seconds` / `end_seconds` remain for backward compatibility

## Word Fields

Each aligned word or token includes:

```json
{
  "index": 1,
  "word": "机器学习",
  "text": "机器学习",
  "start": 4.1,
  "end": 4.8,
  "start_seconds": 4.1,
  "end_seconds": 4.8,
  "duration_seconds": 0.7,
  "confidence": 0.91
}
```

Preferred fields for new consumers:

- `word`
- `start`
- `end`

Compatibility fields:

- `text`
- `start_seconds`
- `end_seconds`

## Chunk Fields

`chunks` are the primary RAG-oriented units. In v1, FlowScribe emits stable
chunk objects directly in the JSON artifact.

Each chunk includes:

```json
{
  "chunk_id": "23fd7d8b6dce52c5ddf8f49fb507f3b8",
  "index": 1,
  "text": "第一段内容",
  "start_seconds": 0.0,
  "end_seconds": 12.4,
  "segment_ids": ["seg-0001"],
  "segment_indexes": [1]
}
```

Recommended usage:

- use `chunk_id` as the embedding row key
- store `document_id` alongside each embedding
- keep `start_seconds` / `end_seconds` for playback and citation
- use `segment_ids` to map retrieval hits back to transcript segments

Current v1 chunking behavior:

- simple and stable
- directly traceable to transcript segments
- intended to be reproducible across repeated runs with the same inputs

## Artifact Fields

`artifacts` records every file written for the task:

```json
[
  {
    "format": "txt",
    "path": "outputs/lecture.txt"
  },
  {
    "format": "json",
    "path": "outputs/lecture.json"
  }
]
```

The JSON file itself is the canonical artifact for automation and RAG.

## Media Binding

When FlowScribe preserves or binds media to the transcript, `media_binding`
captures the playable source:

```json
{
  "path": "outputs/url-media/remote-media.mp4",
  "kind": "video"
}
```

This is especially useful for:

- transcript viewers
- click-to-jump playback
- agent systems that need citations back to the original media

## Legacy Compatibility

Legacy readers can continue to rely on:

- `source`
- `text`
- `segments`
- `start_seconds`
- `end_seconds`
- `words`
- `raw_words`

New integrations should prefer:

- `document_id`
- `task_id`
- `provenance`
- `chunks`
- `artifacts`
- `resume`

## Integration Guidance

For agents and workflow tools:

- read `task_id` and `resume` to correlate runs
- ingest `chunks` into vector or search indexes
- use `artifacts` to discover sibling txt/md/srt/vtt outputs
- use `media_binding` and chunk timestamps for user-visible citations

For more automation-specific examples, see
[Agent API Guide](agent-api.md).
