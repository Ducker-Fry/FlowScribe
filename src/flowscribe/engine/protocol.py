import struct
import json

PIPE_NAME = r"\\.\pipe\flowscribe-engine-v1"
PROTOCOL_VERSION = 1

class MessageKind:
    # 握手
    HelloRequest = 0x0001
    HelloResult = 0x0002

    # 模型
    LoadModelRequest = 0x0010
    LoadModelResult = 0x0011

    # 任务
    SubmitJobRequest = 0x0020
    SubmitJobResult = 0x0021
    CancelJobRequest = 0x0022
    CancelJobResult = 0x0023
    QueryJobRequest = 0x0024
    QueryJobResult = 0x0025

    # 事件与结果
    JobEvent = 0x0030
    JobResult = 0x0031
    JobError = 0x0032

    # 关闭
    ShutdownRequest = 0x00F0
    ShutdownResult = 0x00F1

def encode_message(kind: int, payload: dict) -> bytes:
    json_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    payload_len = len(json_bytes)
    header = struct.pack("<I H H", payload_len, PROTOCOL_VERSION, kind)
    return header + json_bytes

def decode_header(header_bytes: bytes) -> tuple[int, int, int]:
    payload_len, version, kind = struct.unpack("<I H H", header_bytes)
    return payload_len, version, kind
