#include "flowscribe/engine/protocol/codec.h"

#include <cstring>

using nlohmann::json;

namespace flowscribe::engine::protocol {

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

MessageKindRegistry::MessageKindRegistry() {
    REGISTER_MESSAGE_KIND(*this, HelloRequest, "hello_request");
    REGISTER_MESSAGE_KIND(*this, HelloResult, "hello_result");
    REGISTER_MESSAGE_KIND(*this, LoadModelRequest, "load_model_request");
    REGISTER_MESSAGE_KIND(*this, LoadModelResult, "load_model_result");
    REGISTER_MESSAGE_KIND(*this, SubmitJobRequest, "submit_job_request");
    REGISTER_MESSAGE_KIND(*this, SubmitJobResult, "submit_job_result");
    REGISTER_MESSAGE_KIND(*this, CancelJobRequest, "cancel_job_request");
    REGISTER_MESSAGE_KIND(*this, CancelJobResult, "cancel_job_result");
    REGISTER_MESSAGE_KIND(*this, QueryJobRequest, "query_job_request");
    REGISTER_MESSAGE_KIND(*this, QueryJobResult, "query_job_result");
    REGISTER_MESSAGE_KIND(*this, JobEvent, "job_event");
    REGISTER_MESSAGE_KIND(*this, JobResult, "job_result");
    REGISTER_MESSAGE_KIND(*this, JobError, "job_error");
    REGISTER_MESSAGE_KIND(*this, ShutdownRequest, "shutdown_request");
    REGISTER_MESSAGE_KIND(*this, ShutdownResult, "shutdown_result");
}

const char* message_kind_to_str(MessageKind kind) {
    thread_local std::string name;
    name = MessageKindRegistry::instance().to_str(kind);
    return name.c_str();
}

bool is_known_message_kind(MessageKind kind) {
    return MessageKindRegistry::instance().is_known(kind);
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
        {"runtime_count", value.runtime_count},
    };
}

void from_json(const json& j, LoadModelResult& value) {
    j.at("ok").get_to(value.ok);
    read_optional(j, "error", value.error);
    read_optional(j, "model_load_time_ms", value.model_load_time_ms);
    read_optional(j, "runtime_count", value.runtime_count);
}

void to_json(json& j, const ProgressiveOptions& value) {
    j = json{
        {"enabled", value.enabled},
        {"chunk_seconds", value.chunk_seconds},
        {"overlap_seconds", value.overlap_seconds},
        {"max_workers", value.max_workers},
    };
}

void from_json(const json& j, ProgressiveOptions& value) {
    read_optional(j, "enabled", value.enabled);
    read_optional(j, "chunk_seconds", value.chunk_seconds);
    read_optional(j, "overlap_seconds", value.overlap_seconds);
    read_optional(j, "max_workers", value.max_workers);
}

