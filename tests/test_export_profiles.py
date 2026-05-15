from flowscribe.gui.export_profiles import (
    ExportProfile,
    apply_export_profile,
    create_export_profile,
    export_profiles_payload,
    normalize_export_profiles_payload,
    profile_list_label,
    remove_export_profile,
    upsert_export_profile,
)


def test_create_export_profile_uses_named_export_settings() -> None:
    profile = create_export_profile(
        "字幕导出",
        {
            "output_formats": ["json", "srt", "vtt"],
            "timestamps": True,
            "word_timestamps": False,
        },
    )

    assert profile.name == "字幕导出"
    assert profile.output_formats == ("json", "srt", "vtt")
    assert profile.timestamps is True
    assert profile.word_timestamps is False


def test_apply_export_profile_updates_only_export_preferences() -> None:
    updated = apply_export_profile(
        ExportProfile(
            name="Review",
            output_formats=("txt", "md"),
            timestamps=False,
            word_timestamps=True,
        ),
        {
            "output_dir": "outputs",
            "output_formats": ["json"],
            "timestamps": True,
            "word_timestamps": False,
        },
    )

    assert updated["output_dir"] == "outputs"
    assert updated["output_formats"] == ["txt", "md"]
    assert updated["timestamps"] is False
    assert updated["word_timestamps"] is True


def test_upsert_and_remove_export_profile_manage_named_profiles() -> None:
    profiles = ()
    profiles = upsert_export_profile(
        profiles,
        ExportProfile(name="Default", output_formats=("txt", "md", "json")),
    )
    profiles = upsert_export_profile(
        profiles,
        ExportProfile(name="Subtitles", output_formats=("srt", "vtt")),
    )
    profiles = upsert_export_profile(
        profiles,
        ExportProfile(name="Default", output_formats=("txt",)),
    )

    assert [profile.name for profile in profiles] == ["Default", "Subtitles"]
    assert profiles[0].output_formats == ("txt",)

    remaining = remove_export_profile(profiles, "Subtitles")
    assert [profile.name for profile in remaining] == ["Default"]


def test_export_profiles_payload_round_trips_and_filters_invalid_entries() -> None:
    payload = export_profiles_payload(
        (
            ExportProfile(
                name="Review",
                output_formats=("txt", "md"),
                timestamps=True,
                word_timestamps=False,
            ),
        )
    )

    normalized = normalize_export_profiles_payload(
        payload
        + [
            {"name": "", "output_formats": ["txt"]},
            {"name": "Review", "output_formats": ["json"]},
            {"name": "Broken", "output_formats": ["bad"]},
        ]
    )

    assert normalized[0].name == "Review"
    assert normalized[0].output_formats == ("txt", "md")
    assert normalized[1].name == "Broken"
    assert normalized[1].output_formats == ("txt", "md", "json")


def test_profile_list_label_summarizes_export_profile() -> None:
    label = profile_list_label(
        ExportProfile(
            name="Archive",
            output_formats=("json", "txt"),
            timestamps=False,
            word_timestamps=True,
        )
    )

    assert "Archive" in label
    assert "Formats: json, txt" in label
    assert "Timestamps: off" in label
    assert "Word timestamps: on" in label
