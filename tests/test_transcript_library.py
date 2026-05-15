from datetime import datetime
from pathlib import Path

from flowscribe.library import (
    LibraryMediaBinding,
    LibraryOutputRecord,
    TranscriptLibraryEntry,
    TranscriptLibraryStore,
    derive_library_entry_id,
)


def test_transcript_library_store_round_trips_entry_with_outputs_and_binding(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    transcript = output_dir / "lesson.json"
    transcript.write_text('{"segments": []}', encoding="utf-8")
    media = tmp_path / "lesson.mp4"
    media.write_bytes(b"media")
    txt_output = output_dir / "lesson.txt"
    txt_output.write_text("hello", encoding="utf-8")
    md_output = output_dir / "lesson.md"
    md_output.write_text("# hello", encoding="utf-8")

    store = TranscriptLibraryStore(tmp_path / "library.json")
    created_at = datetime(2026, 5, 15, 12, 0, 0)
    binding = LibraryMediaBinding.create(
        transcript_path=transcript,
        media_path=media,
        binding_type="manual",
        updated_at=created_at,
    )
    entry = TranscriptLibraryEntry.create(
        transcript_path=transcript,
        output_dir=output_dir,
        display_label="Lesson transcript",
        source_kind="local",
        source_media_path=media,
        created_at=created_at,
        updated_at=created_at,
        last_opened_at=created_at,
        media_binding=binding,
        outputs=(
            LibraryOutputRecord.from_path(transcript),
            LibraryOutputRecord.from_path(txt_output),
            LibraryOutputRecord.from_path(md_output),
        ),
    )

    saved = store.upsert_entry(entry)
    loaded = store.list_entries()

    assert saved.entry_id == derive_library_entry_id(transcript)
    assert len(loaded) == 1
    assert loaded[0].display_label == "Lesson transcript"
    assert loaded[0].source_kind == "local"
    assert loaded[0].source_media_path == media.resolve()
    assert loaded[0].media_binding is not None
    assert loaded[0].media_binding.media_path == media.resolve()
    assert [output.kind for output in loaded[0].outputs] == ["json", "txt", "md"]
    assert loaded[0].missing is False


def test_transcript_library_store_marks_missing_paths_on_load(tmp_path: Path) -> None:
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    transcript = output_dir / "lesson.json"
    transcript.write_text('{"segments": []}', encoding="utf-8")
    media = tmp_path / "lesson.mp4"
    media.write_bytes(b"media")
    subtitle = output_dir / "lesson.srt"
    subtitle.write_text("1", encoding="utf-8")

    store = TranscriptLibraryStore(tmp_path / "library.json")
    entry = TranscriptLibraryEntry.create(
        transcript_path=transcript,
        output_dir=output_dir,
        display_label="Lesson transcript",
        source_kind="local",
        source_media_path=media,
        media_binding=LibraryMediaBinding.create(
            transcript_path=transcript,
            media_path=media,
        ),
        outputs=(
            LibraryOutputRecord.from_path(transcript),
            LibraryOutputRecord.from_path(subtitle),
        ),
    )
    store.save_entries((entry,))

    transcript.unlink()
    media.unlink()
    subtitle.unlink()

    refreshed = store.list_entries()[0]

    assert refreshed.missing is True
    assert "transcript" in refreshed.missing_paths
    assert "source_media" in refreshed.missing_paths
    assert "bound_media" in refreshed.missing_paths
    assert "outputs" in refreshed.missing_paths


def test_transcript_library_store_recovers_from_corrupt_json(tmp_path: Path) -> None:
    store_path = tmp_path / "library.json"
    store_path.write_text("{not valid json", encoding="utf-8")

    store = TranscriptLibraryStore(store_path)
    loaded = store.list_entries()

    assert loaded == ()
    assert store_path.exists() is False
    backups = list(tmp_path.glob("library.json.corrupt-*"))
    assert len(backups) == 1


def test_transcript_library_store_marks_opened_timestamp(tmp_path: Path) -> None:
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    transcript = output_dir / "lesson.json"
    transcript.write_text('{"segments": []}', encoding="utf-8")
    store = TranscriptLibraryStore(tmp_path / "library.json")

    entry = TranscriptLibraryEntry.create(
        transcript_path=transcript,
        output_dir=output_dir,
        display_label="Lesson transcript",
    )
    store.save_entries((entry,))

    opened_at = datetime(2026, 5, 15, 18, 30, 0)
    updated = store.mark_opened(entry.entry_id, opened_at=opened_at)

    assert updated is not None
    assert updated.last_opened_at == opened_at
    assert store.get_entry(entry.entry_id) is not None
    assert store.get_entry(entry.entry_id).last_opened_at == opened_at


def test_transcript_library_store_can_remove_entry_by_transcript_path(tmp_path: Path) -> None:
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    transcript = output_dir / "lesson.json"
    transcript.write_text('{"segments": []}', encoding="utf-8")
    store = TranscriptLibraryStore(tmp_path / "library.json")

    entry = TranscriptLibraryEntry.create(
        transcript_path=transcript,
        output_dir=output_dir,
        display_label="Lesson transcript",
    )
    store.save_entries((entry,))

    assert store.remove_entry_by_transcript_path(transcript) is True
    assert store.list_entries() == ()


def test_transcript_library_store_can_cleanup_missing_transcript_entries(tmp_path: Path) -> None:
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    keep_transcript = output_dir / "keep.json"
    keep_transcript.write_text('{"segments": []}', encoding="utf-8")
    missing_transcript = output_dir / "missing.json"
    missing_transcript.write_text('{"segments": []}', encoding="utf-8")
    store = TranscriptLibraryStore(tmp_path / "library.json")

    keep_entry = TranscriptLibraryEntry.create(
        transcript_path=keep_transcript,
        output_dir=output_dir,
        display_label="Keep",
    )
    missing_entry = TranscriptLibraryEntry.create(
        transcript_path=missing_transcript,
        output_dir=output_dir,
        display_label="Missing",
    )
    store.save_entries((keep_entry, missing_entry))

    missing_transcript.unlink()

    removed = store.remove_missing_entries()

    assert len(removed) == 1
    assert removed[0].display_label == "Missing"
    remaining = store.list_entries()
    assert len(remaining) == 1
    assert remaining[0].display_label == "Keep"