void to_json(json& j, const SubmitJobRequest& value) {
    j = json{
        {"job_id", value.job_id},
        {"audio_path", value.audio_path},
        {"language", value.language},
        {"task", value.task},
        {"vad_filter", value.vad_filter},
        {"beam_size", value.beam_size},
        {"threads", value.threads},
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
    read_optional(j, "threads", value.threads);
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

void to_json(json& j, const QueryJobRequest& value) {
    j = json{{"job_id", value.job_id}};
}

void from_json(const json& j, QueryJobRequest& value) {
    j.at("job_id").get_to(value.job_id);
}

void to_json(json& j, const JobEvent& value) {
    j = json{
        {"job_id", value.job_id},
        {"status", value.status},
        {"progress", value.progress},
        {"current_seconds", value.current_seconds},
        {"total_seconds", value.total_seconds},
        {"chunk_index", value.chunk_index},
        {"chunk_count", value.chunk_count},
        {"completed_chunks", value.completed_chunks},
        {"runtime_slot", value.runtime_slot},
        {"segments", value.segments},
    };
}

void from_json(const json& j, JobEvent& value) {
    j.at("job_id").get_to(value.job_id);
    j.at("status").get_to(value.status);
    read_optional(j, "progress", value.progress);
    read_optional(j, "current_seconds", value.current_seconds);
    read_optional(j, "total_seconds", value.total_seconds);
    read_optional(j, "chunk_index", value.chunk_index);
    read_optional(j, "chunk_count", value.chunk_count);
    read_optional(j, "completed_chunks", value.completed_chunks);
    read_optional(j, "runtime_slot", value.runtime_slot);
    read_optional(j, "segments", value.segments);
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

void to_json(json& j, const ChunkMetric& value) {
    j = json{
        {"index", value.index},
        {"start", value.start},
        {"end", value.end},
        {"runtime_slot", value.runtime_slot},
        {"acquire_wait_seconds", value.acquire_wait_seconds},
        {"elapsed_seconds", value.elapsed_seconds},
        {"threads", value.threads},
    };
}

void from_json(const json& j, ChunkMetric& value) {
    read_optional(j, "index", value.index);
    read_optional(j, "start", value.start);
    read_optional(j, "end", value.end);
    read_optional(j, "runtime_slot", value.runtime_slot);
    read_optional(j, "acquire_wait_seconds", value.acquire_wait_seconds);
    read_optional(j, "elapsed_seconds", value.elapsed_seconds);
    read_optional(j, "threads", value.threads);
}

void to_json(json& j, const JobResult& value) {
    j = json{
        {"job_id", value.job_id},
        {"duration_seconds", value.duration_seconds},
        {"segments", value.segments},
        {"chunked_enabled", value.chunked_enabled},
        {"chunk_count", value.chunk_count},
        {"runtime_count", value.runtime_count},
        {"effective_parallel_chunks", value.effective_parallel_chunks},
        {"chunk_threads", value.chunk_threads},
        {"chunk_seconds", value.chunk_seconds},
        {"overlap_seconds", value.overlap_seconds},
        {"chunk_metrics", value.chunk_metrics},
    };
}

void from_json(const json& j, JobResult& value) {
    j.at("job_id").get_to(value.job_id);
    read_optional(j, "duration_seconds", value.duration_seconds);
    read_optional(j, "segments", value.segments);
    read_optional(j, "chunked_enabled", value.chunked_enabled);
    read_optional(j, "chunk_count", value.chunk_count);
    read_optional(j, "runtime_count", value.runtime_count);
    read_optional(j, "effective_parallel_chunks", value.effective_parallel_chunks);
    read_optional(j, "chunk_threads", value.chunk_threads);
    read_optional(j, "chunk_seconds", value.chunk_seconds);
    read_optional(j, "overlap_seconds", value.overlap_seconds);
    read_optional(j, "chunk_metrics", value.chunk_metrics);
}

void to_json(json& j, const JobStatus& value) {
    j = json{
        {"job_id", value.job_id},
        {"audio_path", value.audio_path},
        {"status", value.status},
        {"progress", value.progress},
        {"created_at", value.created_at},
        {"started_at", value.started_at},
        {"finished_at", value.finished_at},
        {"error", value.error},
        {"result", value.result},
    };
}

void from_json(const json& j, JobStatus& value) {
    j.at("job_id").get_to(value.job_id);
    read_optional(j, "audio_path", value.audio_path);
    read_optional(j, "status", value.status);
    read_optional(j, "progress", value.progress);
    read_optional(j, "created_at", value.created_at);
    read_optional(j, "started_at", value.started_at);
    read_optional(j, "finished_at", value.finished_at);
    read_optional(j, "error", value.error);
    read_optional(j, "result", value.result);
}

void to_json(json& j, const QueryJobResult& value) {
    j = json{
        {"ok", value.ok},
        {"job_id", value.job_id},
        {"error", value.error},
        {"job", value.job},
    };
}

void from_json(const json& j, QueryJobResult& value) {
    j.at("ok").get_to(value.ok);
    j.at("job_id").get_to(value.job_id);
    read_optional(j, "error", value.error);
    read_optional(j, "job", value.job);
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
