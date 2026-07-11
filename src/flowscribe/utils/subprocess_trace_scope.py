"""Scoped subprocess tracing for pinpointing hidden third-party child processes."""

from __future__ import annotations

import inspect
import importlib
import logging
import os
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

TRACE_ENV_NAME = "FLOWSCRIBE_FUNASR_SUBPROCESS_TRACE"


def scoped_subprocess_trace_enabled() -> bool:
    value = os.environ.get(TRACE_ENV_NAME, "")
    return value.strip().lower() in {"1", "true", "yes", "on"}


@contextmanager
def trace_subprocess_scope(
    label: str,
    *,
    logger: logging.Logger,
) -> Iterator[None]:
    """Log subprocess calls made inside the active scope when enabled."""

    if not scoped_subprocess_trace_enabled():
        yield
        return

    originals = {
        "Popen": subprocess.Popen,
        "run": subprocess.run,
        "check_output": subprocess.check_output,
        "check_call": subprocess.check_call,
        "call": subprocess.call,
    }

    def _wrap(name: str, original):
        def _wrapped(*args: Any, **kwargs: Any):
            logger.warning(
                "Scoped subprocess trace: label=%s api=%s command=%s caller=%s",
                label,
                name,
                _format_command(args, kwargs),
                _find_external_caller(),
            )
            return original(*args, **kwargs)

        return _wrapped

    try:
        subprocess.Popen = _wrap("Popen", originals["Popen"])
        subprocess.run = _wrap("run", originals["run"])
        subprocess.check_output = _wrap("check_output", originals["check_output"])
        subprocess.check_call = _wrap("check_call", originals["check_call"])
        subprocess.call = _wrap("call", originals["call"])
        logger.info("Scoped subprocess trace enabled: %s", label)
        yield
    finally:
        subprocess.Popen = originals["Popen"]
        subprocess.run = originals["run"]
        subprocess.check_output = originals["check_output"]
        subprocess.check_call = originals["check_call"]
        subprocess.call = originals["call"]
        logger.info("Scoped subprocess trace disabled: %s", label)


@contextmanager
def trace_funasr_audio_loading_scope(
    label: str,
    *,
    logger: logging.Logger,
) -> Iterator[None]:
    """Trace which FunASR audio backend path is actually used."""

    if not scoped_subprocess_trace_enabled():
        yield
        return

    patched: list[tuple[Any, str, Any]] = []
    try:
        load_utils = importlib.import_module("funasr.utils.load_utils")
        _patch_attr(
            patched,
            owner=load_utils,
            name="_load_audio_ffmpeg",
            wrapper=_wrap_audio_backend_call(
                label=label,
                backend="funasr._load_audio_ffmpeg",
                logger=logger,
            ),
        )
    except Exception as exc:
        logger.info("Audio backend trace skipped for funasr.load_utils: %s", exc)

    try:
        torchaudio = importlib.import_module("torchaudio")
        _patch_attr(
            patched,
            owner=torchaudio,
            name="load",
            wrapper=_wrap_audio_backend_call(
                label=label,
                backend="torchaudio.load",
                logger=logger,
            ),
        )
    except Exception as exc:
        logger.info("Audio backend trace skipped for torchaudio: %s", exc)

    try:
        soundfile = importlib.import_module("soundfile")
        _patch_attr(
            patched,
            owner=soundfile,
            name="read",
            wrapper=_wrap_audio_backend_call(
                label=label,
                backend="soundfile.read",
                logger=logger,
            ),
        )
    except Exception as exc:
        logger.info("Audio backend trace skipped for soundfile: %s", exc)

    try:
        logger.info("FunASR audio backend trace enabled: %s", label)
        yield
    finally:
        for owner, name, original in reversed(patched):
            setattr(owner, name, original)
        logger.info("FunASR audio backend trace disabled: %s", label)


def _format_command(args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
    if args:
        return args[0]
    if "args" in kwargs:
        return kwargs["args"]
    return "<unknown>"


def _find_external_caller() -> str:
    for frame_info in inspect.stack()[2:]:
        filename = frame_info.filename.replace("\\", "/")
        if "subprocess_trace_scope.py" in filename:
            continue
        return f"{frame_info.filename}:{frame_info.lineno}"
    return "<unknown>"


def _patch_attr(
    patched: list[tuple[Any, str, Any]],
    *,
    owner: Any,
    name: str,
    wrapper,
) -> None:
    original = getattr(owner, name, None)
    if original is None:
        return
    setattr(owner, name, wrapper(original))
    patched.append((owner, name, original))


def _wrap_audio_backend_call(
    *,
    label: str,
    backend: str,
    logger: logging.Logger,
):
    def _decorator(original):
        def _wrapped(*args: Any, **kwargs: Any):
            logger.warning(
                "FunASR audio backend trace: label=%s backend=%s action=call input=%s caller=%s",
                label,
                backend,
                _format_command(args, kwargs),
                _find_external_caller(),
            )
            try:
                result = original(*args, **kwargs)
            except Exception as exc:
                logger.warning(
                    "FunASR audio backend trace: label=%s backend=%s action=error error=%s",
                    label,
                    backend,
                    exc,
                )
                raise
            logger.warning(
                "FunASR audio backend trace: label=%s backend=%s action=ok",
                label,
                backend,
            )
            return result

        return _wrapped

    return _decorator
