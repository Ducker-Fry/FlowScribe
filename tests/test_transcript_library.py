from datetime import datetime
from pathlib import Path

from flowscribe.library import (
    LibraryMediaBinding,
    LibraryOutputRecord,
    TranscriptLibraryEntry,
    TranscriptLibraryStore,
    derive_library_entry_id,
    filter_transcript_library_entries,
    sort_transcript_library_entries,
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


def test_transcript_library_store_treats_unreadable_path_as_empty(monkeypatch, tmp_path: Path) -> None:
    store = TranscriptLibraryStore(tmp_path / "library.json")

    original_is_file = Path.is_file

    def fake_is_file(self: Path) -> bool:
        if self == store.path:
            raise PermissionError("denied")
        return original_is_file(self)

    monkeypatch.setattr(Path, "is_file", fake_is_file)

    assert store.list_entries() == ()


def test_transcript_library_store_ignores_write_failures(monkeypatch, tmp_path: Path) -> None:
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

    original_mkdir = Path.mkdir
    original_write_text = Path.write_text

    def fake_mkdir(self: Path, *args, **kwargs):
        if self == store.path.parent:
            return None
        return original_mkdir(self, *args, **kwargs)

    def fake_write_text(self: Path, *args, **kwargs):
        if self == store.path:
            raise PermissionError("denied")
        return original_write_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", fake_mkdir)
    monkeypatch.setattr(Path, "write_text", fake_write_text)

    store.save_entries((entry,))


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

    store.refresh_missing_statuses()
    removed = store.remove_missing_entries()

    assert len(removed) == 1
    assert removed[0].display_label == "Missing"
    remaining = store.list_entries()
    assert len(remaining) == 1
    assert remaining[0].display_label == "Keep"


def test_transcript_library_store_can_cleanup_entries_with_missing_outputs(tmp_path: Path) -> None:
    from flowscribe.library import LibraryOutputRecord

    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    keep_transcript = output_dir / "keep.json"
    keep_transcript.write_text('{"segments": []}', encoding="utf-8")
    keep_txt = output_dir / "keep.txt"
    keep_txt.write_text("transcript text", encoding="utf-8")

    missing_outputs_transcript = output_dir / "missing_outputs.json"
    missing_outputs_transcript.write_text('{"segments": []}', encoding="utf-8")
    missing_txt = output_dir / "missing_outputs.txt"

    store = TranscriptLibraryStore(tmp_path / "library.json")

    keep_entry = TranscriptLibraryEntry.create(
        transcript_path=keep_transcript,
        output_dir=output_dir,
        display_label="Keep",
        outputs=(LibraryOutputRecord.from_path(keep_txt),),
    )
    missing_outputs_entry = TranscriptLibraryEntry.create(
        transcript_path=missing_outputs_transcript,
        output_dir=output_dir,
        display_label="MissingOutputs",
        outputs=(LibraryOutputRecord.from_path(missing_txt),),
    )
    store.save_entries((keep_entry, missing_outputs_entry))

    store.refresh_missing_statuses()
    removed = store.remove_missing_entries()

    assert len(removed) == 1
    assert removed[0].display_label == "MissingOutputs"
    remaining = store.list_entries()
    assert len(remaining) == 1
    assert remaining[0].display_label == "Keep"


def test_filter_transcript_library_entries_supports_source_missing_and_opened_filters(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()

    local_transcript = output_dir / "local.json"
    local_transcript.write_text('{"segments": []}', encoding="utf-8")
    opened_entry = TranscriptLibraryEntry.create(
        transcript_path=local_transcript,
        output_dir=output_dir,
        display_label="Opened local",
        source_kind="local",
        last_opened_at=datetime(2026, 5, 15, 10, 0, 0),
    )

    missing_transcript = output_dir / "missing.json"
    missing_transcript.write_text('{"segments": []}', encoding="utf-8")
    missing_entry = TranscriptLibraryEntry.create(
        transcript_path=missing_transcript,
        output_dir=output_dir,
        display_label="Missing url",
        source_kind="url",
    )
    missing_transcript.unlink()
    missing_entry = missing_entry.refresh_missing_status()

    capture_transcript = output_dir / "capture.json"
    capture_transcript.write_text('{"segments": []}', encoding="utf-8")
    never_opened_entry = TranscriptLibraryEntry.create(
        transcript_path=capture_transcript,
        output_dir=output_dir,
        display_label="Never opened capture",
        source_kind="capture",
    )

    entries = (opened_entry, missing_entry, never_opened_entry)

    assert filter_transcript_library_entries(entries, source_kind="local") == (opened_entry,)
    assert filter_transcript_library_entries(entries, missing_filter="missing_only") == (
        missing_entry,
    )
    assert filter_transcript_library_entries(entries, missing_filter="available_only") == (
        opened_entry,
        never_opened_entry,
    )
    assert filter_transcript_library_entries(entries, opened_filter="opened") == (opened_entry,)
    assert filter_transcript_library_entries(entries, opened_filter="never_opened") == (
        missing_entry,
        never_opened_entry,
    )


def test_sort_transcript_library_entries_supports_multiple_modes(tmp_path: Path) -> None:
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()

    alpha_path = output_dir / "alpha.json"
    alpha_path.write_text('{"segments": []}', encoding="utf-8")
    beta_path = output_dir / "beta.json"
    beta_path.write_text('{"segments": []}', encoding="utf-8")
    gamma_path = output_dir / "gamma.json"
    gamma_path.write_text('{"segments": []}', encoding="utf-8")

    alpha = TranscriptLibraryEntry.create(
        transcript_path=alpha_path,
        output_dir=output_dir,
        display_label="Alpha",
        created_at=datetime(2026, 5, 15, 8, 0, 0),
        updated_at=datetime(2026, 5, 15, 12, 0, 0),
        last_opened_at=datetime(2026, 5, 15, 13, 0, 0),
    )
    beta = TranscriptLibraryEntry.create(
        transcript_path=beta_path,
        output_dir=output_dir,
        display_label="Beta",
        created_at=datetime(2026, 5, 15, 9, 0, 0),
        updated_at=datetime(2026, 5, 15, 11, 0, 0),
        last_opened_at=datetime(2026, 5, 15, 10, 0, 0),
    )
    gamma = TranscriptLibraryEntry.create(
        transcript_path=gamma_path,
        output_dir=output_dir,
        display_label="Gamma",
        created_at=datetime(2026, 5, 15, 10, 0, 0),
        updated_at=datetime(2026, 5, 15, 14, 0, 0),
    )

    entries = (beta, gamma, alpha)

    assert sort_transcript_library_entries(entries, sort_mode="last_opened") == (
        alpha,
        beta,
        gamma,
    )
    assert sort_transcript_library_entries(entries, sort_mode="updated") == (
        gamma,
        alpha,
        beta,
    )
    assert sort_transcript_library_entries(entries, sort_mode="created") == (
        gamma,
        beta,
        alpha,
    )
    assert sort_transcript_library_entries(entries, sort_mode="label") == (
        gamma,
        beta,
        alpha,
    )
    assert sort_transcript_library_entries(
        entries,
        sort_mode="created",
        descending=False,
    ) == (
        alpha,
        beta,
        gamma,
    )
