# FlowScribe JSON Format

FlowScribe JSON is the stable intermediate format for search, GUI previews, subtitle tooling, and AI analysis.

## Versioning

Each file includes:

```json
{
  "schema_version": "1.1",
  "generator": {
    "name": "FlowScribe",
    "version": "0.1.0"
  }
}
```

Readers should tolerate unknown fields. FlowScribe keeps older compatibility fields such as `start_seconds`, `end_seconds`, and `text` while adding clearer aliases such as `start`, `end`, and `word`.

## Top-Level Fields

- `source`: source media path as a string, kept for compatibility.
- `source_info`: structured source metadata: path, filename, stem, and suffix.
- `language`: detected or configured transcript language.
- `model`: transcription model name.
- `created_at`: local creation time.
- `duration_seconds`: estimated transcript span from first segment start to last segment end.
- `segment_count`: number of transcript segments.
- `word_count`: number of aligned words.
- `raw_word_count`: number of provider timing units.
- `options`: transcription options used to produce the transcript.
- `text`: full transcript text.
- `segments`: ordered transcript segments.

## Segment Fields

Each segment includes:

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

`raw_words` stores provider timing units. `words` stores aligned natural words, especially useful for Chinese navigation and keyword search.

## Word Fields

Each word includes:

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

`word`, `start`, and `end` are the preferred fields for new consumers. `text`, `start_seconds`, and `end_seconds` remain available for compatibility with earlier FlowScribe JSON output.
