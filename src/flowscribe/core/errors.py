"""Project-specific exceptions."""

from __future__ import annotations


class FlowScribeError(Exception):
    """Base class for expected FlowScribe errors."""


class InputError(FlowScribeError):
    """Raised when user input cannot be resolved to media items."""


class MediaPreparationError(FlowScribeError):
    """Raised when media cannot be converted into transcription-ready audio."""


class TranscriptionError(FlowScribeError):
    """Raised when speech-to-text processing fails."""


class OutputError(FlowScribeError):
    """Raised when transcript artifacts cannot be written."""


class SearchError(FlowScribeError):
    """Raised when transcript search input cannot be processed."""
