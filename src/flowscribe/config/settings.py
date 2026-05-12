"""Runtime settings for FlowScribe."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ZH_INITIAL_PROMPT = (
    "以下是普通话、中文和英语可能混合出现的逐字转写。"
    "请使用简体中文输出，保留原语言内容，不要翻译；"
    "专有名词、技术词和英文按原文转写。"
)


@dataclass(frozen=True)
class AppSettings:
    output_dir: Path
    work_dir: Path
    model_name: str
    language: str | None
    preset: str | None
    task: str
    beam_size: int
    vad_filter: bool
    initial_prompt: str | None
    word_timestamps: bool
    recursive: bool
    overwrite: bool
    keep_audio: bool
    sample_rate: int = 16000

    @classmethod
    def from_options(
        cls,
        *,
        output_dir: Path,
        work_dir: Path | None,
        model_name: str,
        language: str | None,
        preset: str | None,
        task: str,
        beam_size: int,
        vad_filter: bool,
        initial_prompt: str | None,
        word_timestamps: bool,
        recursive: bool,
        overwrite: bool,
        keep_audio: bool,
    ) -> "AppSettings":
        resolved_output = output_dir.expanduser().resolve()
        resolved_work = (
            work_dir.expanduser().resolve()
            if work_dir is not None
            else resolved_output / ".flowscribe-work"
        )
        effective_language = language
        effective_vad_filter = vad_filter
        effective_initial_prompt = initial_prompt

        if preset == "zh":
            effective_language = effective_language or "zh"
            effective_vad_filter = True
            effective_initial_prompt = effective_initial_prompt or ZH_INITIAL_PROMPT

        return cls(
            output_dir=resolved_output,
            work_dir=resolved_work,
            model_name=model_name,
            language=effective_language,
            preset=preset,
            task=task,
            beam_size=beam_size,
            vad_filter=effective_vad_filter,
            initial_prompt=effective_initial_prompt,
            word_timestamps=word_timestamps,
            recursive=recursive,
            overwrite=overwrite,
            keep_audio=keep_audio,
        )
