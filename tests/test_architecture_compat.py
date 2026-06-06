"""Compatibility checks for the four-layer architecture migration."""

from flowscribe.app.models import TranscriptionJob as LegacyTranscriptionJob
from flowscribe.core.pipeline import LocalTranscriptionPipeline as LegacyPipeline
from flowscribe.queue.store import BatchQueueStore as LegacyBatchQueueStore
from flowscribe.transcription.local_whisper import LocalWhisperTranscriber as LegacyWhisper
from flowscribe.transcription.native_engine import NativeEngineTranscriber as LegacyNativeEngine
from flowscribe.transcription.providers import (
    resolve_transcription_provider as legacy_resolve_provider,
)

from flowscribe.pipeline.transcription import LocalTranscriptionPipeline
from flowscribe.providers.transcribe.local_whisper import LocalWhisperTranscriber
from flowscribe.providers.transcribe.native_engine import NativeEngineTranscriber
from flowscribe.providers.transcribe.registry import resolve_transcription_provider
from flowscribe.tasks.models import TranscriptionJob
from flowscribe.tasks.queue_store import BatchQueueStore


def test_legacy_import_paths_reexport_new_architecture_objects():
    assert LegacyTranscriptionJob is TranscriptionJob
    assert LegacyPipeline is LocalTranscriptionPipeline
    assert LegacyBatchQueueStore is BatchQueueStore
    assert LegacyWhisper is LocalWhisperTranscriber
    assert LegacyNativeEngine is NativeEngineTranscriber
    assert legacy_resolve_provider is resolve_transcription_provider
