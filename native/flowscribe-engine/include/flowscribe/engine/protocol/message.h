#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace flowscribe::engine::protocol {

inline constexpr uint16_t PROTOCOL_VERSION = 1;
inline constexpr uint32_t FRAME_HEADER_SIZE = 8;
inline constexpr uint32_t MAX_PAYLOAD_SIZE = 64U * 1024U * 1024U;

enum class MessageKind : uint16_t {
    HelloRequest = 0x0001,
    HelloResult = 0x0002,

    LoadModelRequest = 0x0010,
    LoadModelResult = 0x0011,

    SubmitJobRequest = 0x0020,
    SubmitJobResult = 0x0021,
    CancelJobRequest = 0x0022,
    CancelJobResult = 0x0023,

    JobEvent = 0x0030,
    JobResult = 0x0031,
    JobError = 0x0032,

    ShutdownRequest = 0x00F0,
    ShutdownResult = 0x00F1,
};

const char* message_kind_to_str(MessageKind kind);
bool is_known_message_kind(MessageKind kind);

struct FrameHeader {
    uint32_t payload_len = 0;
    uint16_t version = PROTOCOL_VERSION;
    MessageKind kind = MessageKind::HelloRequest;
};

struct Message {
    FrameHeader header;
    std::string json_payload;
};

struct HelloRequest {
    std::string client_id;
};

struct HelloResult {
    bool ok = true;
    std::string engine_version;
    uint16_t protocol_version = PROTOCOL_VERSION;
};

struct LoadModelRequest {
    std::string model_path;
    std::string model_name;
    bool use_gpu = false;
};

struct LoadModelResult {
    bool ok = false;
    std::string error;
    int64_t model_load_time_ms = 0;
};

struct ProgressiveOptions {
    bool enabled = true;
    double chunk_seconds = 60.0;
    double overlap_seconds = 5.0;
};

struct SubmitJobRequest {
    std::string job_id;
    std::string audio_path;
    std::string language = "zh";
    std::string task = "transcribe";
    bool vad_filter = false;
    int beam_size = 5;
    std::string initial_prompt;
    ProgressiveOptions progressive;
};

struct SubmitJobResult {
    bool ok = false;
    std::string job_id;
    std::string error;
};

struct CancelJobRequest {
    std::string job_id;
};

struct CancelJobResult {
    bool ok = false;
    std::string job_id;
    std::string error;
};

struct JobEvent {
    std::string job_id;
    std::string status;
    double progress = 0.0;
    double current_seconds = 0.0;
    double total_seconds = 0.0;
};

struct WordTiming {
    std::string word;
    double start = 0.0;
    double end = 0.0;
};

struct TranscriptSegment {
    int id = 0;
    double start = 0.0;
    double end = 0.0;
    std::string text;
    std::vector<WordTiming> words;
};

struct JobResult {
    std::string job_id;
    double duration_seconds = 0.0;
    std::vector<TranscriptSegment> segments;
};

struct JobError {
    std::string job_id;
    std::string code;
    std::string message;
};

struct ShutdownRequest {
};

struct ShutdownResult {
    bool ok = true;
    std::string error;
};

} // namespace flowscribe::engine::protocol
