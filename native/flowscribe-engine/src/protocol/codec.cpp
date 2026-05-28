#include "flowscribe/engine/protocol/codec.h"

#include <cstring>

using nlohmann::json;

namespace flowscribe::engine::protocol {
namespace {

uint16_t read_u16_le(const uint8_t* data) {
    return static_cast<uint16_t>(data[0]) |
           static_cast<uint16_t>(static_cast<uint16_t>(data[1]) << 8);
}

uint32_t read_u32_le(const uint8_t* data) {
    return static_cast<uint32_t>(data[0]) |
           (static_cast<uint32_t>(data[1]) << 8) |
           (static_cast<uint32_t>(data[2]) << 16) |
           (static_cast<uint32_t>(data[3]) << 24);
}

void write_u16_le(std::vector<uint8_t>& buffer, size_t offset, uint16_t value) {
    buffer[offset] = static_cast<uint8_t>(value & 0xFFU);
    buffer[offset + 1] = static_cast<uint8_t>((value >> 8) & 0xFFU);
}

void write_u32_le(std::vector<uint8_t>& buffer, size_t offset, uint32_t value) {
    buffer[offset] = static_cast<uint8_t>(value & 0xFFU);
    buffer[offset + 1] = static_cast<uint8_t>((value >> 8) & 0xFFU);
    buffer[offset + 2] = static_cast<uint8_t>((value >> 16) & 0xFFU);
    buffer[offset + 3] = static_cast<uint8_t>((value >> 24) & 0xFFU);
}

template <typename T>
void read_optional(const json& j, const char* key, T& value) {
    if (j.contains(key) && !j.at(key).is_null()) {
        j.at(key).get_to(value);
    }
}

} // namespace

const char* message_kind_to_str(MessageKind kind) {
    switch (kind) {
    case MessageKind::HelloRequest:
        return "hello_request";
    case MessageKind::HelloResult:
        return "hello_result";
    case MessageKind::LoadModelRequest:
        return "load_model_request";
    case MessageKind::LoadModelResult:
        return "load_model_result";
    case MessageKind::SubmitJobRequest:
        return "submit_job_request";
    case MessageKind::SubmitJobResult:
        return "submit_job_result";
    case MessageKind::CancelJobRequest:
        return "cancel_job_request";
    case MessageKind::CancelJobResult:
        return "cancel_job_result";
    case MessageKind::JobEvent:
        return "job_event";
    case MessageKind::JobResult:
        return "job_result";
    case MessageKind::JobError:
        return "job_error";
    case MessageKind::ShutdownRequest:
        return "shutdown_request";
    case MessageKind::ShutdownResult:
        return "shutdown_result";
    default:
        return "unknown";
    }
}

bool is_known_message_kind(MessageKind kind) {
    return std::string(message_kind_to_str(kind)) != "unknown";
}

Message make_message(MessageKind kind, const std::string& json_payload) {
    Message msg;
    msg.header.payload_len = static_cast<uint32_t>(json_payload.size());
    msg.header.version = PROTOCOL_VERSION;
    msg.header.kind = kind;
    msg.json_payload = json_payload;
    return msg;
}

std::vector<uint8_t> encode_message(const Message& msg) {
    const uint32_t payload_len = static_cast<uint32_t>(msg.json_payload.size());
    std::vector<uint8_t> buffer(FRAME_HEADER_SIZE + payload_len);

    write_u32_le(buffer, 0, payload_len);
    write_u16_le(buffer, 4, msg.header.version);
    write_u16_le(buffer, 6, static_cast<uint16_t>(msg.header.kind));

    if (payload_len > 0) {
        std::memcpy(buffer.data() + FRAME_HEADER_SIZE, msg.json_payload.data(), payload_len);
    }

    return buffer;
}

bool decode_frame_header(const uint8_t* data, FrameHeader& out_header) {
    if (data == nullptr) {
        return false;
    }

    out_header.payload_len = read_u32_le(data);
    out_header.version = read_u16_le(data + 4);
    out_header.kind = static_cast<MessageKind>(read_u16_le(data + 6));
    return true;
}

bool decode_frame_header(const std::vector<uint8_t>& data, FrameHeader& out_header) {
    if (data.size() < FRAME_HEADER_SIZE) {
        return false;
    }
    return decode_frame_header(data.data(), out_header);
}

bool decode_message(const std::vector<uint8_t>& data, Message& out_message, std::string& error) {
    error.clear();

    FrameHeader header;
    if (!decode_frame_header(data, header)) {
        error = "message is shorter than frame header";
        return false;
    }

    if (header.version != PROTOCOL_VERSION) {
        error = "unsupported protocol version";
        return false;
    }

    if (!is_known_message_kind(header.kind)) {
        error = "unknown message kind";
        return false;
    }

    if (header.payload_len > MAX_PAYLOAD_SIZE) {
        error = "payload exceeds maximum size";
        return false;
    }

    const size_t expected_size = FRAME_HEADER_SIZE + static_cast<size_t>(header.payload_len);
    if (data.size() != expected_size) {
        error = "message size does not match frame header payload length";
        return false;
    }

    out_message.header = header;
    out_message.json_payload.assign(
        reinterpret_cast<const char*>(data.data() + FRAME_HEADER_SIZE),
        header.payload_len);
    return true;
}

void to_json(json& j, const HelloRequest& value) {
    j = json{{"client_id", value.client_id}};
}

void from_json(const json& j, HelloRequest& value) {
    j.at("client_id").get_to(value.client_id);
}

void to_json(json& j, const HelloResult& value) {
    j = json{
        {"ok", value.ok},
        {"engine_version", value.engine_version},
        {"protocol_version", value.protocol_version},
    };
}

void from_json(const json& j, HelloResult& value) {
    j.at("ok").get_to(value.ok);
    j.at("engine_version").get_to(value.engine_version);
    read_optional(j, "protocol_version", value.protocol_version);
}

void to_json(json& j, const LoadModelRequest& value) {
    j = json{
        {"model_path", value.model_path},
        {"model_name", value.model_name},
        {"use_gpu", value.use_gpu},
    };
}

void from_json(const json& j, LoadModelRequest& value) {
    j.at("model_path").get_to(value.model_path);
    j.at("model_name").get_to(value.model_name);
    read_optional(j, "use_gpu", value.use_gpu);
}

void to_json(json& j, const LoadModelResult& value) {
    j = json{
        {"ok", value.ok},
        {"error", value.error},
        {"model_load_time_ms", value.model_load_time_ms},
    };
}

void from_json(const json& j, LoadModelResult& value) {
    j.at("ok").get_to(value.ok);
    read_optional(j, "error", value.error);
    read_optional(j, "model_load_time_ms", value.model_load_time_ms);
}

void to_json(json& j, const ProgressiveOptions& value) {
    j = json{
        {"enabled", value.enabled},
        {"chunk_seconds", value.chunk_seconds},
        {"overlap_seconds", value.overlap_seconds},
    };
}

void from_json(const json& j, ProgressiveOptions& value) {
    read_optional(j, "enabled", value.enabled);
    read_optional(j, "chunk_seconds", value.chunk_seconds);
    read_optional(j, "overlap_seconds", value.overlap_seconds);
}

void to_json(json& j, const SubmitJobRequest& value) {
    j = json{
        {"job_id", value.job_id},
        {"audio_path", value.audio_path},
        {"language", value.language},
        {"task", value.task},
        {"vad_filter", value.vad_filter},
        {"beam_size", value.beam_size},
        {"initial_prompt", value.initial_prompt},
        {"progressive", value.progressive},
    };
}

void from_json(const json& j, SubmitJobRequest& value) {
    j.at("job_id").get_to(value.job_id);
    j.at("audio_path").get_to(value.audio_path);
    read_optional(j, "language", value.language);
    read_optional(j, "task", value.task);
    read_optional(j, "vad_filter", value.vad_filter);
    read_optional(j, "beam_size", value.beam_size);
    read_optional(j, "initial_prompt", value.initial_prompt);
    read_optional(j, "progressive", value.progressive);
}

void to_json(json& j, const SubmitJobResult& value) {
    j = json{
        {"ok", value.ok},
        {"job_id", value.job_id},
        {"error", value.error},
    };
}

void from_json(const json& j, SubmitJobResult& value) {
    j.at("ok").get_to(value.ok);
    j.at("job_id").get_to(value.job_id);
    read_optional(j, "error", value.error);
}

void to_json(json& j, const CancelJobRequest& value) {
    j = json{{"job_id", value.job_id}};
}

void from_json(const json& j, CancelJobRequest& value) {
    j.at("job_id").get_to(value.job_id);
}

void to_json(json& j, const CancelJobResult& value) {
    j = json{
        {"ok", value.ok},
        {"job_id", value.job_id},
        {"error", value.error},
    };
}

void from_json(const json& j, CancelJobResult& value) {
    j.at("ok").get_to(value.ok);
    j.at("job_id").get_to(value.job_id);
    read_optional(j, "error", value.error);
}

void to_json(json& j, const JobEvent& value) {
    j = json{
        {"job_id", value.job_id},
        {"status", value.status},
        {"progress", value.progress},
        {"current_seconds", value.current_seconds},
        {"total_seconds", value.total_seconds},
    };
}

void from_json(const json& j, JobEvent& value) {
    j.at("job_id").get_to(value.job_id);
    j.at("status").get_to(value.status);
    read_optional(j, "progress", value.progress);
    read_optional(j, "current_seconds", value.current_seconds);
    read_optional(j, "total_seconds", value.total_seconds);
}

void to_json(json& j, const WordTiming& value) {
    j = json{
        {"word", value.word},
        {"start", value.start},
        {"end", value.end},
    };
}

void from_json(const json& j, WordTiming& value) {
    j.at("word").get_to(value.word);
    read_optional(j, "start", value.start);
    read_optional(j, "end", value.end);
}

void to_json(json& j, const TranscriptSegment& value) {
    j = json{
        {"id", value.id},
        {"start", value.start},
        {"end", value.end},
        {"text", value.text},
        {"words", value.words},
    };
}

void from_json(const json& j, TranscriptSegment& value) {
    read_optional(j, "id", value.id);
    read_optional(j, "start", value.start);
    read_optional(j, "end", value.end);
    j.at("text").get_to(value.text);
    read_optional(j, "words", value.words);
}

void to_json(json& j, const JobResult& value) {
    j = json{
        {"job_id", value.job_id},
        {"duration_seconds", value.duration_seconds},
        {"segments", value.segments},
    };
}

void from_json(const json& j, JobResult& value) {
    j.at("job_id").get_to(value.job_id);
    read_optional(j, "duration_seconds", value.duration_seconds);
    read_optional(j, "segments", value.segments);
}

void to_json(json& j, const JobError& value) {
    j = json{
        {"job_id", value.job_id},
        {"code", value.code},
        {"message", value.message},
    };
}

void from_json(const json& j, JobError& value) {
    read_optional(j, "job_id", value.job_id);
    j.at("code").get_to(value.code);
    j.at("message").get_to(value.message);
}

void to_json(json& j, const ShutdownRequest&) {
    j = json::object();
}

void from_json(const json&, ShutdownRequest&) {
}

void to_json(json& j, const ShutdownResult& value) {
    j = json{
        {"ok", value.ok},
        {"error", value.error},
    };
}

void from_json(const json& j, ShutdownResult& value) {
    j.at("ok").get_to(value.ok);
    read_optional(j, "error", value.error);
}

} // namespace flowscribe::engine::protocol
