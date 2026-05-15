"""Named export profile helpers for the GUI."""

from __future__ import annotations

from dataclasses import dataclass

from flowscribe.gui.state import SUPPORTED_GUI_FORMATS


@dataclass(frozen=True)
class ExportProfile:
    """Reusable non-sensitive export settings."""

    name: str
    output_formats: tuple[str, ...]
    timestamps: bool = True
    word_timestamps: bool = False


def create_export_profile(name: str, preferences: dict[str, object]) -> ExportProfile:
    normalized_name = _normalize_profile_name(name)
    output_formats = tuple(
        output_format
        for output_format in preferences.get("output_formats", [])
        if output_format in SUPPORTED_GUI_FORMATS
    )
    if not output_formats:
        output_formats = ("txt", "md", "json")
    return ExportProfile(
        name=normalized_name,
        output_formats=output_formats,
        timestamps=bool(preferences.get("timestamps", True)),
        word_timestamps=bool(preferences.get("word_timestamps", False)),
    )


def apply_export_profile(
    profile: ExportProfile,
    preferences: dict[str, object],
) -> dict[str, object]:
    updated = dict(preferences)
    updated["output_formats"] = list(profile.output_formats)
    updated["timestamps"] = profile.timestamps
    updated["word_timestamps"] = profile.word_timestamps
    return updated


def upsert_export_profile(
    profiles: tuple[ExportProfile, ...],
    profile: ExportProfile,
) -> tuple[ExportProfile, ...]:
    updated = [existing for existing in profiles if existing.name != profile.name]
    updated.insert(0, profile)
    return tuple(updated)


def remove_export_profile(
    profiles: tuple[ExportProfile, ...],
    name: str,
) -> tuple[ExportProfile, ...]:
    normalized_name = _normalize_profile_name(name)
    return tuple(profile for profile in profiles if profile.name != normalized_name)


def export_profiles_payload(profiles: tuple[ExportProfile, ...]) -> list[dict[str, object]]:
    return [
        {
            "name": profile.name,
            "output_formats": list(profile.output_formats),
            "timestamps": profile.timestamps,
            "word_timestamps": profile.word_timestamps,
        }
        for profile in profiles
    ]


def normalize_export_profiles_payload(payload: object) -> tuple[ExportProfile, ...]:
    if not isinstance(payload, list):
        return ()

    normalized: list[ExportProfile] = []
    seen: set[str] = set()
    for raw_profile in payload:
        if not isinstance(raw_profile, dict):
            continue
        name = raw_profile.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        normalized_name = _normalize_profile_name(name)
        if normalized_name in seen:
            continue
        seen.add(normalized_name)
        output_formats = tuple(
            output_format
            for output_format in raw_profile.get("output_formats", [])
            if output_format in SUPPORTED_GUI_FORMATS
        )
        normalized.append(
            ExportProfile(
                name=normalized_name,
                output_formats=output_formats or ("txt", "md", "json"),
                timestamps=bool(raw_profile.get("timestamps", True)),
                word_timestamps=bool(raw_profile.get("word_timestamps", False)),
            )
        )
    return tuple(normalized)


def profile_list_label(profile: ExportProfile) -> str:
    formats = ", ".join(profile.output_formats)
    return (
        f"{profile.name}\n"
        f"Formats: {formats} | "
        f"Timestamps: {'on' if profile.timestamps else 'off'} | "
        f"Word timestamps: {'on' if profile.word_timestamps else 'off'}"
    )


def _normalize_profile_name(name: str) -> str:
    text = str(name).strip()
    if not text:
        raise ValueError("Export profile name cannot be empty.")
    return text
