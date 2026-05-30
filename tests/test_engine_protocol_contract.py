from __future__ import annotations

import json
import struct

from flowscribe.engine.protocol import PROTOCOL_VERSION, MessageKind, decode_header, encode_message


def test_python_frame_header_matches_native_protocol() -> None:
    payload = {"client_id": "test-client"}
    encoded = encode_message(MessageKind.HelloRequest, payload)

    payload_len, version, kind = struct.unpack("<I H H", encoded[:8])

    assert payload_len == len(encoded) - 8
    assert version == PROTOCOL_VERSION == 1
    assert kind == 0x0001
    assert decode_header(encoded[:8]) == (payload_len, version, kind)
    assert json.loads(encoded[8:].decode("utf-8")) == payload


def test_message_kind_values_match_native_message_h() -> None:
    assert MessageKind.HelloRequest == 0x0001
    assert MessageKind.HelloResult == 0x0002
    assert MessageKind.LoadModelRequest == 0x0010
    assert MessageKind.LoadModelResult == 0x0011
    assert MessageKind.SubmitJobRequest == 0x0020
    assert MessageKind.SubmitJobResult == 0x0021
    assert MessageKind.CancelJobRequest == 0x0022
    assert MessageKind.CancelJobResult == 0x0023
    assert MessageKind.QueryJobRequest == 0x0024
    assert MessageKind.QueryJobResult == 0x0025
    assert MessageKind.JobEvent == 0x0030
    assert MessageKind.JobResult == 0x0031
    assert MessageKind.JobError == 0x0032
    assert MessageKind.ShutdownRequest == 0x00F0
    assert MessageKind.ShutdownResult == 0x00F1


def test_submit_job_payload_uses_native_field_names() -> None:
    payload = {
        "job_id": "job-1",
        "audio_path": "D:/media/audio.wav",
        "language": "zh",
        "task": "transcribe",
        "vad_filter": True,
        "beam_size": 8,
        "initial_prompt": "domain words",
        "progressive": {
            "enabled": True,
            "chunk_seconds": 30.0,
            "overlap_seconds": 3.0,
        },
    }

    encoded = encode_message(MessageKind.SubmitJobRequest, payload)
    decoded = json.loads(encoded[8:].decode("utf-8"))

    assert set(decoded) == {
        "job_id",
        "audio_path",
        "language",
        "task",
        "vad_filter",
        "beam_size",
        "initial_prompt",
        "progressive",
    }
    assert set(decoded["progressive"]) == {"enabled", "chunk_seconds", "overlap_seconds"}


def test_job_event_payload_supports_chunk_progress_fields() -> None:
    payload = {
        "job_id": "job-1",
        "status": "chunk_completed",
        "progress": 0.5,
        "current_seconds": 30.0,
        "total_seconds": 60.0,
        "chunk_index": 1,
        "chunk_count": 2,
        "completed_chunks": 1,
        "runtime_slot": 0,
        "segments": [
            {
                "id": 1,
                "start": 0.5,
                "end": 2.0,
                "text": "hello",
                "words": [],
            }
        ],
    }

    encoded = encode_message(MessageKind.JobEvent, payload)
    decoded = json.loads(encoded[8:].decode("utf-8"))

    assert decoded == payload
